import { Pressable } from 'react-native';
import { AppText } from '../common/AppText';
import { useTheme } from '../../theme/tokens';

export function SummaryCard({ label, count, available, onPress }: { label: string; count: number | null; available: boolean; onPress?: () => void }) {
  const theme = useTheme();
  return <Pressable onPress={onPress} disabled={!available || !onPress} style={{ width: '48%', minHeight: 106, padding: 16, borderRadius: theme.radius.lg, backgroundColor: theme.colors.surface, borderWidth: 1, borderColor: theme.colors.border, justifyContent: 'space-between' }}>
    <AppText style={{ color: theme.colors.muted, fontSize: 13, lineHeight: 18 }}>{label}</AppText>
    <AppText style={{ fontSize: available ? 27 : 17, fontWeight: '800', color: available ? theme.colors.navy : theme.colors.muted }}>{available ? count ?? 0 : '—'}</AppText>
  </Pressable>;
}
