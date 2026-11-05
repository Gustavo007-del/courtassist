import { apiRequest } from './api';
export type Court = { id: string; name: string; court_type: string; state: string; district: string; address: string; phone_number: string | null; email: string | null; official_website: string | null; jurisdiction: string | null; notes: string | null; source: string | null; is_active: boolean; record_scope: 'shared' | 'private'; is_favorite: boolean; can_edit: boolean; created_at: string; updated_at: string };
export type CourtInput = Pick<Court, 'name' | 'court_type' | 'state' | 'district' | 'address' | 'phone_number' | 'email' | 'official_website' | 'jurisdiction' | 'notes'>;
export type CourtPage = { items: Court[]; total: number; limit: number; offset: number };
const query = (data: Record<string, string | number | undefined>) => new URLSearchParams(Object.entries(data).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => [k, String(v)])).toString();
export const courtApi = {
  list: (params: Record<string, string | number | undefined>) => apiRequest<CourtPage>(`/courts?${query(params)}`),
  favorites: () => apiRequest<CourtPage>('/courts/favorites'), get: (id: string) => apiRequest<Court>(`/courts/${id}`),
  create: (data: CourtInput) => apiRequest<Court>('/courts', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<CourtInput>) => apiRequest<Court>(`/courts/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  remove: (id: string) => apiRequest<void>(`/courts/${id}`, { method: 'DELETE' }),
  favorite: (id: string) => apiRequest<{ detail: string }>(`/courts/${id}/favorite`, { method: 'POST' }),
  unfavorite: (id: string) => apiRequest<void>(`/courts/${id}/favorite`, { method: 'DELETE' }),
};
