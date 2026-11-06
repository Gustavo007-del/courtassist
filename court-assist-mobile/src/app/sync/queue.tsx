import { useState } from 'react';
import { Alert } from 'react-native';
import { router } from 'expo-router';
import { randomUUID } from 'expo-crypto';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../../store/auth-store';
import { useSyncState } from '../../features/sync/state';
import { outcome, queue, retry } from '../../features/sync/repository';
import { publishStatus, resolve, syncNow } from '../../features/sync/engine';
import { ApiError, networkRequest } from '../../services/api';
import { finishUpload } from '../../features/sync/files';
import type { Change, Data, QueueItem } from '../../features/sync/types';
import { Screen } from '../../components/layout/Screen';
import { Button } from '../../components/common/Button';
import { AppText } from '../../components/common/AppText';
import { Card } from '../../components/common/Card';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { ErrorState } from '../../components/common/ErrorState';
import { TextField } from '../../components/common/TextField';

const display = (value: unknown) => value == null ? '—' : typeof value === 'string' ? value : JSON.stringify(value, null, 2);

function Conflict({ owner, item, refresh }: { owner: string; item: QueueItem; refresh: () => void }) {
  const { t } = useTranslation();
  const [edited, setEdited] = useState<Data>({ ...item.operation.payload });
  const [merge, setMerge] = useState(false);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const connected = useSyncState(state => state.connected);
  const running = useSyncState(state => state.running);
  const server = item.result?.server?.record;
  const action = item.operation.action;
  const compare = Object.keys(item.operation.payload).filter(key => !key.endsWith('_id') && key !== 'checksum');
  const visible = compare.length ? compare : ['title', 'case_title', 'document_name', 'updated_at'].filter(key => server?.[key] != null);
  const allowMerge = item.kind !== 'payment' && compare.length > 0 && (
    !item.result?.server?.deleted || (item.result?.error === 'schedule_conflict' && action === 'create')
  );
  const choose = (strategy: 'server' | 'local' | 'merge') => Alert.alert(t('sync.resolve'), t(`sync.confirm.${strategy}`), [
    { text: t('cancel'), style: 'cancel' },
    { text: t('sync.confirmAction'), onPress: async () => {
      setError(false);
      setBusy(true);
      try {
        await resolve(owner, item, strategy, randomUUID(), strategy === 'merge' ? edited : undefined);
      } catch { setError(true); }
      finally { setBusy(false); refresh(); }
    } },
  ]);
  return <>
    {error && <AppText>{t('sync.resolveError')}</AppText>}
    {item.result?.server?.deleted && <AppText>{t('sync.serverDeleted')}</AppText>}
    <AppText>{t('sync.reviewDescription')}</AppText>
    {visible.map(key => <Card key={key}>
      <AppText style={{ fontWeight: '700' }}>{t(`sync.fields.${key}`, { defaultValue: key.replaceAll('_', ' ') })}</AppText>
      {key in item.operation.payload && <AppText selectable>{t('sync.localValue')} · {display(item.operation.payload[key])}</AppText>}
      <AppText selectable>{t('sync.serverValue')} · {display(server?.[key])}</AppText>
      {merge && key in edited && (typeof edited[key] === 'string' || typeof item.operation.payload[key] === 'string') &&
        <TextField label={t('sync.mergePayload')} multiline value={String(edited[key] ?? '')}
          onChangeText={value => setEdited(previous => ({ ...previous, [key]: value }))} />}
      {merge && action === 'update' && <Button variant="text" label={t(key in edited ? 'sync.serverValue' : 'sync.localValue')}
        onPress={() => setEdited(previous => {
          const next = { ...previous };
          if (key in next) delete next[key];
          else next[key] = item.operation.payload[key];
          return next;
        })} />}
    </Card>)}
    <Button label={t('sync.keepServer')} variant="secondary" disabled={connected === false || running} loading={busy} onPress={() => choose('server')} />
    {item.kind !== 'payment' && !item.result?.server?.deleted &&
      <Button label={t('sync.keepLocal')} variant="secondary" disabled={connected === false || running} loading={busy} onPress={() => choose('local')} />}
    {allowMerge && <Button label={t('sync.merge')} variant="text" onPress={() => setMerge(!merge)} />}
    {allowMerge && merge && <Button label={t('sync.applyMerge')} disabled={connected === false || running} loading={busy} onPress={() => choose('merge')} />}
  </>;
}

export default function SyncQueue() {
  const { t } = useTranslation();
  const owner = useAuthStore(state => state.user!.id);
  const cache = useQueryClient();
  const state = useSyncState();
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState<string>();
  const [error, setError] = useState(false);
  const query = useQuery({ queryKey: ['sync-queue', owner, offset], queryFn: () => queue(owner, false, 20, offset),
    refetchInterval: state.running ? 2000 : false });
  const refresh = () => { void query.refetch(); void cache.invalidateQueries(); };
  const discard = (item: QueueItem) => Alert.alert(t('sync.discard'), t('sync.discardExplanation'), [
    { text: t('cancel'), style: 'cancel' },
    { text: t('sync.discard'), style: 'destructive', onPress: () => void (async () => {
      try {
        let current: Change;
        try { current = await networkRequest<Change>(`/sync/records/${item.kind}/${item.entity}`); }
        catch (caught) {
          if (!(caught instanceof ApiError) || caught.status !== 404) throw caught;
          current = { kind: item.kind, id: item.entity, revision: item.operation.base_revision, deleted: true, record: null };
        }
        if (useAuthStore.getState().user?.id !== owner) return;
        await outcome(owner, item, 'discarded', { id: item.id, status: 'applied', server: current });
        if (item.upload) finishUpload(owner, item.upload);
        await publishStatus(owner);
        refresh();
      } catch { setError(true); }
    })() },
  ]);
  return <Screen title={t('sync.queue')} back onRefresh={refresh} refreshing={query.isRefetching}>
    {error && <AppText>{t('sync.resolveError')}</AppText>}
    {query.isPending ? <LoadingSkeleton /> : query.isError
      ? <ErrorState message={t('work.error')} retry={() => void query.refetch()} />
      : <>
        {!query.data.length && <AppText>{t('sync.empty')}</AppText>}
        {query.data.map(item => <Card key={item.id}>
          <AppText>{t(`sync.kinds.${item.kind}`, { defaultValue: item.kind })} · {t(`sync.states.${item.status}`)}</AppText>
          <AppText>{new Date(item.created_at).toLocaleString()}</AppText>
          {item.upload && <AppText>{t('sync.uploadPending')}</AppText>}
          {item.error && <AppText>{t(`sync.errors.${item.error}`, { defaultValue: t('sync.operationError') })}</AppText>}
          {item.status === 'conflict' && <Button label={t('sync.resolve')} variant="secondary" onPress={() => setOpen(open === item.id ? undefined : item.id)} />}
          {item.status === 'conflict' && open === item.id && <Conflict owner={owner} item={item} refresh={refresh} />}
          {['failed', 'retry', 'blocked'].includes(item.status) && <>
            <Button label={t('sync.retry')} variant="secondary" disabled={state.running || state.connected === false}
              onPress={() => void retry(owner, item.id).then(() => syncNow(owner, true)).then(refresh).catch(() => setError(true))} />
            <Button label={t('sync.discard')} variant="text" disabled={state.running || state.connected === false} onPress={() => discard(item)} />
          </>}
        </Card>)}
        {offset > 0 && <Button label={t('ai.previous')} variant="text" onPress={() => setOffset(Math.max(0, offset - 20))} />}
        {query.data.length === 20 && <Button label={t('ai.next')} variant="text" onPress={() => setOffset(offset + 20)} />}
      </>}
    <Button label={t('sync.title')} variant="text" onPress={() => router.replace('/sync')} />
  </Screen>;
}

