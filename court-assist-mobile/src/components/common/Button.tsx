import { ActivityIndicator, Pressable, StyleSheet } from 'react-native';
import { AppText } from './AppText';
import { useTheme } from '../../theme/tokens';

export function Button({ label, onPress, loading = false, variant = 'primary', disabled = false }: { label: string; onPress: () => void; loading?: boolean; variant?: 'primary' | 'secondary' | 'text'; disabled?: boolean }) {
  const theme = useTheme();
  const primary = variant === 'primary';
  return <Pressable accessibilityRole="button" accessibilityLabel={label} disabled={disabled || loading} onPress={onPress} style={({ pressed }) => [styles.button, { backgroundColor: primary ? theme.colors.navy : variant === 'secondary' ? theme.colors.input : 'transparent', borderRadius: theme.radius.md, opacity: disabled || loading ? 0.5 : pressed ? 0.8 : 1 }]}>
    {loading ? <ActivityIndicator color={primary ? theme.colors.surface : theme.colors.navy} /> : <AppText style={{ color: primary ? theme.colors.surface : theme.colors.navy, fontWeight: '700', textAlign: 'center' }}>{label}</AppText>}
  </Pressable>;
}
const styles = StyleSheet.create({ button: { minHeight: 52, paddingHorizontal: 20, paddingVertical: 14, alignItems: 'center', justifyContent: 'center' } });
