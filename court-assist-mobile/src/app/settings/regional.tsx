import { useState } from 'react';
import { View } from 'react-native';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Card } from '../../components/common/Card';
import { TextField } from '../../components/common/TextField';
import { Button } from '../../components/common/Button';
import { AppText } from '../../components/common/AppText';
import { Notice } from '../../components/common/Notice';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { ErrorState } from '../../components/common/ErrorState';
import { SectionHeader } from '../../components/common/SectionHeader';
import { preferencesApi } from '../../services/preferences-api';
import { useAuthStore } from '../../store/auth-store';
import { useAppStore } from '../../store/app-store';
import { friendlyError } from '../../utils/errors';
import type { Preferences } from '../../features/auth/types';

export default function RegionalSettings() {
  const { t } = useTranslation(); const client = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const { data, isPending, isError, error, refetch } = useQuery({ queryKey: ['preferences', user?.id], queryFn: preferencesApi.get, enabled: !!user });
  const [draft, setDraft] = useState<Partial<Pick<Preferences, 'timezone' | 'date_format' | 'time_format'>>>({});
  const timezone = draft.timezone ?? data?.timezone ?? 'Asia/Kolkata';
  const dateFormat = draft.date_format ?? data?.date_format ?? 'DD/MM/YYYY';
  const timeFormat = draft.time_format ?? data?.time_format ?? '12';
  const [busy, setBusy] = useState(false); const [saveError, setSaveError] = useState<string | null>(null);
  const save = async () => {
    setBusy(true); setSaveError(null);
    try {
      const preferences = await preferencesApi.update({ timezone: timezone.trim(), date_format: dateFormat, time_format: timeFormat });
      client.setQueryData(['preferences', user?.id], preferences);
      setDraft({});
      if (user) { const updated = { ...user, preferences }; useAuthStore.setState({ user: updated }); client.setQueryData(['me', user.id], updated); }
      await client.invalidateQueries({ queryKey: ['dashboard'] });
      useAppStore.getState().showToast(t('settings2.saved'));
    } catch (caught) { setSaveError(friendlyError(caught)); } finally { setBusy(false); }
  };
  return <Screen title={t('settings2.regional')} subtitle={t('settings2.regionalDetail')}>
    {saveError && <Notice message={saveError} />}
    {isPending ? <LoadingSkeleton rows={2} /> : isError ? <ErrorState message={friendlyError(error)} retry={() => { void refetch(); }} /> : data && <>
      <Card><TextField label={t('profile2.timezone')} value={timezone} onChangeText={(value) => setDraft((current) => ({ ...current, timezone: value }))} /><AppText style={{ fontSize: 13 }}>{t('settings2.invalidTimezone')}</AppText></Card>
      <SectionHeader title={t('profile2.dateFormat')} /><Card><View style={{ gap: 8 }}>{(['DD/MM/YYYY', 'MM/DD/YYYY', 'YYYY-MM-DD'] as const).map((value) => <Button key={value} label={`${dateFormat === value ? '✓  ' : ''}${value}`} variant="secondary" onPress={() => setDraft((current) => ({ ...current, date_format: value }))} />)}</View></Card>
      <SectionHeader title={t('profile2.timeFormat')} /><Card><View style={{ gap: 8 }}>{(['12', '24'] as const).map((value) => <Button key={value} label={`${timeFormat === value ? '✓  ' : ''}${value}`} variant="secondary" onPress={() => setDraft((current) => ({ ...current, time_format: value }))} />)}</View></Card>
      <View style={{ marginTop: 24 }}><Button label={t('save')} loading={busy} onPress={() => { void save(); }} /></View>
    </>}
  </Screen>;
}
