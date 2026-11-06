import { useAuthStore } from '../store/auth-store';
import type { TokenResponse } from '../features/auth/types';

export const baseUrl = process.env.EXPO_PUBLIC_API_URL?.replace(/\/$/, '');
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }
export type RequestOptions = RequestInit & { offlineBase?: string };
const mutationListeners=new Set<()=>void>();
export function onApiMutation(listener:()=>void){mutationListeners.add(listener);return ()=>{mutationListeners.delete(listener);};}
let refreshing: Promise<boolean> | null = null;

async function parseResponse<T>(response: Response): Promise<T> {
  const contentType = response.headers.get('Content-Type') ?? '';
  if (response.ok && (contentType.includes('text/csv') || contentType.includes('text/plain'))) return await response.text() as T;
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
    const response = await boundedFetch(`${baseUrl}/api/v1/auth/refresh`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: token }) });
    const tokens = await parseResponse<TokenResponse>(response);
    await useAuthStore.getState().setTokens(tokens, token);
    return !!useAuthStore.getState().accessToken;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401 && useAuthStore.getState().refreshToken === token) await useAuthStore.getState().clear(true);
    return false;
  }
}

export async function ensureSession(): Promise<boolean> {
  if (useAuthStore.getState().accessToken) return true;
  refreshing ??= refreshSession().finally(() => { refreshing = null; });
  return refreshing;
}

async function boundedFetch(url: string, options: RequestInit) {
  const controller = new AbortController();
  const stop = () => controller.abort();
  const timer = setTimeout(stop, 15_000);
  if (options.signal?.aborted) stop();
  else options.signal?.addEventListener('abort', stop, { once: true });
  try { return await fetch(url, { ...options, signal: controller.signal }); }
  finally { clearTimeout(timer); options.signal?.removeEventListener('abort', stop); }
}

export async function networkRequest<T>(path: string, options: RequestInit = {}, authenticated = true): Promise<T> {
  if (!baseUrl) throw new ApiError(0, 'EXPO_PUBLIC_API_URL is not configured');
  const originalOwner = useAuthStore.getState().user?.id;
  if (authenticated && !useAuthStore.getState().accessToken) await ensureSession();
  const owner = useAuthStore.getState().user?.id;
  if (authenticated && originalOwner && originalOwner !== owner) throw new ApiError(401, 'Account changed');
  const transport = !options.method || options.method === 'GET' || path.startsWith('/sync/') ? boundedFetch : fetch;
  const send = () => transport(`${baseUrl}/api/v1${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...(authenticated && useAuthStore.getState().accessToken ? { Authorization: `Bearer ${useAuthStore.getState().accessToken}` } : {}), ...options.headers } });
  try {
    let response = await send();
    if (authenticated && response.status === 401 && owner === useAuthStore.getState().user?.id && await (refreshing ??= refreshSession().finally(() => { refreshing = null; }))) {
      if (owner && owner !== useAuthStore.getState().user?.id) throw new ApiError(401, 'Account changed');
      response = await send();
    }
    const result=await parseResponse<T>(response);
    if (authenticated && owner && owner !== useAuthStore.getState().user?.id) throw new ApiError(401, 'Account changed');
    if(options.method&&options.method!=='GET'&&!/^\/(notifications|notification-preferences|auth|sync)(?:\/|$)/.test(path))mutationListeners.forEach(listener=>listener());
    return result;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(0, 'Network request failed');
  }
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}, authenticated = true): Promise<T> {
  const owner = authenticated ? useAuthStore.getState().user?.id : undefined;
  if (!owner || /^\/(auth|sync)(?:\/|$)/.test(path)) return networkRequest(path, options, authenticated);
  const { offlineRequest } = await import('../features/sync/transport');
  return offlineRequest<T>(owner, path, options);
}
