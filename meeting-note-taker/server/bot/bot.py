"""Headless-Chromium Meet bot. Joins as guest, records remote audio, leaves."""
from __future__ import annotations

import asyncio
import base64
import os
import subprocess
import time
from pathlib import Path
from typing import Awaitable, Callable, Optional

from playwright.async_api import async_playwright, Page, BrowserContext

INJECT_JS = (Path(__file__).parent / "inject_capture.js").read_text()

CHROMIUM_FLAGS = [
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-setuid-sandbox",
    "--disable-gpu",
    "--window-size=1280,800",
    "--start-maximized",
    "--disable-extensions",
    "--disable-infobars",
    "--disable-notifications",
    "--disable-popup-blocking",
    "--disable-features=IsolateOrigins,site-per-process",
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
        debug_dir: Optional[Path] = None,
        headless: bool = True,
        use_real_chrome: bool = False,
    ):
        self.meet_url = meet_url
        self.display_name = display_name
        self.out_webm = out_webm
        self._on_status = on_status or _noop
        self._chunks: list[bytes] = []
        self._page: Optional[Page] = None
        self._ctx: Optional[BrowserContext] = None
        self._debug_dir = debug_dir
        self._headless = headless
        self._use_real_chrome = use_real_chrome

    async def _on_chunk(self, b64: str) -> None:
        self._chunks.append(base64.b64decode(b64))

    async def _take_screenshot(self, page: Page, name: str) -> None:
        if self._debug_dir:
            self._debug_dir.mkdir(parents=True, exist_ok=True)
            path = self._debug_dir / f"{name}_{int(time.time())}.png"
            await page.screenshot(path=path, full_page=True)
            print(f"[debug] screenshot: {path}")

    async def _dump_html(self, page: Page, name: str) -> None:
        if self._debug_dir:
            self._debug_dir.mkdir(parents=True, exist_ok=True)
            path = self._debug_dir / f"{name}_{int(time.time())}.html"
            html = await page.content()
            path.write_text(html)
            print(f"[debug] html dump: {path}")

    async def _enter_name_and_request(self, page: Page) -> None:
        print(f"[bot] current URL: {page.url}")
        await self._take_screenshot(page, "1_pre_join")
        await self._dump_html(page, "1_pre_join")

        # Try to dismiss any initial dialogs/popups
        try:
            await page.get_by_role("button", name="Got it").click(timeout=3000)
        except Exception:
            pass

        # Turn off mic and camera
        for label in ("Turn off microphone", "Turn off camera"):
            try:
                await page.get_by_role("button", name=label).click(timeout=3000)
                print(f"[bot] clicked: {label}")
            except Exception:
                print(f"[bot] could not click: {label}")

        await self._take_screenshot(page, "2_after_mic_camera")

        # Fill name field
        try:
            await page.get_by_role("textbox", name="Your name").fill(self.display_name, timeout=15000)
            print(f"[bot] filled name via textbox")
        except Exception:
            try:
                await page.locator('input[type="text"]').first.fill(self.display_name, timeout=10000)
                print(f"[bot] filled name via input locator")
            except Exception as e:
                print(f"[bot] could not fill name: {e}")
                # Try to find any input field
                inputs = await page.locator('input').all()
                print(f"[bot] found {len(inputs)} input fields")
                for i, inp in enumerate(inputs):
                    try:
                        placeholder = await inp.get_attribute('placeholder') or ''
                        aria_label = await inp.get_attribute('aria-label') or ''
                        print(f"  input[{i}]: placeholder='{placeholder}', aria-label='{aria_label}'")
                    except:
                        pass

        await self._take_screenshot(page, "3_after_name")
        await self._dump_html(page, "3_after_name")

        # Click join button
        for label in ("Ask to join", "Join now", "Join meeting"):
            try:
                btn = page.get_by_role("button", name=label)
                count = await btn.count()
                if count > 0:
                    await btn.click(timeout=5000)
                    print(f"[bot] clicked join button: '{label}'")
                    return
            except Exception as e:
                print(f"[bot] button '{label}' not found: {e}")

        # Fallback: look for any button containing "join"
        try:
            buttons = await page.locator('button').all()
            print(f"[bot] found {len(buttons)} buttons:")
            for i, btn in enumerate(buttons):
                try:
                    text = await btn.text_content() or ''
                    aria_label = await btn.get_attribute('aria-label') or ''
                    print(f"  button[{i}]: text='{text.strip()}', aria-label='{aria_label}'")
                    if 'join' in text.lower() or 'join' in aria_label.lower():
                        await btn.click(timeout=5000)
                        print(f"[bot] clicked fallback join button")
                        return
                except:
                    pass
        except Exception as e:
            print(f"[bot] fallback button search failed: {e}")

        await self._take_screenshot(page, "4_join_failed")
        raise RuntimeError("Could not find join button")

    async def _wait_for_admission(self, page: Page, timeout_s: int = 300) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                await page.get_by_role("button", name="Leave call").wait_for(timeout=5000)
                print("[bot] admitted to meeting!")
                return
            except Exception:
                # Check if we're still on the waiting page
                try:
                    waiting_text = await page.get_by_text("Waiting to be let in").count()
                    if waiting_text > 0:
                        print("[bot] still waiting for admission...")
                except:
                    pass
                await asyncio.sleep(2)
        raise TimeoutError("Host did not admit bot within timeout")

    async def run(self, duration_s: int) -> Path:
        # Get Chrome profile from environment or use default
        chrome_user_data_dir = os.environ.get("GOOGLE_CHROME_USER_DATA_DIR")
        chrome_profile = os.environ.get("GOOGLE_CHROME_PROFILE", "Profile 1")
        
        async with async_playwright() as p:
            if self._use_real_chrome and os.path.exists("/Applications/Google Chrome.app"):
                # Use real Google Chrome with user's profile
                print("[bot] using real Google Chrome.app")
                chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
                
                # Launch Chrome with remote debugging
                debug_port = 9222
                chrome_process = subprocess.Popen([
                    chrome_path,
                    f"--remote-debugging-port={debug_port}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--user-data-dir=/tmp/chrome-bot-profile",  # Use a temp profile to avoid conflicts
                    "--headless=new" if self._headless else "",
                ] + [flag for flag in CHROMIUM_FLAGS if flag not in ["--headless", "--headless=new"]], 
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
                
                await asyncio.sleep(3)  # Wait for Chrome to start
                
                # Connect to Chrome via CDP
                try:
                    browser = await p.chromium.connect_over_cdp(f"http://localhost:{debug_port}")
                    ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
                    print("[bot] connected to Chrome via CDP")
                except Exception as e:
                    print(f"[bot] failed to connect to Chrome: {e}")
                    chrome_process.terminate()
                    raise
                
            elif chrome_user_data_dir and Path(chrome_user_data_dir).exists():
                print(f"[bot] using Chrome profile: {chrome_user_data_dir}/{chrome_profile}")
                
                # Use persistent context with the specific profile
                profile_path = Path(chrome_user_data_dir) / chrome_profile
                if not profile_path.exists():
                    print(f"[bot] Warning: Profile {chrome_profile} not found, using Default")
                    profile_path = Path(chrome_user_data_dir) / "Default"
                
                # Launch with user_data_dir - Playwright will use this profile
                browser = await p.chromium.launch_persistent_context(
                    user_data_dir=str(profile_path),
                    headless=self._headless,
                    args=CHROMIUM_FLAGS,
                    permissions=["microphone", "camera"],
                    viewport={"width": 1280, "height": 800},
                )
                ctx = browser
            else:
                print("[bot] using default Playwright Chromium")
                browser = await p.chromium.launch(
                    headless=self._headless,
                    args=CHROMIUM_FLAGS,
                )
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
            print(f"[bot] navigating to: {self.meet_url}")
            await page.goto(self.meet_url, wait_until="domcontentloaded")
            print(f"[bot] page loaded, URL: {page.url}")

            await self._enter_name_and_request(page)

            await self._on_status("waiting_admit")
            await self._wait_for_admission(page)

            await self._on_status("recording")
            await page.evaluate("window.__startCapture()")
            print(f"[bot] recording for {duration_s}s...")
            await asyncio.sleep(duration_s)
            await page.evaluate("window.__stopCapture()")
            await asyncio.sleep(1)

            try:
                await page.get_by_role("button", name="Leave call").click(timeout=5000)
                print("[bot] left the meeting")
            except Exception:
                print("[bot] could not click leave call")

            await ctx.close()
            if 'browser' in locals() and hasattr(browser, 'close') and browser != ctx:
                await browser.close()

        self.out_webm.write_bytes(b"".join(self._chunks))
        print(f"[bot] saved recording: {self.out_webm}")
        return self.out_webm
