import { useState } from 'react';
import { Alert, Platform, View } from 'react-native';
import { router } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../../store/auth-store';
import { networkRequest } from '../../services/api';
import type { Advocate } from '../../features/auth/types';
import { control, enable, clearRecords } from '../../features/sync/repository';
import { clearFiles } from '../../features/sync/files';
import { publishStatus, status, syncNow } from '../../features/sync/engine';
import { syncDatabase } from '../../features/sync/schema';
import { setBackgroundSync } from '../../features/sync/background';
import { useSyncState } from '../../features/sync/state';
import { Toggle } from '../../components/ai/Controls';
import { Screen } from '../../components/layout/Screen';
import { Button } from '../../components/common/Button';
import { AppText } from '../../components/common/AppText';
import { Card } from '../../components/common/Card';

type Run = { id: number; ran_at: string; duration: number; status: string; applied: number };

export default function SyncDashboard() {
  const { t } = useTranslation();
  const cache = useQueryClient();
  const user = useAuthStore(state => state.user)!;
  const state = useSyncState();
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const native = Platform.OS !== 'web';
  const data = useQuery({
    queryKey: ['sync-control', user.id], queryFn: () => control(user.id), enabled: native,
  });
  const runs = useQuery({
    queryKey: ['sync-runs', user.id], enabled: native && !!data.data?.enabled,
    queryFn: async () => (await syncDatabase()).getAllAsync<Run>('SELECT * FROM sync_runs WHERE owner=? ORDER BY id DESC LIMIT 10', user.id),
  });
  async function action(work: () => Promise<void>) {
    setBusy(true);
    setError(false);
    try { await work(); await data.refetch(); }
    catch { setError(true); }
    finally { setBusy(false); }
  }
  async function manual() {
    await syncNow(user.id, true);
    await runs.refetch();
    void cache.invalidateQueries();
  }
  function toggle(value: boolean) {
    if (value) {
      void action(async () => {
        const verified = await networkRequest<Advocate>('/users/me');
        if (verified.id !== user.id || useAuthStore.getState().user?.id !== user.id) throw new Error('account changed');
        const expiry = useAuthStore.getState().refreshExpiry;
        await enable(user.id, verified, expiry);
        await publishStatus(user.id);
        await setBackgroundSync(true).catch(() => {});
        await manual();
      });
      return;
    }
    Alert.alert(t('sync.disable'), t('sync.disableExplanation'), [
      { text: t('cancel'), style: 'cancel' },
      { text: t('sync.disable'), style: 'destructive', onPress: () => void action(async () => {
        const summary = await status(user.id);
        if (summary.pending || summary.conflicts || summary.failed || useSyncState.getState().running) throw new Error('pending changes');
        await clearRecords(user.id);
        clearFiles(user.id);
        await setBackgroundSync(false).catch(() => {});
        await publishStatus(user.id);
      }) },
    ]);
  }

  return <Screen title={t('sync.title')} subtitle={t('sync.description')} back>
    {!native ? <AppText>{t('sync.nativeOnly')}</AppText> : <>
      {error && <AppText>{t('sync.settingsError')}</AppText>}
      <Card>
        <AppText>{t(state.connected === false ? 'sync.offline' : state.connected === true ? 'sync.online' : 'sync.checking')}</AppText>
        <Toggle label={t('sync.enable')} value={!!data.data?.enabled} onChange={value => { if (!busy && !state.running) toggle(value); }} />
        <AppText>{t('sync.storageExplanation')}</AppText>
        {!!data.data?.enabled && <>
          <Toggle label={t('sync.automatic')} value={!!data.data.automatic} onChange={value => void action(async () => {
            await (await syncDatabase()).runAsync('UPDATE sync_control SET automatic=? WHERE owner=?', Number(value), user.id);
            await setBackgroundSync(value).catch(() => {});
          })} />
          <AppText>{t('sync.lastSync', { date: state.lastSync ? new Date(state.lastSync).toLocaleString() : t('sync.never') })}</AppText>
          <AppText>{t('sync.counts', { pending: state.pending, failed: state.failed, conflicts: state.conflicts })}</AppText>
          {state.phase && <AppText accessibilityLiveRegion="polite">{t(`sync.phases.${state.phase}`)}</AppText>}
          <Button label={t('sync.now')} loading={busy || state.running} disabled={state.connected === false}
            onPress={() => void action(manual)} />
        </>}
      </Card>
      {!!data.data?.enabled && <View style={{ gap: 8 }}>
        <Button label={t('sync.queue')} variant="secondary" onPress={() => router.push('/sync/queue')} />
        <Button label={t('sync.files')} variant="secondary" onPress={() => router.push('/sync/files')} />
        <AppText>{t('sync.history')}</AppText>
        {runs.data?.map(run => <Card key={run.id}>
          <AppText>{new Date(run.ran_at).toLocaleString()} · {t(`sync.runs.${run.status}`)}</AppText>
          <AppText>{t('sync.runStats', { applied: run.applied, seconds: Math.round(run.duration / 1000) })}</AppText>
        </Card>)}
      </View>}
    </>}
  </Screen>;
}

