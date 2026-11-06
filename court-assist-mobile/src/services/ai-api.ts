import { apiRequest, ApiError } from './api';

export const sourceKinds = ['case', 'document', 'diary', 'hearing', 'timeline', 'status', 'research', 'task'] as const;
export type SourceKind = typeof sourceKinds[number];
export type Source = { kind: SourceKind; id: string; first_page?: number; last_page?: number };
export type ContextRow = Source & { title: string; date?: string | null };
export type Language = 'source' | 'en' | 'ml';
export type Preferences = {
  enabled: boolean; documents: boolean; assistant: boolean; external: boolean; retention_days: number;
  available: boolean; provider: string | null; model: string | null; embeddings_available: boolean;
  external_provider: boolean; provider_policy: string | null; external_confirmation: string | null;
};
export type JobKind = 'ask' | 'summarize' | 'dates' | 'metadata' | 'chronology' | 'draft' | 'diary';
export type Status = 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
export type Evidence = {
  section: string; quote: string; date: string | null; date_status: 'explicit' | 'inferred' | 'missing';
  check_other_dates?: boolean;
  source: { kind: SourceKind; id: string; title: string; page: number | null; paragraph: string | null; version: string | null; reference: string | null };
};
export type Job = {
  id: string; kind: JobKind; status: Status; provider: string; model: string; attempts: number;
  error_code: string | null; case_id: string | null; document_id: string | null; draft_id: string | null;
  conversation_id: string | null; created_at: string; expires_at: string;
  input_tokens: number | null; output_tokens: number | null; estimated_cost: number | null;
  result?: { suggestion?: string; items?: Evidence[]; missing_sections?: string[]; warnings?: string[]; insufficient?: boolean };
  question?: string; selected_text?: string; draft_revision?: string; can_retry?: boolean;
  review?: { text: string; reviewed_at: string };
  approval?: Record<string, unknown>;
};
type Page<T> = { items: T[]; total: number };
type Request = { request_id: string; language?: Language; external_confirmation?: string | null };
type Ask = Request & { question: string; sources: Source[]; case_id?: string; previous_job_id?: string };
type Write = Request & { text: string; action?: string; case_id?: string; entry_id?: string };

function send<T>(path: string, data?: unknown, method = 'POST') {
  return apiRequest<T>('/ai' + path, { method, ...(data === undefined ? {} : { body: JSON.stringify(data) }) });
}

export const aiApi = {
  preferences: () => apiRequest<Preferences>('/ai/preferences'),
  savePreferences: (data: Partial<Preferences>) => send<Preferences>('/preferences', data, 'PATCH'),
  context: (kind: SourceKind, offset: number, caseId?: string) =>
    apiRequest<Page<ContextRow>>(`/ai/context?kind=${kind}&offset=${offset}&limit=20${caseId ? '&case_id=' + encodeURIComponent(caseId) : ''}`),
  ask: (data: Ask, conversation?: string) => send<Job>(conversation ? `/conversations/${conversation}/messages` : '/ask', data),
  document: (id: string, operation: string, data: Request & { first_page?: number; last_page?: number }) =>
    send<Job>(`/documents/${id}/${operation}`, data),
  documentJobs: (id: string, offset: number) => apiRequest<Page<Job>>(`/ai/documents/${id}/results?offset=${offset}&limit=20`),
  chronology: (id: string, data: Request & { sources: Source[] }) => send<Job>(`/cases/${id}/chronology`, data),
  draft: (id: string, operation: string, data: Write) => send<Job>(`/drafts/${id}/${operation}`, data),
  diary: (data: Write) => send<Job>('/diary/organize', data),
  jobs: (offset: number) => apiRequest<Page<Job>>(`/ai/jobs?offset=${offset}&limit=20`),
  job: (id: string) => apiRequest<Job>(`/ai/jobs/${id}`),
  cancel: (id: string) => send<Job>(`/jobs/${id}/cancel`),
  retry: (id: string, data: Request) => send<Job>(`/jobs/${id}/retry`, data),
  remove: (id: string) => send<void>(`/jobs/${id}`, undefined, 'DELETE'),
  review: (id: string, text: string) => send<Job>(`/jobs/${id}/review`, { text }, 'PATCH'),
  export: (id: string) => apiRequest<string>(`/ai/jobs/${id}/export`),
  approveDraft: (id: string, text: string, expected_updated_at: string, mode: 'append' | 'replace') =>
    send<{ draft_id: string }>(`/jobs/${id}/approve-draft`, { text, expected_updated_at, mode }),
  approveDiary: (id: string, data: { text: string; title: string; case_id: string; entry_date: string; item_index?: number }) =>
    send<{ diary_entry_id: string }>(`/jobs/${id}/approve-diary`, data),
  conversations: (offset: number) => apiRequest<{ items: { id: string; created_at: string }[] }>(`/ai/conversations?offset=${offset}&limit=20`),
  conversation: (id: string, offset: number) => apiRequest<Page<Job>>(`/ai/conversations/${id}?offset=${offset}&limit=20`),
  removeConversation: (id: string) => send<void>(`/conversations/${id}`, undefined, 'DELETE'),
  usage: (offset: number) => apiRequest<Page<Job>>(`/ai/usage?offset=${offset}&limit=20`),
  usageSummary: () => apiRequest<{ requests: number; daily_limit: number; input_tokens: number | null; output_tokens: number | null; estimated_cost: number | null }>('/ai/usage/summary'),
};

export function aiErrorKey(error: unknown) {
  return error instanceof ApiError && /^[a-z_]+$/.test(error.message) ? `ai.errors.${error.message}` : 'work.error';
}

export const isWorking = (job: Job) => job.status === 'pending' || job.status === 'processing';

