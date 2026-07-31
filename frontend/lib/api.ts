export type RepositoryStatus = "queued" | "indexing" | "ready" | "failed" | "cancelled";

export type Repository = {
  id: string;
  url: string;
  owner: string;
  name: string;
  branch: string | null;
  status: RepositoryStatus;
  indexed_at: string;
  updated_at: string | null;
  progress: number;
  stage: string | null;
  file_count: number;
  chunk_count: number;
  error: string | null;
};

export type RepositoryFile = {
  path: string;
  language: string;
  size_bytes: number;
  content?: string | null;
};

export type Source = {
  path: string;
  start_line: number;
  end_line: number;
  score: number;
  excerpt: string;
  language?: string | null;
};

export type ChatTurn = { role: "user" | "assistant"; content: string };
export type ChatResponse = { answer: string; sources: Source[] };

export type LanguageBreakdown = { language: string; file_count: number; chunk_count: number; share: number };
export type FileWeight = { path: string; language: string; chunk_count: number; character_count: number };
export type RepositoryInsights = {
  repository_id: string;
  owner: string;
  name: string;
  branch: string | null;
  indexed_at: string;
  file_count: number;
  chunk_count: number;
  total_characters: number;
  average_chunk_characters: number;
  languages: LanguageBreakdown[];
  largest_files: FileWeight[];
  documentation_files: string[];
};
export type SymbolEntry = { name: string; kind: string; line: number };
export type FileOutline = { path: string; language: string; line_count: number; symbols: SymbolEntry[] };
export type RepositoryMatches = { repository_id: string; owner: string; name: string; sources: Source[] };
export type MultiSearchResult = { query: string; repositories: RepositoryMatches[] };
export type ConversationMessage = { role: "user" | "assistant"; content: string; sources?: Source[] };
export type ConversationSummary = {
  id: string;
  repository_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
};
export type Conversation = ConversationSummary & { messages: ConversationMessage[] };
export type Metrics = {
  repositories_total: number;
  repositories_by_status: Record<string, number>;
  files_indexed: number;
  chunks_indexed: number;
  active_index_jobs: number;
  conversations_saved: number;
  providers: Record<string, string>;
};

export type IndexRepositoryInput = { url: string; branch?: string; access_token?: string };
export type SearchInput = {
  query: string;
  limit?: number;
  languages?: string[];
  path_prefix?: string;
  min_score?: number;
};
type ApiError = { detail?: string };
type StreamEvent = { event: "delta"; text: string } | { event: "sources"; sources: Source[] } | { event: "done" };

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const API_KEY = process.env.NEXT_PUBLIC_REPOSAGE_API_KEY;

function headers(init?: HeadersInit): Headers {
  const result = new Headers(init);
  result.set("Content-Type", "application/json");
  if (API_KEY) result.set("X-API-Key", API_KEY);
  return result;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { ...init, headers: headers(init?.headers) });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as ApiError;
    throw new Error(body.detail ?? `Request failed with status ${response.status}.`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function repositoryPayload(input: IndexRepositoryInput) {
  return Object.fromEntries(Object.entries(input).filter(([, value]) => value));
}

export const api = {
  listRepositories: () => request<Repository[]>("/api/repositories"),
  getRepository: (repositoryId: string) => request<Repository>(`/api/repositories/${encodeURIComponent(repositoryId)}`),
  indexRepository: (input: IndexRepositoryInput) => request<Repository>("/api/repositories", { method: "POST", body: JSON.stringify(repositoryPayload(input)) }),
  reindexRepository: (repositoryId: string, input: Omit<IndexRepositoryInput, "url"> = {}) => request<Repository>(`/api/repositories/${encodeURIComponent(repositoryId)}/reindex`, { method: "POST", body: JSON.stringify(repositoryPayload(input as IndexRepositoryInput)) }),
  deleteRepository: (repositoryId: string) => request<void>(`/api/repositories/${encodeURIComponent(repositoryId)}`, { method: "DELETE" }),
  cancelIndexing: (repositoryId: string) => request<Repository>(`/api/repositories/${encodeURIComponent(repositoryId)}/cancel`, { method: "POST" }),
  insights: (repositoryId: string) => request<RepositoryInsights>(`/api/repositories/${encodeURIComponent(repositoryId)}/insights`),
  outline: (repositoryId: string, path: string) => request<FileOutline>(`/api/repositories/${encodeURIComponent(repositoryId)}/outline?path=${encodeURIComponent(path)}`),
  metrics: () => request<Metrics>("/api/metrics"),
  listFiles: (repositoryId: string) => request<RepositoryFile[]>(`/api/repositories/${encodeURIComponent(repositoryId)}/files`),
  getFile: (repositoryId: string, path: string) => request<RepositoryFile>(`/api/repositories/${encodeURIComponent(repositoryId)}/files/${path.split("/").map(encodeURIComponent).join("/")}`),
  search: (repositoryId: string, input: SearchInput) => request<{ query: string; sources: Source[] }>("/api/search", { method: "POST", body: JSON.stringify({ repository_id: repositoryId, limit: 8, ...input }) }),
  searchAll: (input: SearchInput & { limit_per_repository?: number }) => request<MultiSearchResult>("/api/search/all", { method: "POST", body: JSON.stringify({ limit_per_repository: 3, ...input }) }),
  similar: (repositoryId: string, path: string, line = 1) => request<{ query: string; sources: Source[] }>("/api/similar", { method: "POST", body: JSON.stringify({ repository_id: repositoryId, path, line }) }),
  listConversations: (repositoryId?: string) => request<ConversationSummary[]>(`/api/conversations${repositoryId ? `?repository_id=${encodeURIComponent(repositoryId)}` : ""}`),
  saveConversation: (repositoryId: string, messages: ConversationMessage[], title?: string) => request<Conversation>("/api/conversations", { method: "POST", body: JSON.stringify({ repository_id: repositoryId, messages, ...(title && { title }) }) }),
  getConversation: (conversationId: string) => request<Conversation>(`/api/conversations/${encodeURIComponent(conversationId)}`),
  deleteConversation: (conversationId: string) => request<void>(`/api/conversations/${encodeURIComponent(conversationId)}`, { method: "DELETE" }),
  exportConversationUrl: (conversationId: string) => `${API_URL}/api/conversations/${encodeURIComponent(conversationId)}/export`,
  async exportConversation(conversationId: string): Promise<{ filename: string; markdown: string }> {
    const response = await fetch(api.exportConversationUrl(conversationId), { headers: headers() });
    if (!response.ok) throw new Error(`Export failed with status ${response.status}.`);
    return { filename: `reposage-${conversationId}.md`, markdown: await response.text() };
  },
  chat: (repositoryId: string, question: string, history: ChatTurn[] = []) => request<ChatResponse>("/api/chat", { method: "POST", body: JSON.stringify({ repository_id: repositoryId, question, history }) }),
  async streamChat(
    repositoryId: string,
    question: string,
    history: ChatTurn[],
    onEvent: (event: StreamEvent) => void,
  ): Promise<void> {
    const response = await fetch(`${API_URL}/api/chat/stream`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({ repository_id: repositoryId, question, history }),
    });
    if (!response.ok || !response.body) {
      const body = (await response.json().catch(() => ({}))) as ApiError;
      throw new Error(body.detail ?? `Request failed with status ${response.status}.`);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      const messages = buffer.split("\n\n");
      buffer = messages.pop() ?? "";
      for (const message of messages) {
        const event = message.match(/^event: (.+)$/m)?.[1];
        const data = message.match(/^data: (.+)$/m)?.[1];
        if (!event || !data) continue;
        const payload = JSON.parse(data) as { text?: string; sources?: Source[] };
        if (event === "delta" && payload.text) onEvent({ event: "delta", text: payload.text });
        if (event === "sources") onEvent({ event: "sources", sources: payload.sources ?? [] });
        if (event === "done") onEvent({ event: "done" });
      }
      if (done) break;
    }
  },
};
