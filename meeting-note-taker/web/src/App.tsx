import { useEffect, useState } from "react";
import { Link, Outlet, useNavigate } from "react-router-dom";
import { api, ApiError } from "./api";

export function App() {
  const nav = useNavigate();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    api.me()
      .then(() => setReady(true))
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) nav("/login", { replace: true });
      });
  }, [nav]);

  if (!ready) return <div className="p-8 text-slate-400">loading…</div>;

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <Link to="/" className="font-semibold">Meet Notetaker</Link>
        <button
          onClick={async () => { await api.logout(); nav("/login"); }}
          className="text-sm text-slate-400 hover:text-slate-100"
        >
          log out
        </button>
      </header>
      <main className="max-w-5xl mx-auto p-6"><Outlet /></main>
    </div>
  );
}
