import type { Data, Operation } from './types';

const hour = 60 * 60 * 1000;
export const offlineLifetime = 24 * hour;
export const canRestore = (at: number, expiry: number, now: number) => at > 0 && at <= now && now < expiry && expiry <= at + offlineLifetime;
export const backoff = (attempt: number) => Math.min(15 * 60_000, 5000 * 2 ** Math.max(0, attempt - 1));
export const isUuid = (value: unknown): value is string => typeof value === 'string'
  && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
export const newerOrEqual = (left: string, right: string) => BigInt(left) >= BigInt(right);

export const roots: Record<string, string> = {
  cases: 'case', hearings: 'hearing', diary: 'diary', tasks: 'task', appointments: 'appointment',
  documents: 'document', 'draft-documents': 'draft', payments: 'payment', clients: 'client',
  courts: 'court', 'research-items': 'research', 'research-notes': 'research_note',
  'fee-agreements': 'agreement', expenses: 'expense', invoices: 'invoice', receipts: 'receipt',
};
const supported: Record<string, string[]> = {
  case: ['create', 'update', 'archive', 'restore', 'status'],
  hearing: ['create', 'update', 'cancel', 'reschedule'],
  diary: ['create', 'update', 'delete', 'pin', 'unpin', 'important', 'unimportant'],
  task: ['create', 'update', 'archive', 'complete', 'reopen'],
  appointment: ['create', 'update', 'archive', 'cancel'],
  document: ['update', 'archive'],
  draft: ['create', 'update', 'archive', 'restore'],
  payment: ['create', 'update'],
};
export function writeRoute(path: string, method: string) {
  const [root, id, sub, extra] = path.split('?')[0].split('/').filter(Boolean);
  const kind = roots[root];
  if (!kind || extra || (id && !isUuid(id))) return null;
  let action = '';
  if (method === 'POST') action = !id ? 'create' : sub ?? '';
  if (method === 'PATCH' && id && !sub) action = 'update';
  if (method === 'DELETE' && id) {
    if (kind === 'diary') action = sub === 'pin' ? 'unpin' : sub === 'important' ? 'unimportant' : !sub ? 'delete' : '';
    else if (!sub) action = kind === 'hearing' ? 'cancel' : 'archive';
  }
  return supported[kind]?.includes(action) ? { kind, action, id } : null;
}

export function localEffect(operation: Operation, previous: Data | null, stamp: string): Data | null {
  const { action, kind, payload, entity_id } = operation;
  if (action === 'delete') return null;
  const { expected_updated_at: _draftRevision, ...changes } = payload;
  const next: Data = { ...(previous ?? {}), ...changes, id: entity_id, updated_at: stamp };
  if (action === 'create') {
    next.created_at = stamp;
    if (kind === 'case') {
      next.current_status = payload.initial_status ?? 'Pending';
      next.is_archived = false;
    }
    if (kind === 'hearing') next.status = 'Scheduled';
    if (kind === 'document') {
      next.storage_status = 'upload_pending';
      next.is_archived = false;
      next.current_version_id = null;
      next.file_extension = '.' + String(payload.original_filename ?? '').split('.').pop();
    }
    if (kind === 'payment') next.status = 'pending';
  }
  if (action === 'archive' || action === 'restore') {
    if (kind === 'case' || kind === 'document') next.is_archived = action === 'archive';
    else next.archived_at = action === 'archive' ? stamp : null;
  }
  if (action === 'complete') { next.status = 'Completed'; next.completed_at = stamp; }
  if (action === 'reopen') { next.status = 'Pending'; next.completed_at = null; }
  if (action === 'cancel') next.status = 'Cancelled';
  if (action === 'status') next.current_status = payload.new_status;
  if (action === 'pin' || action === 'unpin') next.is_pinned = action === 'pin';
  if (action === 'important' || action === 'unimportant') next.is_important = action === 'important';
  if (action === 'reschedule') {
    next.hearing_date = previous?.hearing_date;
    next.hearing_time = previous?.hearing_time;
    next.estimated_end_time = previous?.estimated_end_time;
    next.status = 'Postponed';
    next.next_hearing_date = payload.hearing_date;
    next.next_hearing_time = payload.hearing_time;
    next.follow_up_hearing_id = payload.follow_up_id;
  }
  return next;
}

export function nextQueueState(status: string, attempts: number) {
  if (status === 'applied' || status === 'conflict' || status === 'blocked') return status;
  return status === 'retryable' && attempts < 5 ? 'retry' : 'failed';
}

