import { View } from 'react-native';
import { useTheme } from '../../theme/tokens';

export function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  const theme = useTheme();
  return <View accessibilityLabel="Loading" style={{ gap: 12 }}>{Array.from({ length: rows }, (_, index) => <View key={index} style={{ height: index === 0 ? 92 : 68, borderRadius: theme.radius.lg, backgroundColor: theme.colors.input, borderWidth: 1, borderColor: theme.colors.border }} />)}</View>;
}
