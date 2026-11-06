import { Pressable } from 'react-native';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { useSyncState } from '../../features/sync/state';
import { AppText } from './AppText';
import { useTheme } from '../../theme/tokens';

export function SyncIndicator({ recordPending = false }: { recordPending?: boolean }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const enabled = useSyncState(state => state.enabled);
  const connected = useSyncState(state => state.connected);
  const pending = useSyncState(state => state.pending + state.conflicts + state.failed);
  if (!enabled || (connected !== false && pending === 0 && !recordPending)) return null;
  return <Pressable accessibilityRole="button" onPress={() => router.push(recordPending ? '/sync/queue' : '/sync')} style={{ padding: 10, marginBottom: 12, borderRadius: 8, backgroundColor: theme.colors.input }}>
    <AppText>{connected === false ? t('sync.offline') : t('sync.online')}{pending > 0 ? ' · ' + t('sync.unsynced', { count: pending }) : ''}</AppText>
    {recordPending && <AppText>{t('sync.recordPending')}</AppText>}
  </Pressable>;
}

