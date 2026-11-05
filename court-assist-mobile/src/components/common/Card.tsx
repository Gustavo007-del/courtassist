import { View, type ViewProps } from 'react-native';
import { useTheme } from '../../theme/tokens';

export function Card({ style, ...props }: ViewProps) {
  const theme = useTheme();
  return <View {...props} style={[{ backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1, borderRadius: theme.radius.lg, padding: theme.spacing.lg, ...theme.shadow }, style]} />;
}
