import { apiRequest } from './api';

export type TaskStatus = 'Pending' | 'In Progress' | 'Completed' | 'Cancelled';
export type TaskPriority = 'Low' | 'Medium' | 'High' | 'Urgent';
export type Task = { id: string; user_id: string; title: string; description: string; category: string; priority: TaskPriority; status: TaskStatus; start_date: string | null; due_date: string | null; due_time: string | null; completed_at: string | null; case_id: string | null; client_id: string | null; hearing_id: string | null; document_id: string | null; recurrence_kind: string; recurrence_interval: number; recurrence_root_id: string | null; occurrence_date: string | null; reminder_minutes: number | null; follow_up_notes: string; is_overdue: boolean; archived_at: string | null; created_at: string; updated_at: string };
export type TaskInput = Pick<Task, 'title' | 'description' | 'category' | 'priority' | 'status' | 'start_date' | 'due_date' | 'due_time' | 'case_id' | 'client_id' | 'hearing_id' | 'document_id' | 'recurrence_kind' | 'recurrence_interval' | 'reminder_minutes' | 'follow_up_notes'>;
export type Appointment = { id: string; user_id: string; title: string; description: string; appointment_type: string; appointment_date: string; start_time: string; end_time: string; location: string; meeting_mode: string; client_id: string | null; case_id: string | null; attendee_details: string; reminder_minutes: number | null; status: 'Scheduled' | 'Completed' | 'Cancelled' | 'No-show'; private_notes: string; archived_at: string | null; created_at: string; updated_at: string };
export type AppointmentInput = Pick<Appointment, 'title' | 'description' | 'appointment_type' | 'appointment_date' | 'start_time' | 'end_time' | 'location' | 'meeting_mode' | 'client_id' | 'case_id' | 'attendee_details' | 'reminder_minutes' | 'status' | 'private_notes'>;
export type PlanningReminder = { id: string; task_id: string | null; appointment_id: string | null; scheduled_at: string; status: string };
export type AgendaItem = { kind: 'hearing' | 'task' | 'appointment'; id: string; date: string; time: string | null; title: string; status?: string };
export type Page<T> = { items: T[]; total: number; limit: number; offset: number };
const query = (data: Record<string, string | number | boolean | null | undefined>) => new URLSearchParams(Object.entries(data).filter(([, value]) => value !== null && value !== undefined && value !== '').map(([key, value]) => [key, String(value)])).toString();
export const taskApi = {
  list: (filters: Record<string, string | number | boolean | null | undefined> = {}) => apiRequest<Page<Task>>(`/tasks?${query(filters)}`),
  get: (id: string) => apiRequest<Task>(`/tasks/${id}`),
  create: (data: TaskInput) => apiRequest<Task>('/tasks', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<TaskInput>, offlineBase?: string) => apiRequest<Task>(`/tasks/${id}`, { method: 'PATCH', offlineBase, body: JSON.stringify(data) }),
  archive: (id: string) => apiRequest<void>(`/tasks/${id}`, { method: 'DELETE' }),
  complete: (id: string) => apiRequest<Task>(`/tasks/${id}/complete`, { method: 'POST' }),
  reopen: (id: string) => apiRequest<Task>(`/tasks/${id}/reopen`, { method: 'POST' }),
  overdue: () => apiRequest<Page<Task>>('/tasks/overdue'),
  upcoming: () => apiRequest<Task[]>('/tasks/upcoming'),
  reminders: (id: string) => apiRequest<PlanningReminder[]>(`/tasks/${id}/reminders`),
};
export const appointmentApi = {
  list: (filters: Record<string, string | number | boolean | null | undefined> = {}) => apiRequest<Page<Appointment>>(`/appointments?${query(filters)}`),
  get: (id: string) => apiRequest<Appointment>(`/appointments/${id}`),
  create: (data: AppointmentInput) => apiRequest<Appointment>('/appointments', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<AppointmentInput>, offlineBase?: string) => apiRequest<Appointment>(`/appointments/${id}`, { method: 'PATCH', offlineBase, body: JSON.stringify(data) }),
  archive: (id: string) => apiRequest<void>(`/appointments/${id}`, { method: 'DELETE' }),
  cancel: (id: string) => apiRequest<Appointment>(`/appointments/${id}/cancel`, { method: 'POST' }),
  conflicts: (data: AppointmentInput, appointmentId?: string) => apiRequest<{ kind: string; id: string; title: string; estimated: boolean }[]>(`/appointments/check-conflicts${appointmentId ? `?appointment_id=${appointmentId}` : ''}`, { method: 'POST', body: JSON.stringify(data) }),
  upcoming: () => apiRequest<Appointment[]>('/appointments/upcoming'),
  calendar: (fromDate: string, toDate: string) => apiRequest<Appointment[]>(`/appointments/calendar?${query({ from_date: fromDate, to_date: toDate })}`),
  reminders: (id: string) => apiRequest<PlanningReminder[]>(`/appointments/${id}/reminders`),
};
export const planningCalendarApi = { agenda: (fromDate: string, toDate: string) => apiRequest<AgendaItem[]>(`/calendar/agenda?${query({ from_date: fromDate, to_date: toDate })}`) };
export const planningReminderApi = { upcoming: () => apiRequest<PlanningReminder[]>('/planning/reminders/upcoming') };
