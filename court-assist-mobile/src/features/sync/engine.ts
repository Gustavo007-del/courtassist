import { networkRequest, ApiError } from '../../services/api';
import { useAuthStore } from '../../store/auth-store';
import { finishUpload, transfer } from './files';
import { backoff, nextQueueState } from './policy';
import { applyPage, control, outcome, queue, saveRun, writeCache } from './repository';
import { syncDatabase } from './schema';
import { useSyncState } from './state';
import type { Change, QueueItem, Result } from './types';

let running: Promise<boolean> | null = null;
const owned = (owner: string) => useAuthStore.getState().user?.id === owner;

export async function status(owner: string) {
  const info = await control(owner);
  if (!info?.enabled) return { enabled: false, pending: 0, failed: 0, conflicts: 0, lastSync: null };
  const rows = await (await syncDatabase()).getAllAsync<{ status: string; count: number }>(
    "SELECT status, COUNT(*) AS count FROM sync_queue WHERE owner=? AND status NOT IN ('applied','discarded') GROUP BY status", owner);
  const count = (names: string[]) => rows.filter(row => names.includes(row.status)).reduce((total, row) => total + row.count, 0);
  return { enabled: true, pending: count(['pending', 'retry', 'blocked']), failed: count(['failed']), conflicts: count(['conflict']), lastSync: info.last_sync };
}

export async function publishStatus(owner: string) {
  const summary = await status(owner);
  if (owned(owner)) useSyncState.setState(summary);
  return summary;
}

async function run(owner: string, manual: boolean, background: boolean) {
  if (!owned(owner) || useSyncState.getState().connected === false) return false;
  const info = await control(owner);
  if (!info?.enabled || (!manual && !info.automatic)) return false;
  const start = Date.now();
  let applied = 0;
  let changed = false;
  let hasMore = false;
  let result = 'incomplete';
  useSyncState.setState({ running: true, phase: 'push' });
  try {
    const items = await queue(owner, true, background ? 8 : 30);
    const pending = new Map(items.map(item => [item.id, item.status]));
    for (const item of items) {
      if (!owned(owner)) return changed;
      const dependencies = [...item.operation.depends_on, item.operation.after_operation_id];
      if (dependencies.some(id => id && pending.has(id) && pending.get(id) !== 'applied')) {
        await outcome(owner, item, 'blocked', { id: item.id, status: 'blocked', error: 'dependency_pending' }, Date.now() + 60_000);
        pending.set(item.id, 'blocked');
        continue;
      }
      useSyncState.setState({ phase: item.upload ? 'upload' : 'push' });
      let confirmation: Result;
      try {
        confirmation = (await networkRequest<{ results: Result[] }>('/sync/push', {
          method: 'POST', body: JSON.stringify({ device_id: info.device, operations: [item.operation] }),
        })).results[0];
        if (confirmation.status === 'applied' && item.upload) {
          if (!owned(owner)) return changed;
          await transfer(owner, item);
          confirmation.server = await networkRequest<Change>(`/sync/records/document/${item.entity}`);
        }
      } catch (error) {
        const invalid = error instanceof ApiError && error.status >= 400 && error.status < 500 && error.status !== 401 && error.status !== 410 && error.status !== 429;
        confirmation = { id: item.id, status: invalid ? 'invalid' : 'retryable', error: item.upload ? 'upload_interrupted' : 'connection_interrupted' };
      }
      if (!owned(owner)) return changed;
      const next = nextQueueState(confirmation.status, item.retries + 1);
      await outcome(owner, item, next, confirmation,
        next === 'blocked' ? Date.now() + 60_000 : next === 'retry' ? Date.now() + backoff(item.retries + 1) : 0);
      pending.set(item.id, next);
      if (next === 'applied') {
        applied += 1;
        changed = true;
        if (item.upload) finishUpload(owner, item.upload);
      }
      if (confirmation.error === 'connection_interrupted') return changed;
    }
    useSyncState.setState({ phase: 'pull' });
    let cursor = info.cursor;
    for (let index = 0; index < (background ? 4 : 20); index += 1) {
      if (!owned(owner)) return changed;
      const page = await networkRequest<{ changes: Change[]; cursor: string; has_more: boolean }>('/sync/pull', {
        method: 'POST', body: JSON.stringify({ cursor, device_id: info.device, limit: 50 }),
      });
      if (!owned(owner)) return changed;
      await applyPage(owner, page.changes, page.cursor);
      changed ||= page.changes.length > 0;
      cursor = page.cursor;
      hasMore = page.has_more;
      if (!hasMore) break;
    }
    if (!background && (!info.last_sync || changed)) {
      for (const path of ['/dashboard/overview', '/finance/summary', '/courts?limit=100']) {
        try {
          const data = await networkRequest(path);
          if (owned(owner)) await writeCache(owner, path, data);
        } catch { /* An unavailable optional summary does not invalidate the record feed. */ }
      }
    }
    const summary = await status(owner);
    result = hasMore || summary.pending || summary.failed || summary.conflicts ? 'incomplete' : 'complete';
    return changed;
  } catch {
    result = 'failed';
    return changed;
  } finally {
    if (owned(owner)) {
      await saveRun(owner, start, result, applied).catch(() => {});
      await publishStatus(owner).catch(() => {});
    }
    useSyncState.setState({ running: false, phase: null });
  }
}

export function syncNow(owner: string, manual = false, background = false) {
  running ??= run(owner, manual, background).finally(() => { running = null; });
  return running;
}

export async function resolve(owner: string, item: QueueItem, strategy: 'server' | 'local' | 'merge', id: string, payload?: Record<string, unknown>) {
  const info = await control(owner);
  if (!info || !item.result?.revision) throw new Error('offline_conflict_missing');
  type Resolution = { strategy: string; result: Result };
  let reply: Resolution;
  try {
    reply = await networkRequest<Resolution>(`/sync/conflicts/${item.id}/resolve`, {
      method: 'POST', body: JSON.stringify({
        id, device_id: info.device, strategy, server_revision: item.result.revision, payload,
      }),
    });
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 409) throw error;
    const current = await networkRequest<Result & { resolved?: Resolution }>(`/sync/operations/${item.id}`);
    if (!current.resolved) {
      if (owned(owner)) await outcome(owner, item, 'conflict', current);
      throw error;
    }
    reply = current.resolved;
  }
  if (!owned(owner)) return;
  await outcome(owner, item, reply.strategy === 'server' ? 'discarded' : 'applied', reply.result);
  await publishStatus(owner);
}

