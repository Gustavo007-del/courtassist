import { apiRequest } from './api';
import type { Activity } from './activity-api';

export type DashboardOverview = {
  profile: { id: string; full_name: string; profile_image: string | null; professional_designation: string | null };
  today_date: string; timezone: string;
  summary: { today_hearings: number | null; tomorrow_hearings: number | null; active_cases: number | null; pending_tasks: number | null; overdue_tasks: number | null; upcoming_deadlines: number | null; tasks_due_today: number; high_priority_tasks: number; upcoming_appointments: number; recently_completed_tasks: number };
  module_availability: { cases: boolean; hearings: boolean; tasks: boolean; appointments: boolean; deadlines: boolean; payments: boolean };
  today_schedule: { id: string; hearing_time: string | null; case_title: string; case_number: string; court_name: string; hearing_purpose: string | null }[];
  today_activities: Activity[];
  upcoming_activities: { id: string; activity_type: string; title: string; scheduled_at: string | null; hearing_date: string | null; entity_type: string | null; entity_id: string | null }[];
  recent_activities: Activity[];
  hearing_summary: { this_week: number; recently_completed: number; potential_conflicts_today: number };
};
export const dashboardApi = { overview: () => apiRequest<DashboardOverview>('/dashboard/overview') };
