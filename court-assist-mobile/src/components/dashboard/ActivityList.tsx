import { View } from 'react-native';
import { useTranslation } from 'react-i18next';
import { AppText } from '../common/AppText';
import { EmptyState } from '../common/EmptyState';
import { useTheme } from '../../theme/tokens';
import type { Activity } from '../../services/activity-api';
import { useAuthStore } from '../../store/auth-store';
import { formatTimestamp } from '../../utils/dates';

export function ActivityList({ items, emptyBody }: { items: Activity[]; emptyBody: string }) {
  const { t, i18n } = useTranslation(); const theme = useTheme(); const preferences = useAuthStore((state) => state.user?.preferences ?? null);
  if (!items.length) return <EmptyState title={t('dashboard.nothingYet')} body={emptyBody} />;
  return <View>{items.map((item, index) => <View key={item.id} style={{ flexDirection: 'row', gap: 12, paddingVertical: 12, borderBottomWidth: index === items.length - 1 ? 0 : 1, borderBottomColor: theme.colors.border }}>
    <View style={{ width: 8, height: 8, borderRadius: 4, marginTop: 9, backgroundColor: theme.colors.accent }} />
    <View style={{ flex: 1 }}><AppText style={{ fontWeight: '700' }}>{t(`activity.${item.activity_type}`, { defaultValue: item.title })}</AppText><AppText style={{ fontSize: 13, color: theme.colors.muted }}>{formatTimestamp(item.created_at, preferences, i18n.language)}</AppText></View>
  </View>)}</View>;
}
