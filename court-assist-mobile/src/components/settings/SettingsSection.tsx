import type { ReactNode } from 'react';
import { Pressable, View } from 'react-native';
import { ChevronRight } from 'lucide-react-native';
import { Card } from '../common/Card';
import { AppText } from '../common/AppText';
import { SectionHeader } from '../common/SectionHeader';
import { useTheme } from '../../theme/tokens';

export function SettingsSection({ title, children }: { title: string; children: ReactNode }) {
  return <><SectionHeader title={title} /><Card style={{ paddingVertical: 4 }}>{children}</Card></>;
}
export function SettingsRow({ label, detail, onPress }: { label: string; detail?: string; onPress?: () => void }) {
  const theme = useTheme();
  return <Pressable accessibilityRole={onPress ? 'button' : 'text'} disabled={!onPress} onPress={onPress} style={({ pressed }) => ({ minHeight: 56, paddingVertical: 11, flexDirection: 'row', alignItems: 'center', gap: 8, opacity: pressed ? 0.7 : 1 })}>
    <View style={{ flex: 1 }}><AppText style={{ fontWeight: '600' }}>{label}</AppText>{detail && <AppText style={{ color: theme.colors.muted, fontSize: 13 }}>{detail}</AppText>}</View>{onPress && <ChevronRight size={18} color={theme.colors.muted} />}
  </Pressable>;
}
