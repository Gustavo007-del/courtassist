import { apiRequest } from './api';

export type DiaryEntry = {
  id: string; user_id?: string; case_id: string; hearing_id: string | null; entry_date: string;
  entry_type: string; title: string; content: string; proceedings_summary: string | null;
  judge_directions: string | null; arguments_summary: string | null; evidence_notes: string | null;
  witness_notes: string | null; observations: string | null; next_action: string | null;
  follow_up_date: string | null; is_important: boolean; is_pinned: boolean; created_at: string;
  updated_at: string; case_title: string; case_number: string; hearing_date: string | null;
};
export type DiaryInput = Pick<DiaryEntry, 'case_id' | 'hearing_id' | 'entry_date' | 'entry_type' | 'title' | 'content' | 'proceedings_summary' | 'judge_directions' | 'arguments_summary' | 'evidence_notes' | 'witness_notes' | 'observations' | 'next_action' | 'follow_up_date' | 'is_important' | 'is_pinned'> & { request_id?: string };
export type Page<T> = { items: T[]; total: number; limit: number; offset: number };
const query = (data: Record<string, string | number | boolean | null | undefined>) => new URLSearchParams(Object.entries(data).filter(([, value]) => value !== null && value !== undefined && value !== '').map(([key, value]) => [key, String(value)])).toString();
export const diaryApi = {
  list: (filters: Record<string, string | number | boolean | null | undefined>) => apiRequest<Page<DiaryEntry>>(`/diary?${query(filters)}`),
  caseList: (id: string, limit = 20) => apiRequest<Page<DiaryEntry>>(`/cases/${id}/diary?${query({ limit })}`),
  hearingList: (id: string) => apiRequest<Page<DiaryEntry>>(`/hearings/${id}/diary`),
  get: (id: string) => apiRequest<DiaryEntry>(`/diary/${id}`),
  create: (data: DiaryInput) => apiRequest<DiaryEntry>('/diary', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<DiaryInput>, offlineBase?: string) => apiRequest<DiaryEntry>(`/diary/${id}`, { method: 'PATCH', offlineBase, body: JSON.stringify(data) }),
  remove: (id: string) => apiRequest<void>(`/diary/${id}`, { method: 'DELETE' }),
  pin: (id: string, value: boolean) => apiRequest<DiaryEntry>(`/diary/${id}/pin`, { method: value ? 'POST' : 'DELETE' }),
  important: (id: string, value: boolean) => apiRequest<DiaryEntry>(`/diary/${id}/important`, { method: value ? 'POST' : 'DELETE' }),
};
