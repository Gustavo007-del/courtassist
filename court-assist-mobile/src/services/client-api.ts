import { apiRequest } from './api';

export type Client = { id: string; client_type: 'individual' | 'organization'; full_name: string; organization_name: string | null; phone_number: string; alternate_phone: string | null; email: string | null; address: string; city: string; district: string; state: string; postal_code: string; occupation: string | null; notes: string | null; created_at: string; updated_at: string; is_archived: boolean; associated_case_count: number };
export type ClientInput = Omit<Client, 'id' | 'created_at' | 'updated_at' | 'is_archived' | 'associated_case_count'>;
export type ClientPage = { items: Client[]; total: number; limit: number; offset: number };
export type ClientNote = { id: string; client_id: string; title: string; content: string; created_at: string; updated_at: string };
export type Interaction = { id: string; client_id: string; interaction_type: 'consultation' | 'phone_call' | 'meeting' | 'email' | 'other'; interaction_date: string; subject: string; description: string; follow_up_required: boolean; follow_up_date: string | null; created_at: string; updated_at: string };
const query = (data: Record<string, string | number | boolean | undefined>) => new URLSearchParams(Object.entries(data).filter(([, v]) => v !== undefined && v !== '').map(([k, v]) => [k, String(v)])).toString();
export const clientApi = {
  list: (params: Record<string, string | number | boolean | undefined>) => apiRequest<ClientPage>(`/clients?${query(params)}`),
  get: (id: string, includeArchived = false) => apiRequest<Client>(`/clients/${id}?include_archived=${includeArchived}`),
  create: (data: ClientInput) => apiRequest<Client>('/clients', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<ClientInput>) => apiRequest<Client>(`/clients/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  archive: (id: string) => apiRequest<Client>(`/clients/${id}/archive`, { method: 'POST' }),
  restore: (id: string) => apiRequest<Client>(`/clients/${id}/restore`, { method: 'POST' }),
  remove: (id: string) => apiRequest<void>(`/clients/${id}`, { method: 'DELETE' }),
  notes: (id: string, q = '') => apiRequest<ClientNote[]>(`/clients/${id}/notes?${query({ q })}`),
  addNote: (id: string, data: { title: string; content: string }) => apiRequest<ClientNote>(`/clients/${id}/notes`, { method: 'POST', body: JSON.stringify(data) }),
  updateNote: (id: string, noteId: string, data: { title?: string; content?: string }) => apiRequest<ClientNote>(`/clients/${id}/notes/${noteId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteNote: (id: string, noteId: string) => apiRequest<void>(`/clients/${id}/notes/${noteId}`, { method: 'DELETE' }),
  interactions: (id: string) => apiRequest<Interaction[]>(`/clients/${id}/interactions`),
  addInteraction: (id: string, data: Omit<Interaction, 'id' | 'client_id' | 'created_at' | 'updated_at'>) => apiRequest<Interaction>(`/clients/${id}/interactions`, { method: 'POST', body: JSON.stringify(data) }),
  updateInteraction: (id: string, interactionId: string, data: Partial<Interaction>) => apiRequest<Interaction>(`/clients/${id}/interactions/${interactionId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteInteraction: (id: string, interactionId: string) => apiRequest<void>(`/clients/${id}/interactions/${interactionId}`, { method: 'DELETE' }),
};
