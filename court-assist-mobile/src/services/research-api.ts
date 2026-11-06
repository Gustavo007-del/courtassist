import { apiRequest } from './api';
export const researchTypes = [
  'Judgment',
  'Court order',
  'Act',
  'Section',
  'Rule',
  'Regulation',
  'Legal article',
  'Citation',
  'Precedent',
  'Research note',
  'External reference',
  'Other',
];
export type ResearchFields = {
  title: string;
  item_type: string;
  court: string;
  case_number: string;
  cnr_number: string;
  citation: string;
  case_title: string;
  judgment_date: string | null;
  source_name: string;
  source_url: string;
  accessed_date: string | null;
  summary: string;
  full_text: string;
  language: string;
  act_name: string;
  section_number: string;
  party_information: string;
  subject: string;
  notes: string;
  verification_status: string;
  verification_notes: string;
  page_reference: string;
  paragraph_reference: string;
  case_id: string | null;
  client_id: string | null;
  document_id: string | null;
  favorite: boolean;
  tags: string[];
};
export type ResearchItem = ResearchFields & {
  id: string;
  source_status: string;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  linked_case_ids: string[];
};
export type ResearchTag = { id: string; name: string };
export type ResearchListItem = Omit<
  ResearchItem,
  'full_text' | 'notes' | 'party_information' | 'linked_case_ids'
>;
export type ResearchNote = {
  id: string;
  title: string;
  content: string;
  quoted_text: string;
  references: string;
  item_id: string | null;
  case_id: string | null;
  tags: string[];
  pinned: boolean;
  language: string;
  archived_at: string | null;
  updated_at: string;
};
export type Page<T> = { items: T[]; total: number; limit: number; offset: number };
export type ResearchNoteSummary = Omit<ResearchNote, 'content' | 'quoted_text' | 'references'>;
export type Suggestion = {
  field: string;
  value: string;
  source_text: string;
  page_number: number | null;
  confidence: number | null;
};
export type Extraction = {
  metadata_id?: string;
  processing_status: string;
  suggestions: Suggestion[];
  unavailable_fields: string[];
  reviewed?: unknown[];
  error_message?: string;
};
export type ImportBatch = {
  batch_id: string;
  status: string;
  rows: { row: number; data: Partial<ResearchFields>; duplicate: boolean }[];
  errors: { row: number; message: string }[];
  imported_ids: string[];
};
const qs = (params: Record<string, string>) =>
  new URLSearchParams(Object.entries(params).filter(([, value]) => value !== '')).toString();
export const researchApi = {
  list: (params: Record<string, string> = {}) =>
    apiRequest<Page<ResearchListItem>>(`/research-items?${qs(params)}`),
  get: (id: string) => apiRequest<ResearchItem>(`/research-items/${id}`),
  save: (id: string | undefined, body: unknown) =>
    apiRequest<ResearchItem>(`/research-items${id ? '/' + id : ''}`, {
      method: id ? 'PATCH' : 'POST',
      body: JSON.stringify(body),
    }),
  action: (id: string, action: string, body?: unknown) =>
    apiRequest<ResearchItem>(`/research-items/${id}/${action}`, {
      method: 'POST',
      ...(body ? { body: JSON.stringify(body) } : {}),
    }),
  tags: (q = '') => apiRequest<ResearchTag[]>(`/research-tags?q=${encodeURIComponent(q)}`),
  saveTag: (id: string | undefined, name: string) =>
    apiRequest<ResearchTag>(`/research-tags${id ? '/' + id : ''}`, {
      method: id ? 'PATCH' : 'POST',
      body: JSON.stringify({ name }),
    }),
  deleteTag: (id: string) => apiRequest(`/research-tags/${id}`, { method: 'DELETE' }),
  notes: (params: Record<string, string> = {}) =>
    apiRequest<Page<ResearchNoteSummary>>(`/research-notes?${qs(params)}`),
  note: (id: string) => apiRequest<ResearchNote>(`/research-notes/${id}`),
  saveNote: (id: string | undefined, body: unknown) =>
    apiRequest<ResearchNote>(`/research-notes${id ? '/' + id : ''}`, {
      method: id ? 'PATCH' : 'POST',
      body: JSON.stringify(body),
    }),
  archiveNote: (id: string) => apiRequest(`/research-notes/${id}`, { method: 'DELETE' }),
  restoreNote: (id: string) => apiRequest(`/research-notes/${id}/restore`, { method: 'POST' }),
  extraction: (id: string) => apiRequest<Extraction>(`/research-items/${id}/extraction-status`),
  extract: (id: string) =>
    apiRequest<Extraction>(`/research-items/${id}/extract-metadata`, { method: 'POST' }),
  confirmMetadata: (id: string, body: unknown) =>
    apiRequest(`/research-items/${id}/confirm-metadata`, { method: 'POST', body: JSON.stringify(body) }),
  import: (body: unknown) =>
    apiRequest<ImportBatch>('/research-items/import', { method: 'POST', body: JSON.stringify(body) }),
  caseItems: (id: string, offset = 0) =>
    apiRequest<Page<ResearchListItem>>(`/cases/${id}/research-items?offset=${offset}`),
  link: (caseId: string, itemId: string) =>
    apiRequest(`/cases/${caseId}/research-items`, {
      method: 'POST',
      body: JSON.stringify({ item_id: itemId }),
    }),
  unlink: (caseId: string, itemId: string) =>
    apiRequest(`/cases/${caseId}/research-items/${itemId}`, { method: 'DELETE' }),
};
