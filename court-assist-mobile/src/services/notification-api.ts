import { apiRequest } from './api';
export type NotificationItem = { id:string; category:string; title:string; message:string; entity_type:string|null; entity_id:string|null; scheduled_at:string; nominal_at:string; status:string; priority:string; read_at:string|null; cancelled_at:string|null; manual:boolean; purpose:string|null; summary:Record<string,string|number>|null; deliveries?:{id:string;channel:string;status:string;attempt_count:number;error_code:string|null}[] };
export type Device = { id:string; platform:string; label:string; last_seen_at:string; revoked_at:string|null; push_registered:boolean };
export type NotificationPreferences = {
 push_notifications:boolean;local_notifications:boolean;email_notifications:boolean;hearing_reminders:boolean;task_reminders:boolean;appointment_reminders:boolean;payment_reminders:boolean;document_reminders:boolean;draft_reminders:boolean;daily_summary:boolean;hearing_auto_reminders:boolean;hearing_reminder_days:number[];reminder_time:string;daily_summary_time:string;quiet_start:string|null;quiet_end:string|null;urgent_quiet_override:boolean;task_due_today:boolean;task_overdue_alerts:boolean;task_high_priority:boolean;overdue_repeat_days:number|null;payment_due_days:number;finance_auto_reminders:boolean;timezone:string;
};
export type PreferenceResponse={preferences:NotificationPreferences;capabilities:{push_configured:boolean;email_configured:boolean;email_verified:boolean;whatsapp_supported:boolean}};
export type LocalPlan={id:string;title:string;message:string;scheduled_at:string};
const post=<T>(path:string,data:unknown={})=>apiRequest<T>(path,{method:'POST',body:JSON.stringify(data)});
export const notificationApi={
 list:(filters:Record<string,string>)=>apiRequest<{items:NotificationItem[];total:number}>('/notifications?'+new URLSearchParams(filters)),
 get:(id:string)=>apiRequest<NotificationItem>(`/notifications/${id}`),
 read:(id:string)=>post<NotificationItem>(`/notifications/${id}/read`),
 dismiss:(id:string)=>post<NotificationItem>(`/notifications/${id}/dismiss`),
 readAll:()=>post('/notifications/read-all'),
 unread:()=>apiRequest<{count:number}>('/notifications/unread-count'),
 preferences:()=>apiRequest<PreferenceResponse>('/notification-preferences'),
 updatePreferences:(data:Partial<NotificationPreferences>)=>apiRequest<PreferenceResponse>('/notification-preferences',{method:'PATCH',body:JSON.stringify(data)}),
 devices:()=>apiRequest<Device[]>('/notifications/devices'),
 revoke:(id:string)=>apiRequest(`/notifications/devices/${id}`,{method:'DELETE'}),
 register:(data:{installation_id:string;platform:'android'|'ios';label:string;token:string|null;reactivate?:boolean})=>post<Device>('/notifications/register-device',data),
 localPlan:(id:string,allowed=true)=>apiRequest<{active_ids:string[];plans:LocalPlan[]}>(`/notifications/local-plan?device_id=${id}&local_allowed=${allowed}`),
 ack:(device_id:string,plan:LocalPlan)=>post('/notifications/local-ack',{device_id,notification_id:plan.id,scheduled_at:plan.scheduled_at}),
 observed:(id:string,device:string)=>post(`/notifications/${id}/observed?device_id=${device}`),
 manual:(data:{entity_type:string;entity_id:string;local_date:string;local_time:string;priority:string;purpose:string;replaces?:string})=>post<NotificationItem>('/notifications/reminders',data),
};
