import * as SecureStore from 'expo-secure-store';
import { getNotificationDeviceId,clearNotifications } from '../../../services/notification-manager';
import { apiRequest } from '../../../services/api';
import type { Advocate, TokenResponse } from '../types';

export const authApi = {
  login: (identifier: string, password: string) => apiRequest<TokenResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ identifier, password }) }, false),
  register: (data: { full_name: string; email?: string; phone_number?: string; password: string; confirm_password: string; preferred_language: 'en' | 'ml' }) => apiRequest<Advocate>('/auth/register', { method: 'POST', body: JSON.stringify(data) }, false),
  forgot: (email: string) => apiRequest<{ detail: string }>('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) }, false),
  reset: (token: string, password: string, confirm_password: string) => apiRequest<{ detail: string }>('/auth/reset-password', { method: 'POST', body: JSON.stringify({ token, password, confirm_password }) }, false),
  logout: async (refresh_token: string) => { const device_id=getNotificationDeviceId(); const installation_id=await SecureStore.getItemAsync('courtassist.installation').catch(()=>null); try { return await apiRequest<{detail:string}>('/auth/logout',{method:'POST',body:JSON.stringify({refresh_token,device_id,installation_id})}); } finally { await clearNotifications(); } },
  me: () => apiRequest<Advocate>('/users/me'),
  updateMe: (data: Partial<Advocate>) => apiRequest<Advocate>('/users/me', { method: 'PATCH', body: JSON.stringify(data) }),
  changePassword: (current_password: string, new_password: string, confirm_password: string) => apiRequest<{ detail: string }>('/auth/change-password', { method: 'POST', body: JSON.stringify({ current_password, new_password, confirm_password }) }),
  sessions: () => apiRequest<{ active_sessions: number; last_login_at: string | null }>('/auth/sessions'),
  activeSessions: () => apiRequest<{ id: string; current: boolean; refreshed_at: string; expires_at: string }[]>('/auth/sessions/devices'),
  revokeSession: (id: string) => apiRequest<void>(`/auth/sessions/${id}`, { method: 'DELETE' }),
  requestErasure: (password: string) => apiRequest<{ id: string }>('/users/me/erasure-requests', { method: 'POST', body: JSON.stringify({ password }) }),
};
