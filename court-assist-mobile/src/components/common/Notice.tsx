import { View } from 'react-native';
import { AppText } from './AppText';
import { useTheme } from '../../theme/tokens';

export function Notice({ message, kind = 'error' }: { message: string; kind?: 'error' | 'success' }) {
  const theme = useTheme();
  return <View accessibilityRole="alert" style={{ padding: 14, borderRadius: theme.radius.md, backgroundColor: theme.colors.input, borderLeftWidth: 3, borderLeftColor: kind === 'error' ? theme.colors.danger : theme.colors.success, marginBottom: 16 }}><AppText style={{ color: kind === 'error' ? theme.colors.danger : theme.colors.success, fontSize: 14 }}>{message}</AppText></View>;
}
