import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Meeting } from "../api";
import { StatusPill } from "../components/StatusPill";

export function Detail() {
  const { id = "" } = useParams();
  const [m, setM] = useState<Meeting | null>(null);
  const [transcript, setTranscript] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    async function tick() {
      try {
        const next = await api.getMeeting(id);
        if (!live) return;
        setM(next);
        if (next.has_transcript && transcript === null) {
          setTranscript(await api.transcript(id));
        }
      } catch { /* ignore */ }
    }
    tick();
    const t = setInterval(tick, 3000);
    return () => { live = false; clearInterval(t); };
  }, [id, transcript]);

  if (!m) return <div className="text-slate-400">loading…</div>;

  const isActive = ["queued", "joining", "waiting_admit", "recording", "transcribing"].includes(m.status);

  return (
    <div className="space-y-6">
      <Link to="/" className="text-sm text-slate-400 hover:text-slate-100">← back</Link>

      <div className="bg-slate-900 rounded-lg p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-mono text-xs text-slate-500">{m.id}</div>
            <h1 className="font-semibold">{m.display_name}</h1>
            <a href={m.url} target="_blank" className="text-sm text-indigo-400 hover:underline">
              {m.url}
            </a>
          </div>
          <StatusPill status={m.status} />
        </div>
        {m.error && <div className="text-sm text-red-400">{m.error}</div>}
        {isActive && (
          <button
            onClick={() => api.cancelMeeting(id).catch(() => {})}
            className="text-sm text-red-400 hover:text-red-300"
          >
            cancel
          </button>
        )}
      </div>

      {m.has_recording && (
        <div className="bg-slate-900 rounded-lg p-5 space-y-2">
          <h2 className="font-semibold">Recording</h2>
          <audio controls src={api.recordingUrl(id)} className="w-full" />
        </div>
      )}

      {m.has_transcript && (
        <div className="bg-slate-900 rounded-lg p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Transcript</h2>
            <button
              onClick={() => transcript && navigator.clipboard.writeText(transcript)}
              className="text-sm text-slate-400 hover:text-slate-100"
            >
              copy
            </button>
          </div>
          <pre className="whitespace-pre-wrap text-sm text-slate-300 font-sans">
            {transcript ?? "loading…"}
          </pre>
        </div>
      )}
    </div>
  );
}
