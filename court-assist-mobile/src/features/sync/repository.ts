import { Platform } from 'react-native';
import { randomUUID, digestStringAsync, CryptoDigestAlgorithm } from 'expo-crypto';
import type { SQLiteDatabase } from 'expo-sqlite';
import type { Advocate } from '../auth/types';
import { syncDatabase } from './schema';
import { destroyKey, pack, unpack } from './crypto';
import { canRestore, isUuid, localEffect, newerOrEqual, offlineLifetime } from './policy';
import type { Change, Control, Data, Operation, QueueItem, QueueState, Result } from './types';

type Row = { id: string; kind: string; revision: string; local_version: number; pending: string | null; deleted: number; body: string | null };
type Stored = Omit<QueueItem, 'operation' | 'result'> & { body: string | null; result: string | null };
const supported = () => Platform.OS !== 'web';
const stamp = () => new Date().toISOString();
let writes: Promise<unknown> = Promise.resolve();
export function serialized<T>(work: () => Promise<T>): Promise<T> {
  const result = writes.then(work, work);
  writes = result.catch(() => {});
  return result;
}

export async function control(owner: string) {
  return supported() ? (await syncDatabase()).getFirstAsync<Control>('SELECT * FROM sync_control WHERE owner=?', owner) : null;
}

export async function enable(owner: string, user: Advocate, expiry: number) {
  await serialized(async () => {
    const db = await syncDatabase();
    const verified = Date.now();
    await db.runAsync(`INSERT INTO sync_control(owner,enabled,device,verified_at,expires_at,profile)
      VALUES(?,1,?,?,?,?) ON CONFLICT(owner) DO UPDATE SET enabled=1,verified_at=excluded.verified_at,
      expires_at=excluded.expires_at,profile=excluded.profile`,
    owner, randomUUID(), verified, Math.min(expiry, verified + offlineLifetime), await pack(owner, 'profile', user));
  });
}

export async function remember(user: Advocate, expires: number) {
  if (!await control(user.id).then(value => value?.enabled)) return;
  await serialized(async () => {
    const db = await syncDatabase();
    if (!(await control(user.id))?.enabled) return;
    const verified = Date.now();
    await db.runAsync('UPDATE sync_control SET verified_at=?,expires_at=?,profile=? WHERE owner=?',
      verified, Math.min(expires, verified + offlineLifetime), await pack(user.id, 'profile', user), user.id);
  });
}

export async function restore(owner: string) {
  const value = await control(owner);
  if (!value?.enabled || !value.profile || !canRestore(value.verified_at, value.expires_at, Date.now())) return null;
  return unpack<Advocate>(owner, 'profile', value.profile);
}

function rowBody(owner: string, row: Row) {
  return row.body && !row.deleted ? unpack<Data>(owner, `record:${row.kind}:${row.id}`, row.body) : null;
}
export async function getRecord(owner: string, kind: string, id: string) {
  const row = await (await syncDatabase()).getFirstAsync<Row>('SELECT * FROM sync_entities WHERE owner=? AND kind=? AND id=?', owner, kind, id);
  return row ? rowBody(owner, row) : null;
}
export async function hasRecord(owner: string, kind: string, id: string) {
  return !!await (await syncDatabase()).getFirstAsync('SELECT 1 FROM sync_entities WHERE owner=? AND kind=? AND id=?', owner, kind, id);
}
export async function hasKind(owner: string, kind: string) {
  return !!await (await syncDatabase()).getFirstAsync('SELECT 1 FROM sync_entities WHERE owner=? AND kind=? LIMIT 1', owner, kind);
}
export async function records(owner: string, kind: string) {
  const db = await syncDatabase();
  const out: Data[] = [];
  let previous = '';
  while (true) {
    const rows = await db.getAllAsync<Row>(`SELECT * FROM sync_entities WHERE owner=? AND kind=? AND deleted=0 AND id>?
      ORDER BY id LIMIT 200`, owner, kind, previous);
    for (const row of rows) {
      const data = await rowBody(owner, row);
      if (data) out.push(data);
    }
    if (rows.length < 200) return out;
    previous = rows[rows.length - 1].id;
  }
}
async function project(tx: SQLiteDatabase, owner: string, change: Change, clear?: string) {
  const old = await tx.getFirstAsync<Row>('SELECT * FROM sync_entities WHERE owner=? AND kind=? AND id=?', owner, change.kind, change.id);
  if (old?.pending && old.pending !== clear) return;
  if (old && !newerOrEqual(change.revision, old.revision)) return;
  await tx.runAsync(`INSERT INTO sync_entities(owner,kind,id,revision,deleted,body,synced_at)
    VALUES(?,?,?,?,?,?,?) ON CONFLICT(owner,kind,id) DO UPDATE SET revision=excluded.revision,
    pending=NULL,deleted=excluded.deleted,body=excluded.body,synced_at=excluded.synced_at`,
  owner, change.kind, change.id, change.revision, Number(change.deleted),
  change.record ? await pack(owner, `record:${change.kind}:${change.id}`, change.record) : null, stamp());
}

export function applyPage(owner: string, changes: Change[], cursor?: string) {
  return serialized(async () => {
    const db = await syncDatabase();
    if (!(await control(owner))?.enabled) return;
    await db.withExclusiveTransactionAsync(async tx => {
      for (const change of changes) await project(tx, owner, change);
      if (cursor !== undefined) {
        const current = await tx.getFirstAsync<{ cursor: string }>('SELECT cursor FROM sync_control WHERE owner=?', owner);
        if (current && newerOrEqual(cursor, current.cursor)) await tx.runAsync('UPDATE sync_control SET cursor=? WHERE owner=?', cursor, owner);
      }
    });
  });
}

export function enqueue(owner: string, kind: string, action: string, id: string, payload: Data, upload?: string, baseUpdatedAt?: string) {
  return serialized(async () => {
    const db = await syncDatabase();
    if (!(await control(owner))?.enabled) throw new Error('offline_disabled');
    let operation!: Operation;
    let optimistic: Data | null = null;
    await db.withExclusiveTransactionAsync(async tx => {
      const row = await tx.getFirstAsync<Row>('SELECT * FROM sync_entities WHERE owner=? AND kind=? AND id=?', owner, kind, id);
      const previous = row ? await rowBody(owner, row) : null;
      if (action !== 'create' && !previous) throw new Error('offline_record_missing');
      const pending = row?.pending ?? undefined;
      if (pending && baseUpdatedAt && previous?.updated_at !== baseUpdatedAt) throw new Error('offline_local_changed');
      if (pending) {
        const source = await tx.getFirstAsync<{ entity: string }>('SELECT entity FROM sync_queue WHERE owner=? AND id=?', owner, pending);
        if (source?.entity !== id) throw new Error('offline_followup_pending');
      }
      const dependencies = new Set<string>();
      for (const field of ['case_id', 'client_id', 'hearing_id', 'document_id', 'agreement_id']) {
        const linked = payload[field];
        if (!isUuid(linked)) continue;
        const parent = await tx.getFirstAsync<{ pending: string }>('SELECT pending FROM sync_entities WHERE owner=? AND id=? AND pending IS NOT NULL', owner, linked);
        if (parent) dependencies.add(parent.pending);
      }
      operation = { id: randomUUID(), kind, entity_id: id, action, payload, base_revision: row?.revision ?? '0',
        local_version: (row?.local_version ?? 0) + 1, depends_on: [...dependencies], after_operation_id: pending,
        base_updated_at: pending ? undefined : baseUpdatedAt };
      const when = stamp();
      optimistic = localEffect(operation, previous, when);
      if (optimistic) optimistic = { ...optimistic, user_id: owner, sync_status: 'pending' };
      await tx.runAsync(`INSERT INTO sync_queue(owner,id,kind,entity,status,created_at,upload,body)
        VALUES(?,?,?,?,'pending',?,?,?)`, owner, operation.id, kind, id, when, upload ?? null,
      await pack(owner, `operation:${operation.id}`, operation));
      await tx.runAsync(`INSERT INTO sync_entities(owner,kind,id,revision,local_version,pending,deleted,body)
        VALUES(?,?,?,?,1,?,?,?) ON CONFLICT(owner,kind,id) DO UPDATE SET local_version=local_version+1,
        pending=excluded.pending,deleted=excluded.deleted,body=excluded.body`,
      owner, kind, id, operation.base_revision, operation.id, Number(!optimistic),
      optimistic ? await pack(owner, `record:${kind}:${id}`, optimistic) : row?.body ?? null);
      if (action === 'reschedule' && optimistic && isUuid(payload.follow_up_id)) {
        const follow = { ...optimistic, id: payload.follow_up_id, hearing_date: payload.hearing_date,
          hearing_time: payload.hearing_time, estimated_end_time: payload.estimated_end_time, status: 'Scheduled',
          next_hearing_date: null, next_hearing_time: null, follow_up_hearing_id: null, created_at: when };
        await tx.runAsync('INSERT INTO sync_entities(owner,kind,id,local_version,pending,body) VALUES(?,?,?,1,?,?)',
          owner, kind, follow.id, operation.id, await pack(owner, `record:${kind}:${follow.id}`, follow));
      }
    });
    return { operation, optimistic };
  });
}

async function decode(owner: string, row: Stored): Promise<QueueItem> {
  const { body, result, ...metadata } = row;
  if (!body) throw new Error('offline_operation_missing');
  return { ...metadata, operation: await unpack<Operation>(owner, `operation:${row.id}`, body),
    result: result ? await unpack<Result>(owner, `result:${row.id}`, result) : null };
}

export async function queue(owner: string, ready = false, limit = 100, offset = 0) {
  const db = await syncDatabase();
  const filter = ready ? "status IN ('pending','retry','blocked') AND next_attempt<=?" : "status NOT IN ('applied','discarded')";
  const rows = await db.getAllAsync<Stored>(`SELECT * FROM sync_queue WHERE owner=? AND ${filter} ORDER BY seq LIMIT ? OFFSET ?`,
    owner, ...(ready ? [Date.now()] : []), limit, offset);
  return Promise.all(rows.map(row => decode(owner, row)));
}

export async function outcome(owner: string, item: QueueItem, state: QueueState, result: Result, next = 0) {
  await serialized(async () => {
    const db = await syncDatabase();
    if (!(await control(owner))?.enabled) return;
    await db.withExclusiveTransactionAsync(async tx => {
      await tx.runAsync(`UPDATE sync_queue SET status=?, retries=?, next_attempt=?, last_attempt=?, error=?, result=?, body=
        CASE WHEN ? IN ('applied','discarded') THEN NULL ELSE body END WHERE owner=? AND id=?`,
      state, item.retries + (state === 'blocked' ? 0 : 1), next, stamp(), result.error ?? null,
      state === 'applied' || state === 'discarded' ? null : await pack(owner, `result:${item.id}`, result),
      state, owner, item.id);
      if ((state === 'applied' || state === 'discarded') && result.server) await project(tx, owner, result.server, item.id);
      const follow = item.operation.payload.follow_up_id;
      if ((state === 'applied' || state === 'discarded') && item.operation.action === 'reschedule' && isUuid(follow)) {
        await tx.runAsync('DELETE FROM sync_entities WHERE owner=? AND kind=? AND id=? AND pending=?', owner, item.kind, follow, item.id);
      }
    });
  });
}

export async function retry(owner: string, id: string) {
  await serialized(async () => (await syncDatabase()).runAsync(`UPDATE sync_queue SET status='pending',next_attempt=0,retries=0
    WHERE owner=? AND id=? AND status IN ('failed','retry','blocked')`, owner, id));
}

export async function writeCache(owner: string, path: string, data: unknown) {
  const key = await digestStringAsync(CryptoDigestAlgorithm.SHA256, path);
  await serialized(async () => {
    if (!(await control(owner))?.enabled) return;
    await (await syncDatabase()).runAsync('INSERT OR REPLACE INTO sync_http VALUES(?,?,?,?)',
      owner, key, await pack(owner, `http:${key}`, data), Date.now());
  });
}

export async function readCache<T>(owner: string, path: string) {
  const key = await digestStringAsync(CryptoDigestAlgorithm.SHA256, path);
  const row = await (await syncDatabase()).getFirstAsync<{ body: string }>('SELECT body FROM sync_http WHERE owner=? AND key=?', owner, key);
  return row ? unpack<T>(owner, `http:${key}`, row.body) : undefined;
}

export async function saveRun(owner: string, start: number, status: string, applied: number) {
  await serialized(async () => {
    const db = await syncDatabase();
    if (!(await control(owner))?.enabled) return;
    await db.runAsync('INSERT INTO sync_runs(owner,ran_at,duration,status,applied) VALUES(?,?,?,?,?)',
      owner, stamp(), Date.now() - start, status, applied);
    if (status === 'complete') await db.runAsync('UPDATE sync_control SET last_sync=? WHERE owner=?', stamp(), owner);
    await db.runAsync('DELETE FROM sync_runs WHERE owner=? AND id NOT IN (SELECT id FROM sync_runs WHERE owner=? ORDER BY id DESC LIMIT 50)', owner, owner);
    await db.runAsync('DELETE FROM sync_http WHERE owner=? AND saved_at<?', owner, Date.now() - 7 * offlineLifetime);
  });
}

export async function clearRecords(owner: string) {
  if (!supported() || !isUuid(owner)) return;
  await serialized(async () => {
    const db = await syncDatabase();
    await db.withExclusiveTransactionAsync(async tx => {
      for (const table of ['sync_control', 'sync_entities', 'sync_queue', 'sync_http', 'sync_files', 'sync_runs']) {
        await tx.runAsync(`DELETE FROM ${table} WHERE owner=?`, owner);
      }
    });
    await destroyKey(owner);
  });
}

