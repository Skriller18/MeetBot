import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";

export function Login() {
  const nav = useNavigate();
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await api.login(pw);
      nav("/", { replace: true });
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 401 ? "wrong password" : "login failed");
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center">
      <form onSubmit={onSubmit} className="w-full max-w-sm bg-slate-900 p-6 rounded-lg space-y-4">
        <h1 className="text-lg font-semibold">Meet Notetaker</h1>
        <input
          type="password"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          placeholder="password"
          autoFocus
          className="w-full bg-slate-800 px-3 py-2 rounded outline-none focus:ring-2 focus:ring-indigo-500"
        />
        {err && <div className="text-sm text-red-400">{err}</div>}
        <button
          disabled={busy || !pw}
          className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 px-3 py-2 rounded"
        >
          {busy ? "…" : "log in"}
        </button>
      </form>
    </div>
  );
}
