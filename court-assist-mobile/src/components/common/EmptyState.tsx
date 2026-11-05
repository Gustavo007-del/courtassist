import { View } from 'react-native';
import { AppText } from './AppText';
import { useTheme } from '../../theme/tokens';

export function EmptyState({ title, body }: { title: string; body: string }) {
  const theme = useTheme();
  return <View style={{ alignItems: 'center', padding: 32, gap: 8 }}><View style={{ width: 52, height: 4, backgroundColor: theme.colors.accent, borderRadius: 2, marginBottom: 12 }} /><AppText style={{ fontSize: 20, fontWeight: '700', textAlign: 'center' }}>{title}</AppText><AppText style={{ color: theme.colors.muted, textAlign: 'center' }}>{body}</AppText></View>;
}
