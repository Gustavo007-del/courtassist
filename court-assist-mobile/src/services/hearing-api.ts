import { apiRequest } from './api';
export type HearingStatus = 'Scheduled' | 'Completed' | 'Adjourned' | 'Cancelled' | 'Postponed' | 'Awaiting Order';
export type Hearing = { id: string; case_id: string; court_id: string | null; hearing_date: string; hearing_time: string | null; estimated_end_time: string | null; hearing_type: string; hearing_stage: string | null; courtroom: string | null; judge_name: string | null; purpose: string; proceedings_notes: string | null; judge_directions: string | null; adjournment_reason: string | null; outcome: string | null; next_hearing_date: string | null; next_hearing_time: string | null; status: HearingStatus; reminder_enabled: boolean; follow_up_hearing_id: string | null; created_at: string; updated_at: string; case_title: string; case_number: string; case_category: string; court_name: string | null; court_district: string | null };
export type HearingInput = Pick<Hearing, 'case_id' | 'court_id' | 'hearing_date' | 'hearing_time' | 'estimated_end_time' | 'hearing_type' | 'hearing_stage' | 'courtroom' | 'judge_name' | 'purpose' | 'reminder_enabled'>;
export type Reminder = { id: string; hearing_id: string; reminder_type: 'day_of' | 'one_day' | 'three_days' | 'one_week' | 'custom'; scheduled_at: string; delivery_channel: string; status: string; sent_at: string | null; attempt_count: number; created_at: string; updated_at: string };
export type Conflict = { hearing_id: string; case_title: string; kind: 'confirmed' | 'estimated' | 'unknown_time'; reason: string };
export type Page<T> = { items: T[]; total: number; limit: number; offset: number };
const query = (data: Record<string, string | number | boolean | undefined | null>) => new URLSearchParams(Object.entries(data).filter(([, value]) => value !== null && value !== undefined && value !== '').map(([key, value]) => [key, String(value)])).toString();
export const hearingApi = {
  list: (filters: Record<string, string | number | boolean | undefined | null>) => apiRequest<Page<Hearing>>(`/hearings?${query(filters)}`),
  get: (id: string) => apiRequest<Hearing>(`/hearings/${id}`), create: (data: HearingInput) => apiRequest<Hearing>('/hearings', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<HearingInput> & { proceedings_notes?: string | null; judge_directions?: string | null; outcome?: string | null; adjournment_reason?: string | null }) => apiRequest<Hearing>(`/hearings/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  cancel: (id: string) => apiRequest<void>(`/hearings/${id}`, { method: 'DELETE' }),
  complete: (id: string, data: { proceedings_notes: string | null; judge_directions: string | null; adjournment_reason: string | null; outcome: string | null; next_hearing_date: string | null; next_hearing_time: string | null }) => apiRequest<Hearing>(`/hearings/${id}/complete`, { method: 'POST', body: JSON.stringify(data) }),
  adjourn: (id: string, data: { proceedings_notes: string | null; judge_directions: string | null; adjournment_reason: string | null; outcome: string | null; next_hearing_date: string | null; next_hearing_time: string | null }) => apiRequest<Hearing>(`/hearings/${id}/adjourn`, { method: 'POST', body: JSON.stringify(data) }),
  reschedule: (id: string, data: { hearing_date: string; hearing_time: string | null; estimated_end_time: string | null; reason: string | null }) => apiRequest<Hearing>(`/hearings/${id}/reschedule`, { method: 'POST', body: JSON.stringify(data) }),
  caseHistory: (id: string, status = '') => apiRequest<Page<Hearing>>(`/cases/${id}/hearings/history?${query({ status })}`),
  calendar: (from: string, to: string, filters: Record<string, string | undefined> = {}) => apiRequest<Page<Hearing>>(`/calendar/hearings?${query({ from_date: from, to_date: to, ...filters, limit: 100 })}`),
  day: (day: string) => apiRequest<Page<Hearing>>(`/calendar/day?${query({ day })}`),
  conflicts: (data: HearingInput) => apiRequest<Conflict[]>('/hearings/check-conflicts', { method: 'POST', body: JSON.stringify(data) }),
  dayConflicts: (day: string) => apiRequest<Conflict[]>(`/calendar/day/conflicts?${query({ day })}`),
  reminders: (id: string) => apiRequest<Reminder[]>(`/hearings/${id}/reminders`),
  addReminder: (id: string, data: { reminder_type: Reminder['reminder_type']; scheduled_at?: string | null; delivery_channel?: 'local' | 'push' }) => apiRequest<Reminder>(`/hearings/${id}/reminders`, { method: 'POST', body: JSON.stringify(data) }),
  updateReminder: (id: string, reminderId: string, data: { scheduled_at?: string; status?: 'pending' | 'scheduled_local' | 'cancelled' }) => apiRequest<Reminder>(`/hearings/${id}/reminders/${reminderId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  removeReminder: (id: string, reminderId: string) => apiRequest<void>(`/hearings/${id}/reminders/${reminderId}`, { method: 'DELETE' }),
};
