import { KeyboardAvoidingView, Platform, View } from 'react-native';
import { useTranslation } from 'react-i18next';
import { Scale } from 'lucide-react-native';
import { Screen } from './Screen';
import { AppText } from '../common/AppText';
import { useTheme } from '../../theme/tokens';

export function AuthScreen({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  const theme = useTheme();
  const { t } = useTranslation();
  return <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}><Screen><View style={{ paddingTop: 24, marginBottom: 36 }}><View style={{ width: 54, height: 54, borderRadius: 16, backgroundColor: theme.colors.navy, justifyContent: 'center', alignItems: 'center', marginBottom: 18 }}><Scale size={30} color={theme.colors.accent} /></View><AppText style={{ fontSize: 17, fontWeight: '700', color: theme.colors.navy }}>{t('appName')}</AppText></View><AppText style={{ fontSize: 30, lineHeight: 38, fontWeight: '800', marginBottom: 6 }}>{title}</AppText>{subtitle && <AppText style={{ color: theme.colors.muted, marginBottom: 32 }}>{subtitle}</AppText>}{children}</Screen></KeyboardAvoidingView>;
}
