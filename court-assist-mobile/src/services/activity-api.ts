import { apiRequest } from './api';

export type Activity = { id: string; activity_type: string; title: string; description: string | null; entity_type: string | null; entity_id: string | null; details: Record<string, unknown>; created_at: string };
export type ActivityPage = { items: Activity[]; total: number; limit: number; offset: number };
export const activityApi = {
  list: (query: { limit?: number; offset?: number; activity_type?: string; from_date?: string; to_date?: string } = {}) => apiRequest<ActivityPage>(`/activities?${new URLSearchParams(Object.entries(query).filter(([, value]) => value !== undefined).map(([key, value]) => [key, String(value)])).toString()}`),
};
