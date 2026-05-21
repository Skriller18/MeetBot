const COLORS: Record<string, string> = {
  queued:         "bg-slate-700 text-slate-200",
  joining:        "bg-amber-700 text-amber-100",
  waiting_admit:  "bg-amber-700 text-amber-100",
  recording:      "bg-emerald-700 text-emerald-100",
  transcribing:   "bg-indigo-700 text-indigo-100",
  done:           "bg-emerald-900 text-emerald-300",
  failed:         "bg-red-900 text-red-300",
  cancelled:      "bg-slate-800 text-slate-400",
};

export function StatusPill({ status }: { status: string }) {
  const cls = COLORS[status] ?? "bg-slate-700 text-slate-200";
  return (
    <span className={`text-xs px-2 py-1 rounded-full ${cls}`}>
      {status.replace("_", " ")}
    </span>
  );
}
