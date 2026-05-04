import { FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, Meeting } from "../api";
import { StatusPill } from "../components/StatusPill";

export function Dashboard() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [duration, setDuration] = useState(30);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setMeetings(await api.listMeetings());
    } catch {
      // session might have expired; App will redirect on next /me poll
    }
  }

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, []);

  async function onCreate(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await api.createMeeting({
        url,
        display_name: name || undefined,
        duration_cap_s: duration * 60,
      });
      setUrl("");
      setName("");
      await refresh();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setErr("another meeting is already in progress");
      } else if (e instanceof ApiError) {
        setErr(`error ${e.status}: ${e.message}`);
      } else {
        setErr("could not start meeting");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <form onSubmit={onCreate} className="bg-slate-900 rounded-lg p-5 space-y-3">
        <h2 className="font-semibold">Join a meeting</h2>
        <input
          type="url"
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://meet.google.com/abc-defg-hij"
          className="w-full bg-slate-800 px-3 py-2 rounded outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <div className="flex gap-3">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="bot name (optional)"
            className="flex-1 bg-slate-800 px-3 py-2 rounded outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <label className="flex items-center gap-2 text-sm text-slate-400">
            duration:
            <input
              type="number"
              min={1}
              max={240}
              value={duration}
              onChange={(e) => setDuration(parseInt(e.target.value || "30", 10))}
              className="w-20 bg-slate-800 px-2 py-2 rounded outline-none"
            />
            min
          </label>
        </div>
        {err && <div className="text-sm text-red-400">{err}</div>}
        <button
          disabled={busy || !url}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 px-4 py-2 rounded"
        >
          {busy ? "…" : "send bot"}
        </button>
      </form>

      <section>
        <h2 className="font-semibold mb-3">Past meetings</h2>
        {meetings.length === 0 ? (
          <div className="text-sm text-slate-500">no meetings yet</div>
        ) : (
          <ul className="divide-y divide-slate-800 bg-slate-900 rounded-lg">
            {meetings.map((m) => (
              <li key={m.id}>
                <Link to={`/m/${m.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-slate-800">
                  <div className="min-w-0">
                    <div className="font-mono text-xs text-slate-500">{m.id}</div>
                    <div className="text-sm truncate">{m.display_name} — {m.url}</div>
                  </div>
                  <StatusPill status={m.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
