const API_BASE = "http://localhost:8000";
const TIMEOUT = 120000;

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        ...(options?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...options?.headers,
      },
    });
    if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
    return res.json();
  } finally {
    clearTimeout(timer);
  }
}

export interface Source {
  id: string;
  summary: string;
  source_type: string;
  source: string;
  tags: string[];
  distance: number;
  created_at: string;
  rerank_score?: number;
  rrf_score?: number;
  parent_id?: string;
  chunk_index?: number;
}

export interface EvaluationScores {
  faithfulness: number;
  answer_relevancy: number;
  context_precision: number;
  overall: number;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
  query: string;
  evaluation?: EvaluationScores;
  crag_triggered?: boolean;
}

export interface SearchResponse {
  results: Source[];
  query: string;
}

export interface StatsResponse {
  total_documents: number;
  total_chunks?: number;
  unique_parents?: number;
  collection_name: string;
  by_type?: Record<string, number>;
  file_counts?: { images_on_disk: number; documents_on_disk: number; bookmarks: number };
}

export interface HealthResponse {
  status: string;
  version: string;
}

export interface IngestResponse {
  message: string;
  summary: string;
  tags: string[];
  source_type: string;
}

export interface BookmarkSyncResponse {
  message: string;
  processed: number;
  errors: number;
  total: number;
}

export interface WatchdogResponse {
  message: string;
  directories?: string[];
}

export const api = {
  health: () => apiFetch<HealthResponse>("/health"),
  stats: () => apiFetch<StatsResponse>("/api/stats"),
  chat: (query: string, top_k = 5) =>
    apiFetch<ChatResponse>("/api/chat", { method: "POST", body: JSON.stringify({ query, top_k }) }),
  search: (query: string, top_k = 10) =>
    apiFetch<SearchResponse>("/api/search", { method: "POST", body: JSON.stringify({ query, top_k }) }),
  storeUrl: (url: string) =>
    apiFetch<IngestResponse>("/api/store/url", { method: "POST", body: JSON.stringify({ url }) }),
  storeText: (text: string, title: string) =>
    apiFetch<IngestResponse>("/api/store/text", { method: "POST", body: JSON.stringify({ text, title }) }),
  storeFile: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return apiFetch<IngestResponse>("/api/store/file", { method: "POST", body: fd });
  },
  syncBookmarks: (bookmark_path?: string) =>
    apiFetch<BookmarkSyncResponse>("/api/bookmarks/sync", {
      method: "POST",
      body: JSON.stringify(bookmark_path ? { bookmark_path } : {}),
    }),
  watchdogStart: (directories: string[]) =>
    apiFetch<WatchdogResponse>("/api/watchdog/start", { method: "POST", body: JSON.stringify({ directories }) }),
  watchdogStop: () =>
    apiFetch<WatchdogResponse>("/api/watchdog/stop", { method: "POST" }),
};
