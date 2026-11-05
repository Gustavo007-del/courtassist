import { useState } from 'react';
import { View, Pressable } from 'react-native';
import { router } from 'expo-router';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { AuthScreen } from '../../components/layout/AuthScreen';
import { TextField } from '../../components/common/TextField';
import { Button } from '../../components/common/Button';
import { Notice } from '../../components/common/Notice';
import { AppText } from '../../components/common/AppText';
import { authApi } from '../../features/auth/services/auth-api';
import { friendlyError } from '../../utils/errors';
import { setLanguage, type Language } from '../../i18n';
import { useTheme } from '../../theme/tokens';

const schema = z.object({ fullName: z.string().trim().min(2), identifier: z.string().trim().min(3), password: z.string().min(12).regex(/[A-Za-z]/).regex(/\d/), confirmPassword: z.string(), language: z.enum(['en', 'ml']) }).refine((data) => data.password === data.confirmPassword, { path: ['confirmPassword'] });
type Form = z.infer<typeof schema>;
export default function Register() {
  const { t } = useTranslation(); const theme = useTheme();
  const { control, handleSubmit, setValue, formState: { errors, isSubmitting } } = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { fullName: '', identifier: '', password: '', confirmPassword: '', language: 'en' } });
  const [error, setError] = useState<string | null>(null);
  const language = useWatch({ control, name: 'language' });
  const onSubmit = handleSubmit(async (data) => { setError(null); try { const identifier = data.identifier.trim(); await authApi.register({ full_name: data.fullName, ...(identifier.includes('@') ? { email: identifier } : { phone_number: identifier }), password: data.password, confirm_password: data.confirmPassword, preferred_language: data.language }); await setLanguage(data.language); router.replace({ pathname: '/(auth)/login', params: { registered: '1' } }); } catch (e) { setError(friendlyError(e)); } });
  return <AuthScreen title={t('auth.registerTitle')} subtitle={t('auth.registerDetail')}>
    {error && <Notice message={error} />}
    <Controller control={control} name="fullName" render={({ field }) => <TextField label={t('auth.fullName')} value={field.value} onChangeText={field.onChange} error={errors.fullName && t('validation.name')} autoCapitalize="words" autoComplete="name" />} />
    <Controller control={control} name="identifier" render={({ field }) => <TextField label={t('auth.identifier')} value={field.value} onChangeText={field.onChange} error={errors.identifier && t('validation.identifier')} />} />
    <Controller control={control} name="password" render={({ field }) => <TextField label={t('auth.password')} value={field.value} onChangeText={field.onChange} error={errors.password && t('validation.password')} password autoComplete="password" />} />
    <Controller control={control} name="confirmPassword" render={({ field }) => <TextField label={t('auth.confirmPassword')} value={field.value} onChangeText={field.onChange} error={errors.confirmPassword && t('validation.passwordMatch')} password />} />
    <AppText style={{ fontSize: 14, fontWeight: '600', marginBottom: 8 }}>{t('auth.language')}</AppText><View style={{ flexDirection: 'row', gap: 10, marginBottom: 24 }}>{(['en', 'ml'] as Language[]).map((code) => <Pressable key={code} accessibilityRole="radio" accessibilityState={{ selected: language === code }} onPress={() => setValue('language', code)} style={{ flex: 1, minHeight: 48, alignItems: 'center', justifyContent: 'center', borderRadius: 12, borderWidth: 1, borderColor: language === code ? theme.colors.navy : theme.colors.border, backgroundColor: theme.colors.surface }}><AppText>{t(code === 'en' ? 'settings.english' : 'settings.malayalam')}</AppText></Pressable>)}</View>
    <Button label={t('auth.createAccount')} onPress={onSubmit} loading={isSubmitting} /><View style={{ marginTop: 16 }}><Button label={t('auth.backToSignIn')} variant="text" onPress={() => router.back()} /></View>
  </AuthScreen>;
}
