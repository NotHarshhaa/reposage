export type Repository = {
  id: string;
  url: string;
  owner: string;
  name: string;
  branch: string | null;
  status: "ready" | "failed";
  indexed_at: string;
  file_count: number;
  chunk_count: number;
  error: string | null;
};

export type Source = {
  path: string;
  start_line: number;
  end_line: number;
  score: number;
  excerpt: string;
};

export type ChatResponse = { answer: string; sources: Source[] };

type ApiError = { detail?: string };

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiError;
    throw new Error(body.detail ?? `Request failed with status ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listRepositories: () => request<Repository[]>("/api/repositories"),
  indexRepository: (url: string) => request<Repository>("/api/repositories", { method: "POST", body: JSON.stringify({ url }) }),
  chat: (repositoryId: string, question: string) => request<ChatResponse>("/api/chat", { method: "POST", body: JSON.stringify({ repository_id: repositoryId, question }) }),
};
