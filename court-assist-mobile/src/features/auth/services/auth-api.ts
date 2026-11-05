import { apiRequest } from '../../../services/api';
import type { Advocate, TokenResponse } from '../types';

export const authApi = {
  login: (identifier: string, password: string) => apiRequest<TokenResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ identifier, password }) }, false),
  register: (data: { full_name: string; email?: string; phone_number?: string; password: string; confirm_password: string; preferred_language: 'en' | 'ml' }) => apiRequest<Advocate>('/auth/register', { method: 'POST', body: JSON.stringify(data) }, false),
  forgot: (email: string) => apiRequest<{ detail: string }>('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) }, false),
  reset: (token: string, password: string, confirm_password: string) => apiRequest<{ detail: string }>('/auth/reset-password', { method: 'POST', body: JSON.stringify({ token, password, confirm_password }) }, false),
  logout: (refresh_token: string) => apiRequest<{ detail: string }>('/auth/logout', { method: 'POST', body: JSON.stringify({ refresh_token }) }),
  me: () => apiRequest<Advocate>('/users/me'),
  updateMe: (data: Partial<Advocate>) => apiRequest<Advocate>('/users/me', { method: 'PATCH', body: JSON.stringify(data) }),
  changePassword: (current_password: string, new_password: string, confirm_password: string) => apiRequest<{ detail: string }>('/auth/change-password', { method: 'POST', body: JSON.stringify({ current_password, new_password, confirm_password }) }),
  sessions: () => apiRequest<{ active_sessions: number; last_login_at: string | null }>('/auth/sessions'),
};
