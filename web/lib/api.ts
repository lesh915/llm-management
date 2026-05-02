/**
 * API Gateway 클라이언트.
 * 브라우저에서는 /api/* (next.config.ts rewrites → localhost:8000)를 사용.
 * SSR에서는 NEXT_PUBLIC_API_URL 환경 변수를 직접 사용.
 */

const BASE = typeof window === "undefined"
  ? (process.env.NEXT_PUBLIC_API_URL ?? "http://api-gateway:8000")
  : "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${BASE}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

// ── 타입 정의 ──────────────────────────────────────────────────────────────────

export interface Agent {
  id: string;
  name: string;
  description?: string;
  owner: string;
  created_at: string;
}

export interface AgentArtifact {
  id: string;
  agent_id: string;
  type: "prompt" | "mcp" | "skill" | "tool_schema";
  version: number;
  content: Record<string, unknown>;
  model_requirements: string[];
  created_at: string;
}

export interface Model {
  id: string;
  provider: string;
  family?: string;
  version?: string;
  status: "active" | "deprecated" | "retired";
  is_custom: boolean;
  capabilities: Record<string, unknown>;
  characteristics: Record<string, unknown>;
  pricing: { input_per_1m_tokens: number; output_per_1m_tokens: number };
  api_config?: Record<string, unknown>;
}

export interface ComparisonTask {
  id: string;
  name: string;
  model_ids: string[];
  dataset_id: string;
  metrics: string[];
  status: "pending" | "running" | "completed" | "failed";
  error_message?: string;
  created_at: string;
  completed_at?: string;
}

export interface ComparisonResult {
  id: string;
  task_id: string;
  model_id: string;
  metrics: Record<string, number>;
  raw_outputs: any[];
  cost_usd: number;
  created_at: string;
}

export interface AIOpsEvent {
  id: string;
  agent_id?: string;
  model_id?: string;
  event_type: string;
  severity: "low" | "medium" | "high" | "critical";
  description?: string;
  status: "open" | "diagnosing" | "pending_approval" | "executing" | "resolved";
  actions: Array<Record<string, unknown>>;
  created_at: string;
}

export interface OpsMetric {
  time: string;
  agent_id: string;
  model_id: string;
  metric_name: string;
  value: number;
}

export interface Rule {
  id: string;
  name: string;
  enabled: boolean;
  condition: Record<string, unknown>;
  action: { type: string; params: Record<string, unknown> };
  requires_approval: boolean;
}

// ── API 함수 ───────────────────────────────────────────────────────────────────

// Agents
export const agentsApi = {
  list: () => request<{ data: Agent[]; meta: { count: number } }>("/agents"),
  get:  (id: string) => request<{ data: Agent }>(`/agents/${id}`),
  create: (body: Partial<Agent>) =>
    request<{ data: Agent }>("/agents", { method: "POST", body: JSON.stringify(body) }),
};

// Models
export const modelsApi = {
  list: () => request<{ data: Model[] }>("/models"),
  get:  (id: string) => request<{ data: Model }>(`/models/${encodeURIComponent(id)}`),
  create: (body: Partial<Model>) =>
    request<{ data: Model }>("/models", { method: "POST", body: JSON.stringify(body) }),
  patchStatus: (id: string, status: string) =>
    request<{ data: Model }>(`/models/${encodeURIComponent(id)}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  compare: (ids: string[]) =>
    request<{ data: Record<string, Model> }>(`/models/compare?model_ids=${ids.join(",")}`),
  delete: (id: string) =>
    request<void>(`/models/${encodeURIComponent(id)}`, { method: "DELETE" }),
  testConnection: (body: any) =>
    request<{ status: "success" | "error"; message: string }>("/models/test-connection", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

// Comparison Tasks
export const tasksApi = {
  list: () => request<{ data: ComparisonTask[]; meta: { count: number } }>("/tasks"),
  get:  (id: string) => request<{ data: ComparisonTask }>(`/tasks/${id}`),
  create: (body: Partial<ComparisonTask>) =>
    request<{ data: ComparisonTask }>("/tasks", { method: "POST", body: JSON.stringify(body) }),
  run: (id: string) =>
    request<{ data: { task_id: string; status: string } }>(`/tasks/${id}/run`, { method: "POST" }),
  delete: (id: string) =>
    request<void>(`/tasks/${id}`, { method: "DELETE" }),
  report: (id: string) =>
    request<{ data: { task_id: string; dataset_cases: any[]; results: ComparisonResult[] } }>(`/tasks/${id}/report`),
  recommendation: (id: string, priority: "cost" | "performance" | "balanced" = "balanced") =>
    request<{ data: { recommended_model: string; scores: Record<string, number>; rationale: string } }>(
      `/tasks/${id}/recommendation?priority=${priority}`
    ),
};

// Datasets
export const datasetsApi = {
  list: () => request<{ data: any[] }>("/datasets"),
  get: (id: string) => request<{ data: any }> (`/datasets/${id}`),
  create: (body: { id: string; cases: any[] }) =>
    request<{ data: { id: string } }>("/datasets", { method: "POST", body: JSON.stringify(body) }),
  delete: (id: string) => request<void>(`/datasets/${id}`, { method: "DELETE" }),
};

// AIOps Events
export const eventsApi = {
  list: (params?: { agent_id?: string; status?: string; severity?: string; limit?: number }) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params ?? {}).filter(([, v]) => v != null).map(([k, v]) => [k, String(v)]))
    ).toString();
    return request<{ data: AIOpsEvent[]; meta: { count: number } }>(`/events${qs ? `?${qs}` : ""}`);
  },
  get:      (id: string) => request<{ data: AIOpsEvent }>(`/events/${id}`),
  diagnose: (id: string) => request<{ data: unknown }>(`/events/${id}/diagnose`, { method: "POST" }),
  approve:  (id: string, body: { action_index: number; approved: boolean; note?: string }) =>
    request<{ data: AIOpsEvent }>(`/events/${id}/approve`, { method: "PATCH", body: JSON.stringify(body) }),
  resolve:  (id: string) =>
    request<{ data: AIOpsEvent }>(`/events/${id}/resolve`, { method: "PATCH" }),
};

// AIOps Metrics
export const metricsApi = {
  query: (agentId: string, params?: { metric?: string; limit?: number }) => {
    const qs = new URLSearchParams({ ...(params ?? {}) } as Record<string, string>).toString();
    return request<{ data: OpsMetric[] }>(`/metrics/${agentId}${qs ? `?${qs}` : ""}`);
  },
  ingest: (rows: Partial<OpsMetric>[]) =>
    request<{ data: { ingested: number } }>("/metrics", { method: "POST", body: JSON.stringify(rows) }),
};

// Rules
export const rulesApi = {
  list:   () => request<{ data: Rule[] }>("/rules"),
  create: (body: Partial<Rule>) =>
    request<{ data: Rule }>("/rules", { method: "POST", body: JSON.stringify(body) }),
  update: (id: string, body: Partial<Rule>) =>
    request<{ data: Rule }>(`/rules/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  delete: (id: string) =>
    request<{ data: { deleted: boolean } }>(`/rules/${id}`, { method: "DELETE" }),
};

// Health
export const healthApi = {
  upstream: () =>
    request<{ status: string; services: Record<string, { status: string }> }>("/health/upstream"),
};
