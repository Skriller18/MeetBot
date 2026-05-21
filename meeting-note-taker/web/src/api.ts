export type Meeting = {
  id: string;
  url: string;
  display_name: string;
  duration_cap_s: number;
  status:
    | "queued" | "joining" | "waiting_admit" | "recording"
    | "transcribing" | "done" | "failed" | "cancelled";
  error: string | null;
  created_at: number;
  started_at: number | null;
  ended_at: number | null;
  has_recording: boolean;
  has_transcript: boolean;
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, text);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json() as Promise<T>;
  return res.text() as unknown as Promise<T>;
}

export const api = {
  login: (password: string) =>
    req<{ ok: boolean }>("/api/login", { method: "POST", body: JSON.stringify({ password }) }),
  logout: () => req<{ ok: boolean }>("/api/logout", { method: "POST" }),
  me: () => req<{ user: string }>("/api/me"),
  listMeetings: () => req<Meeting[]>("/api/meetings"),
  getMeeting: (id: string) => req<Meeting>(`/api/meetings/${id}`),
  createMeeting: (body: { url: string; display_name?: string; duration_cap_s?: number }) =>
    req<Meeting>("/api/meetings", { method: "POST", body: JSON.stringify(body) }),
  cancelMeeting: (id: string) =>
    req<{ ok: boolean }>(`/api/meetings/${id}/cancel`, { method: "POST" }),
  transcript: (id: string) => req<string>(`/api/meetings/${id}/transcript`),
  recordingUrl: (id: string) => `/api/meetings/${id}/recording`,
};
