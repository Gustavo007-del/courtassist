import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { AuthScreen } from '../components/layout/AuthScreen';
import { TextField } from '../components/common/TextField';
import { Button } from '../components/common/Button';
import { Notice } from '../components/common/Notice';
import { authApi } from '../features/auth/services/auth-api';
import { friendlyError } from '../utils/errors';

const schema = z.object({ password: z.string().min(12).regex(/[A-Za-z]/).regex(/\d/), confirmPassword: z.string() }).refine((data) => data.password === data.confirmPassword, { path: ['confirmPassword'] });
export default function ResetPassword() {
  const { t } = useTranslation(); const { token } = useLocalSearchParams<{ token?: string }>();
  const { control, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { password: '', confirmPassword: '' } });
  const [notice, setNotice] = useState<{ message: string; kind: 'error' | 'success' } | null>(null);
  const onSubmit = handleSubmit(async (data) => { if (!token) return setNotice({ message: t('error'), kind: 'error' }); try { await authApi.reset(token, data.password, data.confirmPassword); setNotice({ message: t('auth.resetSuccess'), kind: 'success' }); } catch (e) { setNotice({ message: friendlyError(e), kind: 'error' }); } });
  return <AuthScreen title={t('auth.resetTitle')}>{notice && <Notice {...notice} />}<Controller control={control} name="password" render={({ field }) => <TextField label={t('auth.password')} value={field.value} onChangeText={field.onChange} error={errors.password && t('validation.password')} password />} /><Controller control={control} name="confirmPassword" render={({ field }) => <TextField label={t('auth.confirmPassword')} value={field.value} onChangeText={field.onChange} error={errors.confirmPassword && t('validation.passwordMatch')} password />} /><Button label={t('auth.resetAction')} onPress={onSubmit} loading={isSubmitting} /><Button label={t('auth.backToSignIn')} variant="text" onPress={() => router.replace('/(auth)/login')} /></AuthScreen>;
}
