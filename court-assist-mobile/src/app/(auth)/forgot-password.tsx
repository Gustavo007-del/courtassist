import { useState } from 'react';
import { router } from 'expo-router';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { AuthScreen } from '../../components/layout/AuthScreen';
import { TextField } from '../../components/common/TextField';
import { Button } from '../../components/common/Button';
import { Notice } from '../../components/common/Notice';
import { authApi } from '../../features/auth/services/auth-api';
import { friendlyError } from '../../utils/errors';

const schema = z.object({ email: z.email() });
export default function ForgotPassword() {
  const { t } = useTranslation();
  const { control, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema), defaultValues: { email: '' } });
  const [notice, setNotice] = useState<{ message: string; kind: 'error' | 'success' } | null>(null);
  const onSubmit = handleSubmit(async ({ email }) => { try { await authApi.forgot(email); setNotice({ message: t('auth.forgotSuccess'), kind: 'success' }); } catch (e) { setNotice({ message: friendlyError(e), kind: 'error' }); } });
  return <AuthScreen title={t('auth.forgotTitle')} subtitle={t('auth.forgotDetail')}>{notice && <Notice {...notice} />}<Controller control={control} name="email" render={({ field }) => <TextField label={t('auth.email')} value={field.value} onChangeText={field.onChange} error={errors.email && t('validation.email')} keyboardType="email-address" autoComplete="email" />} /><Button label={t('auth.sendLink')} onPress={onSubmit} loading={isSubmitting} /><Button label={t('auth.backToSignIn')} variant="text" onPress={() => router.back()} /></AuthScreen>;
}
