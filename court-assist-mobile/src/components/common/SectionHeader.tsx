import { View } from 'react-native';
import { AppText } from './AppText';
import { useTheme } from '../../theme/tokens';

export function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  const theme = useTheme();
  return <View style={{ marginTop: 28, marginBottom: 14 }}><AppText style={{ fontSize: 20, fontWeight: '800' }}>{title}</AppText>{subtitle && <AppText style={{ color: theme.colors.muted, fontSize: 13, marginTop: 3 }}>{subtitle}</AppText>}</View>;
}
