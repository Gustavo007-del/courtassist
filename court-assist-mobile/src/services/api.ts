import { useAuthStore } from '../store/auth-store';
import type { TokenResponse } from '../features/auth/types';

export const baseUrl = process.env.EXPO_PUBLIC_API_URL?.replace(/\/$/, '');
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }
let refreshing: Promise<boolean> | null = null;

async function parseResponse<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : 'Request failed';
    throw new ApiError(response.status, detail);
  }
  return data as T;
}

async function refreshSession(): Promise<boolean> {
  const token = useAuthStore.getState().refreshToken;
  if (!token || !baseUrl) return false;
  try {
    const response = await fetch(`${baseUrl}/api/v1/auth/refresh`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: token }) });
    const tokens = await parseResponse<TokenResponse>(response);
    await useAuthStore.getState().setTokens(tokens);
    return true;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) await useAuthStore.getState().clear();
    return false;
  }
}

export async function ensureSession(): Promise<boolean> {
  if (useAuthStore.getState().accessToken) return true;
  refreshing ??= refreshSession().finally(() => { refreshing = null; });
  return refreshing;
}

export async function apiRequest<T>(path: string, options: RequestInit = {}, authenticated = true): Promise<T> {
  if (!baseUrl) throw new ApiError(0, 'EXPO_PUBLIC_API_URL is not configured');
  if (authenticated && !useAuthStore.getState().accessToken) await ensureSession();
  const send = () => fetch(`${baseUrl}/api/v1${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...(authenticated && useAuthStore.getState().accessToken ? { Authorization: `Bearer ${useAuthStore.getState().accessToken}` } : {}), ...options.headers } });
  try {
    let response = await send();
    if (authenticated && response.status === 401 && await (refreshing ??= refreshSession().finally(() => { refreshing = null; }))) response = await send();
    return await parseResponse<T>(response);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(0, 'Network request failed');
  }
}
