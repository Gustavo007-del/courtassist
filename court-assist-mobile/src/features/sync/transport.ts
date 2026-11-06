import { Platform } from 'react-native';
import { randomUUID } from 'expo-crypto';
import { ApiError, networkRequest, type RequestOptions } from '../../services/api';
import { useAuthStore } from '../../store/auth-store';
import { cacheable, localRead } from './read';
import { applyPage, control, enqueue, getRecord, writeCache } from './repository';
import { publishStatus, syncNow } from './engine';
import { canRestore, isUuid, writeRoute } from './policy';
import { useSyncState } from './state';
import { syncDatabase } from './schema';
import type { Change, Data } from './types';

function localFailure(code: string): never {
  throw new ApiError(0, code);
}

export async function offlineRequest<T>(owner: string, path: string, options: RequestOptions): Promise<T> {
  if (Platform.OS === 'web') return networkRequest(path, options);
  const connected = useSyncState.getState().connected;
  if (connected === false && /^\/ai(?:\/|$)/.test(path)) localFailure('offline_online_required');
  const profile = await control(owner).catch(() => null);
  if (!profile?.enabled) return networkRequest(path, options);
  const method = options.method ?? 'GET';
  const available = () => useAuthStore.getState().user?.id === owner;
  if (!available()) localFailure('offline_account_changed');
  const verifyOfflineSession = async () => {
    if (!available()) localFailure('offline_account_changed');
    if (!canRestore(profile.verified_at, profile.expires_at, Date.now())) {
      await useAuthStore.getState().clear(true);
      localFailure('offline_session_expired');
    }
  };
  if (connected === false) await verifyOfflineSession();
  if (method === 'GET' && cacheable(path)) {
    const [, identifier] = path.split('?')[0].split('/').filter(Boolean);
    const entity = isUuid(identifier) ? await (await syncDatabase()).getFirstAsync<{ pending: string }>(
      'SELECT pending FROM sync_entities WHERE owner=? AND id=? AND pending IS NOT NULL LIMIT 1', owner, identifier) : null;
    if (connected === false || entity?.pending || (!isUuid(identifier) && useSyncState.getState().pending > 0)) {
      const value = await localRead<T>(owner, path);
      if (!available()) localFailure('offline_account_changed');
      if (value !== undefined) return value;
      if (connected === false) localFailure('offline_record_missing');
    }
    try {
      const value = await networkRequest<T>(path, options);
      if (!available()) localFailure('offline_account_changed');
      await writeCache(owner, path, value).catch(() => {});
      return value;
    } catch (error) {
      if (error instanceof ApiError && error.status === 0 && available()) {
        await verifyOfflineSession();
        const value = await localRead<T>(owner, path);
        if (!available()) localFailure('offline_account_changed');
        if (value !== undefined) return value;
      }
      throw error;
    }
  }
  if (connected === false && /^\/(hearings|appointments)\/check-conflicts(?:\?|$)/.test(path)) {
    // Replayed appointment changes always undergo the server's current scheduling check.
    return [] as T;
  }
  const route = writeRoute(path, method);
  if (!route) {
    if (connected === false) localFailure('offline_online_required');
    return networkRequest(path, options);
  }
  const payload = (typeof options.body === 'string' ? JSON.parse(options.body) : {}) as Data;
  const baseUpdatedAt = options.offlineBase ?? (typeof payload.expected_updated_at === 'string' ? payload.expected_updated_at : undefined);
  const pendingLinks = await Promise.all(Object.values(payload).filter(isUuid).map(id => (async () =>
    (await syncDatabase()).getFirstAsync('SELECT 1 FROM sync_entities WHERE owner=? AND id=? AND pending IS NOT NULL LIMIT 1', owner, id))()));
  const pendingRecord = route.id && await (await syncDatabase()).getFirstAsync(
    'SELECT 1 FROM sync_entities WHERE owner=? AND id=? AND pending IS NOT NULL LIMIT 1', owner, route.id);
  if (connected !== false && !pendingLinks.some(Boolean) && !pendingRecord) {
    // Preserve the existing online confirmation, financial and appointment workflows.
    return networkRequest(path, options);
  }
  const id = route.id ?? randomUUID();
  if (route.kind === 'payment' && route.action === 'create') payload.status = 'pending';
  if (route.action === 'reschedule') payload.follow_up_id = randomUUID();
  if (route.kind === 'case' && route.action === 'update') {
    delete payload.initial_status;
    delete payload.parties;
    delete payload.advocates;
  }
  if (route.kind === 'diary' && route.action === 'update') {
    delete payload.case_id;
    delete payload.request_id;
  }
  if (route.kind === 'hearing' && route.action === 'update') delete payload.case_id;
  for (const field of ['id', 'user_id', 'created_at', 'updated_at', 'sync_status', 'archived_at', 'completed_at', 'recurrence_root_id', 'occurrence_date', 'is_overdue']) {
    if (route.kind === 'task' || route.kind === 'appointment') delete payload[field];
  }
  if (route.kind === 'draft' && route.action === 'update') delete payload.expected_updated_at;
  if (route.id && !await getRecord(owner, route.kind, route.id)) {
    if (connected !== false) {
      const snapshot = await networkRequest<Change>(`/sync/records/${route.kind}/${route.id}`);
      if (available()) await applyPage(owner, [snapshot]);
    } else localFailure('offline_record_missing');
  }
  if (!available()) localFailure('offline_account_changed');
  const { optimistic } = await enqueue(owner, route.kind, route.action, id, payload, undefined, baseUpdatedAt);
  await publishStatus(owner);
  if (connected !== false) void syncNow(owner);
  return optimistic as T;
}

