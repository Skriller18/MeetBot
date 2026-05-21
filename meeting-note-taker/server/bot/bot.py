"""Headless-Chromium Meet bot. Joins as guest, records remote audio, leaves."""
from __future__ import annotations

import asyncio
import base64
import time
from pathlib import Path
from typing import Awaitable, Callable, Optional

from playwright.async_api import async_playwright, Page, BrowserContext

INJECT_JS = (Path(__file__).parent / "inject_capture.js").read_text()

CHROMIUM_FLAGS = [
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
]

# Status values the worker writes to the DB. Kept as plain strings so the
# bot module has no dependency on the server package.
StatusFn = Callable[[str], Awaitable[None]]


async def _noop(_status: str) -> None:
    pass


class MeetBot:
    def __init__(
        self,
        meet_url: str,
        display_name: str,
        out_webm: Path,
        on_status: Optional[StatusFn] = None,
    ):
        self.meet_url = meet_url
        self.display_name = display_name
        self.out_webm = out_webm
        self._on_status = on_status or _noop
        self._chunks: list[bytes] = []
        self._page: Optional[Page] = None
        self._ctx: Optional[BrowserContext] = None

    async def _on_chunk(self, b64: str) -> None:
        self._chunks.append(base64.b64decode(b64))

    async def _enter_name_and_request(self, page: Page) -> None:
        for label in ("Turn off microphone", "Turn off camera"):
            try:
                await page.get_by_role("button", name=label).click(timeout=3000)
            except Exception:
                pass

        try:
            await page.get_by_role("textbox", name="Your name").fill(self.display_name, timeout=15000)
        except Exception:
            await page.locator('input[type="text"]').first.fill(self.display_name)

        for label in ("Ask to join", "Join now"):
            try:
                await page.get_by_role("button", name=label).click(timeout=5000)
                return
            except Exception:
                continue
        raise RuntimeError("Could not find join button")

    async def _wait_for_admission(self, page: Page, timeout_s: int = 300) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                await page.get_by_role("button", name="Leave call").wait_for(timeout=5000)
                return
            except Exception:
                pass
        raise TimeoutError("Host did not admit bot within timeout")

    async def run(self, duration_s: int) -> Path:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=CHROMIUM_FLAGS)
            ctx = await browser.new_context(
                permissions=["microphone", "camera"],
                viewport={"width": 1280, "height": 800},
            )
            self._ctx = ctx

            await ctx.expose_function("__sendAudioChunk", self._on_chunk)
            await ctx.add_init_script(INJECT_JS)

            page = await ctx.new_page()
            self._page = page

            await self._on_status("joining")
            await page.goto(self.meet_url, wait_until="domcontentloaded")
            await self._enter_name_and_request(page)

            await self._on_status("waiting_admit")
            await self._wait_for_admission(page)

            await self._on_status("recording")
            await page.evaluate("window.__startCapture()")
            await asyncio.sleep(duration_s)
            await page.evaluate("window.__stopCapture()")
            await asyncio.sleep(1)

            try:
                await page.get_by_role("button", name="Leave call").click(timeout=5000)
            except Exception:
                pass

            await ctx.close()
            await browser.close()

        self.out_webm.write_bytes(b"".join(self._chunks))
        return self.out_webm
