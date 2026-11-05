import { Pressable, View } from 'react-native';
import { AppText } from './AppText';
import { useTheme } from '../../theme/tokens';

export function ChoiceChips<T extends string>({ value, options, onChange }: { value: T; options: { value: T; label: string }[]; onChange: (value: T) => void }) {
  const theme = useTheme();
  return <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>{options.map((option) => {
    const selected = option.value === value;
    return <Pressable key={option.value} accessibilityRole="radio" accessibilityState={{ selected }} onPress={() => onChange(option.value)} style={{ paddingHorizontal: 13, paddingVertical: 9, borderRadius: 12, borderWidth: 1, borderColor: selected ? theme.colors.accent : theme.colors.border, backgroundColor: selected ? theme.colors.input : theme.colors.surface }}><AppText style={{ fontSize: 13, fontWeight: selected ? '700' : '500' }}>{option.label}</AppText></Pressable>;
  })}</View>;
}
