import { Text, type TextProps } from 'react-native';
import { useTheme } from '../../theme/tokens';

export function AppText({ style, ...props }: TextProps) {
  const theme = useTheme();
  return <Text {...props} style={[{ color: theme.colors.text, fontSize: theme.type.body, lineHeight: 24 }, style]} />;
}
