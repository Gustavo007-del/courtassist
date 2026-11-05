import { useState } from 'react';
import { Switch, View } from 'react-native';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Card } from '../../components/common/Card';
import { AppText } from '../../components/common/AppText';
import { Notice } from '../../components/common/Notice';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { ErrorState } from '../../components/common/ErrorState';
import { preferencesApi } from '../../services/preferences-api';
import { useAuthStore } from '../../store/auth-store';
import { useTheme } from '../../theme/tokens';
import { friendlyError } from '../../utils/errors';
import type { Preferences } from '../../features/auth/types';

const fields: { key: keyof Pick<Preferences, 'hearing_reminders' | 'task_reminders' | 'appointment_reminders' | 'payment_reminders' | 'daily_summary'>; label: string }[] = [
  { key: 'hearing_reminders', label: 'settings2.hearingReminders' }, { key: 'task_reminders', label: 'settings2.taskReminders' },
  { key: 'appointment_reminders', label: 'settings2.appointmentReminders' }, { key: 'payment_reminders', label: 'settings2.paymentReminders' },
  { key: 'daily_summary', label: 'settings2.dailySummary' },
];
export default function NotificationSettings() {
  const { t } = useTranslation(); const theme = useTheme(); const client = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const { data, isPending, isError, error, refetch } = useQuery({ queryKey: ['preferences', user?.id], queryFn: preferencesApi.get, enabled: !!user });
  const [busy, setBusy] = useState(false); const [saveError, setSaveError] = useState<string | null>(null);
  const change = async (key: typeof fields[number]['key'], value: boolean) => {
    setBusy(true); setSaveError(null);
    try { const preferences = await preferencesApi.update({ [key]: value }); client.setQueryData(['preferences', user?.id], preferences); if (user) useAuthStore.setState({ user: { ...user, preferences } }); }
    catch (caught) { setSaveError(friendlyError(caught)); } finally { setBusy(false); }
  };
  return <Screen title={t('settings2.notifications')} subtitle={t('settings2.notificationsDetail')}>
    {saveError && <Notice message={saveError} />}
    {isPending ? <LoadingSkeleton rows={2} /> : isError ? <ErrorState message={friendlyError(error)} retry={() => { void refetch(); }} /> : data && <Card>{fields.map(({ key, label }) => <View key={key} style={{ minHeight: 60, flexDirection: 'row', alignItems: 'center', gap: 12, borderBottomWidth: 1, borderBottomColor: theme.colors.border }}><AppText style={{ flex: 1 }}>{t(label)}</AppText><Switch value={data[key]} disabled={busy} onValueChange={(value) => { void change(key, value); }} trackColor={{ true: theme.colors.accent }} /></View>)}</Card>}
    <AppText style={{ color: theme.colors.muted, fontSize: 13, marginTop: 16 }}>{t('dashboard.notificationsFuture')}</AppText>
  </Screen>;
}
