import { getRecord, hasKind, hasRecord, readCache, records } from './repository';
import { isUuid, roots } from './policy';
import type { Data } from './types';

const sublists: Record<string, string> = {
  parties: 'party', advocates: 'advocate', 'status-history': 'case_status', timeline: 'timeline',
  activities: 'timeline', hearings: 'hearing', diary: 'diary', documents: 'document',
  notes: 'client_note', interactions: 'client_interaction', reminders: 'planning_reminder',
};
const arrayKinds = new Set(['document', 'draft', 'payment', 'expense', 'agreement', 'invoice', 'receipt']);
const arraySub = new Set(['party', 'advocate', 'case_status', 'document', 'hearing_reminder', 'planning_reminder', 'client_note', 'client_interaction']);
const text = (value: unknown) => value == null ? '' : String(value);
async function sharedCourts(owner: string) {
  const page = await readCache<{ items: Data[] }>(owner, '/courts?limit=100');
  return page?.items.filter(row => row.record_scope === 'shared') ?? [];
}
const keys: Record<string, string> = { category: 'category', status: 'status', court_id: 'court_id',
  case_id: 'case_id', client_id: 'client_id', hearing_id: 'hearing_id', priority: 'priority',
  appointment_type: 'appointment_type', mime_type: 'mime_type', storage_status: 'storage_status',
  item_type: 'item_type', language: 'language', district: 'district', court_type: 'court_type', state: 'state',
};
const dates: Record<string, string> = { hearing: 'hearing_date', task: 'due_date', diary: 'entry_date', appointment: 'appointment_date',
  payment: 'payment_date', expense: 'expense_date', case: 'filing_date' };
const category: Record<string, string> = { case: 'case_category', hearing: 'case_category', document: 'document_category', diary: 'entry_type', timeline: 'activity_type' };

export function cacheable(path: string) {
  const [root, id, sub] = path.split('?')[0].split('/').filter(Boolean);
  if (root === 'dashboard') return id === 'overview';
  if (root === 'finance') return id === 'summary' || id === 'reports';
  if (root === 'calendar') return ['hearings', 'day', 'agenda'].includes(id) && !sub;
  if (root === 'planning') return id === 'reminders' && sub === 'upcoming';
  if (!roots[root]) return false;
  if (!sub) return id !== 'upload-url';
  return !!sublists[sub] || sub === 'history' || sub === 'versions' || (root === 'cases' && sub === 'research-items');
}

function active(row: Data, kind: string, archived: boolean) {
  if (kind === 'client' && row.deleted_at) return false;
  return Boolean(row.is_archived || row.archived_at) === archived;
}

async function withLinks(owner: string, kind: string, row: Data) {
  if (kind !== 'hearing' && kind !== 'diary' && kind !== 'case') return row;
  const caseRow = isUuid(row.case_id) ? await getRecord(owner, 'case', row.case_id) : null;
  const court = isUuid(row.court_id) ? await getRecord(owner, 'court', row.court_id) : null;
  return { ...row, ...(caseRow ? { case_title: caseRow.case_title, case_number: caseRow.case_number,
    case_category: caseRow.case_category } : {}), ...(court ? { court_name: court.name, court_district: court.district } : {}) };
}

export async function localRead<T>(owner: string, path: string): Promise<T | undefined> {
  const [pathname, params] = path.split('?');
  const [root, id, sub, tail] = pathname.split('/').filter(Boolean);
  const q = new URLSearchParams(params);
  const cached = () => readCache<T>(owner, path);
  let kind = roots[root];
  const archived = q.get('archived') === 'true';
  const parent = id && isUuid(id) && sub;
  const today = new Date().toLocaleDateString('en-CA');
  if (root === 'calendar' && id === 'agenda') {
    const entries = await Promise.all(['hearing', 'task', 'appointment'].map(async type => (await records(owner, type))
      .filter(row => active(row, type, false) && text(row[dates[type]]) >= (q.get('from_date') ?? '') &&
        text(row[dates[type]]) <= (q.get('to_date') ?? '9999') && (type !== 'hearing' || row.status === 'Scheduled'))
      .map(row => ({ kind: type, id: row.id, date: row[dates[type]], title: row.title ?? row.purpose ?? row.case_title,
        time: row.hearing_time ?? row.due_time ?? row.start_time ?? null, status: row.status }))));
    return entries.flat().sort((a, b) => text(a.date).localeCompare(text(b.date)) || text(a.time ?? '23:59').localeCompare(text(b.time ?? '23:59'))) as T;
  }
  if (root === 'calendar' && (id === 'day' || id === 'hearings')) kind = 'hearing';
  if (root === 'planning' && id === 'reminders') kind = 'planning_reminder';
  if (!kind) return cached();
  if (isUuid(id) && !sub) {
    const row = await getRecord(owner, kind, id);
    if (row && (kind !== 'case' || q.get('include_archived') === 'true' || !row.is_archived) &&
      (kind !== 'court' || row.is_active !== false)) return await withLinks(owner, kind, row) as T;
    // A tombstone takes precedence over previously cached HTTP detail.
    if (await hasRecord(owner, kind, id)) return undefined;
    return await cached() ?? (kind === 'court' ? (await sharedCourts(owner)).find(row => row.id === id) as T | undefined : undefined);
  }
  const parentKind = kind;
  if (parent) {
    if (tail && tail !== 'history') return cached();
    kind = sub === 'reminders' && parentKind === 'hearing' ? 'hearing_reminder' : sublists[sub];
    if (!kind) return cached();
  }
  if (id && !parent && !['upcoming', 'overdue', 'calendar', 'search', 'day', 'hearings', 'reminders'].includes(id)) return cached();
  const rows = await records(owner, kind);
  if (kind === 'court') rows.push(...await sharedCourts(owner));
  if (!rows.length && !await hasKind(owner, kind)) {
    const existing = await cached();
    if (existing !== undefined) return existing;
  }
  const dateField = dates[kind] ?? 'created_at';
  const from = q.get('from_date') ?? q.get('day');
  const to = q.get('to_date') ?? q.get('day');
  const term = q.get('q')?.toLowerCase();
  const start = q.get('start');
  const end = q.get('end');
  const client = kind === 'case' ? q.get('client_id') : null;
  const partyCases = client ? new Set((await records(owner, 'party')).filter(row => row.client_id === client).map(row => row.case_id)) : null;
  const items = rows.filter(row => {
    if (!active(row, kind, archived) || (kind === 'court' && row.is_active === false)) return false;
    if (parent) {
      const field = parentKind === 'case' ? 'case_id' : parentKind === 'client' ? 'client_id' : parentKind + '_id';
      if (row[field] !== id) return false;
    }
    if (id === 'upcoming' && (text(row[dateField]) < today || ['Completed', 'Cancelled'].includes(text(row.status)))) return false;
    if (id === 'overdue' && (!row[dateField] || text(row[dateField]) >= today || ['Completed', 'Cancelled'].includes(text(row.status)))) return false;
    if (root === 'planning' && (row.status !== 'pending' || text(row.scheduled_at) < new Date().toISOString())) return false;
    if ((from || start) && text(row[dateField]) < (from ?? start ?? '')) return false;
    if ((to || end) && text(row[dateField]) > (to ?? end ?? '')) return false;
    for (const [filter, field] of Object.entries(keys)) {
      const value = q.get(filter);
      const mapped = kind === 'case' && filter === 'status' ? 'current_status' : kind === 'case' && filter === 'district' ? 'court_district' : filter === 'category' ? category[kind] ?? field : field;
      if (value && text(row[mapped]) !== value && (filter !== 'client_id' || !partyCases?.has(row.id))) return false;
    }
    if (q.get('important') && Boolean(row.is_important) !== (q.get('important') === 'true')) return false;
    if (q.get('pinned') && Boolean(row.is_pinned) !== (q.get('pinned') === 'true')) return false;
    if (q.get('favorite') && Boolean(row.favorite) !== (q.get('favorite') === 'true')) return false;
    return !term || ['title', 'case_title', 'case_number', 'cnr_number', 'document_name', 'full_name', 'name', 'description', 'content', 'citation']
      .some(field => text(row[field]).toLowerCase().includes(term));
  });
  const descending = tail === 'history' || (q.get('order') !== 'oldest' && !['hearing', 'task', 'planning_reminder'].includes(kind));
  const order = kind === 'case' ? q.get('sort') === 'filing' ? 'filing_date' : q.get('sort') === 'alphabetical' ? 'case_title' : 'updated_at' : kind === 'court' ? 'name' : dateField;
  items.sort((a, b) => (descending && order !== 'case_title' && order !== 'name' ? -1 : 1) * text(a[order]).localeCompare(text(b[order])));
  const offset = Math.max(0, Number(q.get('offset')) || 0);
  const limit = Math.min(300, Math.max(1, Number(q.get('limit')) || (id === 'calendar' ? 300 : arrayKinds.has(kind) ? 50 : 30)));
  const output = await Promise.all(items.slice(offset, offset + limit).map(row => withLinks(owner, kind, row)));
  const array = id !== 'search' && (arrayKinds.has(kind) || (parent && arraySub.has(kind))
    || id === 'upcoming' || id === 'calendar' || root === 'planning');
  if (tail === 'history' && parentKind !== 'case') return cached();
  return (array ? output : { items: output, total: items.length, offset, limit }) as T;
}

