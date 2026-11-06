import { apiRequest } from './api';

export type CaseStatus = 'Pending' | 'Active' | 'In Progress' | 'Stayed' | 'Disposed' | 'Dismissed' | 'Withdrawn' | 'Settled' | 'Transferred' | 'Archived';
export type CasePriority = 'Normal' | 'High' | 'Urgent';
export type CaseRecord = { id: string; client_id: string | null; court_id: string | null; case_title: string; case_number: string; cnr_number: string | null; case_type: string | null; case_category: string; filing_number: string | null; filing_date: string; registration_date: string | null; current_status: CaseStatus; case_stage: string | null; description: string; jurisdiction: string | null; judge_name: string | null; courtroom: string | null; priority: CasePriority; is_confidential: boolean; is_archived: boolean; disposed_at: string | null; created_at: string; updated_at: string; court_name: string | null; court_district: string | null; primary_client_name: string | null };
export type CaseInput = Pick<CaseRecord, 'client_id' | 'court_id' | 'case_title' | 'case_number' | 'cnr_number' | 'case_type' | 'case_category' | 'filing_number' | 'filing_date' | 'registration_date' | 'case_stage' | 'description' | 'jurisdiction' | 'judge_name' | 'courtroom' | 'priority' | 'is_confidential'>;
export type CasePartyInput = { client_id: string | null; party_name: string; party_type: 'individual' | 'organization'; party_role: string; address: string; phone_number: string | null; email: string | null; description: string | null };
export type CaseParty = CasePartyInput & { id: string; case_id: string; created_at: string; updated_at: string };
export type CaseAdvocateInput = { advocate_name: string; bar_registration_number: string | null; representation_role: string; is_primary: boolean };
export type CaseAdvocate = CaseAdvocateInput & { id: string; case_id: string; created_at: string; updated_at: string };
export type CaseEvent = { id: string; case_id: string; activity_type: string; title: string; description: string | null; details: Record<string, unknown>; created_at: string };
export type CaseStatusEvent = { id: string; case_id: string; previous_status: CaseStatus; new_status: CaseStatus; reason: string | null; effective_date: string; created_at: string };
export type Page<T> = { items: T[]; total: number; limit: number; offset: number };
const query = (data: Record<string, string | number | boolean | undefined | null>) => new URLSearchParams(Object.entries(data).filter(([, value]) => value !== undefined && value !== null && value !== '').map(([key, value]) => [key, String(value)])).toString();
const root = '/cases';
export const caseApi = {
  list: (filters: Record<string, string | number | boolean | undefined | null>) => apiRequest<Page<CaseRecord>>(`${root}?${query(filters)}`),
  get: (id: string, archived = false) => apiRequest<CaseRecord>(`${root}/${id}?include_archived=${archived}`),
  create: (data: CaseInput & { initial_status: CaseStatus; parties: CasePartyInput[]; advocates: CaseAdvocateInput[] }) => apiRequest<CaseRecord>(root, { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<CaseInput>, offlineBase?: string) => apiRequest<CaseRecord>(`${root}/${id}`, { method: 'PATCH', offlineBase, body: JSON.stringify(data) }),
  archive: (id: string) => apiRequest<CaseRecord>(`${root}/${id}/archive`, { method: 'POST' }), restore: (id: string) => apiRequest<CaseRecord>(`${root}/${id}/restore`, { method: 'POST' }),
  parties: (id: string) => apiRequest<CaseParty[]>(`${root}/${id}/parties`),
  addParty: (id: string, data: CasePartyInput) => apiRequest<CaseParty>(`${root}/${id}/parties`, { method: 'POST', body: JSON.stringify(data) }),
  updateParty: (id: string, partyId: string, data: CasePartyInput) => apiRequest<CaseParty>(`${root}/${id}/parties/${partyId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  removeParty: (id: string, partyId: string) => apiRequest<void>(`${root}/${id}/parties/${partyId}`, { method: 'DELETE' }),
  advocates: (id: string) => apiRequest<CaseAdvocate[]>(`${root}/${id}/advocates`),
  addAdvocate: (id: string, data: CaseAdvocateInput) => apiRequest<CaseAdvocate>(`${root}/${id}/advocates`, { method: 'POST', body: JSON.stringify(data) }),
  updateAdvocate: (id: string, advocateId: string, data: CaseAdvocateInput) => apiRequest<CaseAdvocate>(`${root}/${id}/advocates/${advocateId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  removeAdvocate: (id: string, advocateId: string) => apiRequest<void>(`${root}/${id}/advocates/${advocateId}`, { method: 'DELETE' }),
  history: (id: string) => apiRequest<CaseStatusEvent[]>(`${root}/${id}/status-history`),
  status: (id: string, data: { new_status: CaseStatus; reason: string | null; effective_date: string }) => apiRequest<CaseStatusEvent>(`${root}/${id}/status`, { method: 'POST', body: JSON.stringify(data) }),
  activities: (id: string, offset = 0) => apiRequest<Page<CaseEvent>>(`${root}/${id}/activities?${query({ limit: 30, offset })}`),
  timeline: (id: string, order: 'newest' | 'oldest', offset = 0, category = '', fromDate = '', toDate = '') => apiRequest<Page<CaseEvent>>(`${root}/${id}/timeline?${query({ order, category, from_date: fromDate, to_date: toDate, limit: 30, offset })}`),
};
