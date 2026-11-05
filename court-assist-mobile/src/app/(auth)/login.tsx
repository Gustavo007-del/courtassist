import { useState } from 'react';
import { View } from 'react-native';
import { Link, router, useLocalSearchParams } from 'expo-router';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { AuthScreen } from '../../components/layout/AuthScreen';
import { TextField } from '../../components/common/TextField';
import { Button } from '../../components/common/Button';
import { Notice } from '../../components/common/Notice';
import { AppText } from '../../components/common/AppText';
import { authApi } from '../../features/auth/services/auth-api';
import { useAuthStore } from '../../store/auth-store';
import { friendlyError } from '../../utils/errors';
import { useTheme } from '../../theme/tokens';
import { setLanguage } from '../../i18n';
import { useThemeStore } from '../../store/theme-store';

const schema = z.object({ identifier: z.string().min(3), password: z.string().min(1) });
type Form = z.infer<typeof schema>;
export default function Login() {
  const { t } = useTranslation(); const theme = useTheme();
  const { registered } = useLocalSearchParams<{ registered?: string }>();
  const { control, handleSubmit, formState: { errors, isSubmitting } } = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { identifier: '', password: '' } });
  const [error, setError] = useState<string | null>(null);
  const onSubmit = handleSubmit(async ({ identifier, password }) => { setError(null); try { const tokens = await authApi.login(identifier.trim(), password); await useAuthStore.getState().setTokens(tokens); await setLanguage(tokens.user.preferred_language).catch(() => {}); if (tokens.user.preferences) await useThemeStore.getState().setMode(tokens.user.preferences.theme).catch(() => {}); router.replace('/(tabs)'); } catch (e) { setError(friendlyError(e)); } });
  return <AuthScreen title={t('auth.welcome')} subtitle={t('auth.welcomeDetail')}>
    {registered === '1' && <Notice message={t('auth.registered')} kind="success" />}
    {error && <Notice message={error} />}
    <Controller control={control} name="identifier" render={({ field }) => <TextField label={t('auth.identifier')} value={field.value} onChangeText={field.onChange} error={errors.identifier && t('validation.identifier')} autoComplete="email" />} />
    <Controller control={control} name="password" render={({ field }) => <TextField label={t('auth.password')} value={field.value} onChangeText={field.onChange} error={errors.password && t('validation.required')} password autoComplete="password" />} />
    <View style={{ alignItems: 'flex-end', marginBottom: 24 }}><Link href="/(auth)/forgot-password"><AppText style={{ color: theme.colors.navy, fontWeight: '700' }}>{t('auth.forgot')}</AppText></Link></View>
    <Button label={t('auth.signIn')} onPress={onSubmit} loading={isSubmitting} />
    <View style={{ marginTop: 16 }}><Button label={t('auth.createAccount')} onPress={() => router.push('/(auth)/register')} variant="text" /></View>
  </AuthScreen>;
}
