import { apiRequest } from './api';
export type DraftRecord = {
  id: string;
  title: string;
  content: string;
  category: string;
  language: string;
  status: string;
  updated_at: string;
  case_id: string | null;
  client_id: string | null;
  template_id: string | null;
  archived_at: string | null;
};
export type LibraryKind = 'draft-templates' | 'draft-clauses';
export type LibraryRecord = {
  id: string;
  title?: string;
  name?: string;
  description?: string;
  category: string;
  content: string;
  built_in?: boolean;
  user_id: string | null;
};
export type DraftVersion = {
  id: string;
  version_number: number;
  content: string;
  description: string;
  created_at: string;
};
export const draftingApi = {
  list: (params: Record<string, string>) =>
    apiRequest<DraftRecord[]>(`/draft-documents?${new URLSearchParams(params).toString()}`),
  get: (id: string) => apiRequest<DraftRecord>(`/draft-documents/${id}`),
  create: (body: unknown) =>
    apiRequest<DraftRecord>('/draft-documents', { method: 'POST', body: JSON.stringify(body) }),
  save: (id: string, body: unknown) =>
    apiRequest<DraftRecord>(`/draft-documents/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  library: (kind: LibraryKind, q = '', offset = 0, category = '') =>
    apiRequest<LibraryRecord[]>(
      `/${kind}?q=${encodeURIComponent(q)}&offset=${offset}&limit=30&category=${encodeURIComponent(category)}`,
    ),
  libraryGet: (kind: LibraryKind, id: string) => apiRequest<LibraryRecord>(`/${kind}/${id}`),
  librarySave: (kind: LibraryKind, id: string | undefined, body: unknown) =>
    apiRequest<LibraryRecord>(`/${kind}${id ? `/${id}` : ''}`, {
      method: id ? 'PATCH' : 'POST',
      body: JSON.stringify(body),
    }),
  versions: (id: string) => apiRequest<DraftVersion[]>(`/draft-documents/${id}/versions`),
  action: (id: string, action: string, body?: unknown) =>
    apiRequest(`/draft-documents/${id}/${action}`, {
      method: 'POST',
      ...(body ? { body: JSON.stringify(body) } : {}),
    }),
};
