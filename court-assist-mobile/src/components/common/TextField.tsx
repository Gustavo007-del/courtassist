import { useState } from 'react';
import { Pressable, TextInput, View } from 'react-native';
import { Eye, EyeOff } from 'lucide-react-native';
import { useTranslation } from 'react-i18next';
import { AppText } from './AppText';
import { useTheme } from '../../theme/tokens';

export function TextField({ label, value, onChangeText, error, password = false, keyboardType = 'default', autoCapitalize = 'none', autoComplete, multiline = false }: { label: string; value?: string; onChangeText: (value: string) => void; error?: string; password?: boolean; keyboardType?: 'default' | 'email-address' | 'phone-pad' | 'numeric'; autoCapitalize?: 'none' | 'words'; autoComplete?: 'email' | 'password' | 'name' | 'tel'; multiline?: boolean }) {
  const theme = useTheme();
  const { t } = useTranslation();
  const [visible, setVisible] = useState(false);
  return <View style={{ gap: 7, marginBottom: 16 }}>
    <AppText style={{ fontSize: 14, fontWeight: '600' }}>{label}</AppText>
    <View style={{ flexDirection: 'row', alignItems: 'center', borderColor: error ? theme.colors.danger : theme.colors.border, borderWidth: 1, borderRadius: theme.radius.md, backgroundColor: theme.colors.surface, minHeight: 54 }}>
      <TextInput accessibilityLabel={label} value={value} onChangeText={onChangeText} secureTextEntry={password && !visible} keyboardType={keyboardType} autoCapitalize={autoCapitalize} autoComplete={autoComplete} multiline={multiline} placeholderTextColor={theme.colors.muted} style={{ flex: 1, paddingHorizontal: 16, fontSize: 16, color: theme.colors.text, minHeight: multiline ? 90 : 52, textAlignVertical: multiline ? 'top' : 'center' }} />
      {password && <Pressable accessibilityRole="button" accessibilityLabel={t(visible ? 'auth.hidePassword' : 'auth.showPassword')} onPress={() => setVisible(!visible)} style={{ padding: 14 }}>
        {visible ? <EyeOff color={theme.colors.muted} size={21} /> : <Eye color={theme.colors.muted} size={21} />}
      </Pressable>}
    </View>
    {error && <AppText style={{ color: theme.colors.danger, fontSize: 13 }}>{error}</AppText>}
  </View>;
}
