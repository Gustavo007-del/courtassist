import { useState } from 'react';
import { router } from 'expo-router';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { TextField } from '../../components/common/TextField';
import { Button } from '../../components/common/Button';
import { Notice } from '../../components/common/Notice';
import { authApi } from '../../features/auth/services/auth-api';
import { useAuthStore } from '../../store/auth-store';
import { useAppStore } from '../../store/app-store';
import { ApiError } from '../../services/api';
import { friendlyError } from '../../utils/errors';

const schema = z.object({ current: z.string().min(1), password: z.string().min(12).regex(/[A-Za-z]/).regex(/\d/), confirm: z.string() }).refine((data) => data.password === data.confirm, { path: ['confirm'] });
type Form = z.infer<typeof schema>;
export default function ChangePassword() {
  const { t } = useTranslation(); const client = useQueryClient();
  const { control, handleSubmit, formState: { errors, isSubmitting } } = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { current: '', password: '', confirm: '' } });
  const [error, setError] = useState<string | null>(null);
  const save = handleSubmit(async (values) => {
    setError(null);
    try { await authApi.changePassword(values.current, values.password, values.confirm); await useAuthStore.getState().clear(); client.clear(); useAppStore.getState().showToast(t('security.passwordChanged')); router.replace('/(auth)/login'); }
    catch (caught) { setError(caught instanceof ApiError && caught.status === 400 ? t('security.currentIncorrect') : friendlyError(caught)); }
  });
  return <Screen title={t('security.changePassword')}>
    {error && <Notice message={error} />}
    <Controller control={control} name="current" render={({ field }) => <TextField label={t('security.currentPassword')} value={field.value} onChangeText={field.onChange} error={errors.current && t('validation.required')} password />} />
    <Controller control={control} name="password" render={({ field }) => <TextField label={t('security.newPassword')} value={field.value} onChangeText={field.onChange} error={errors.password && t('validation.password')} password />} />
    <Controller control={control} name="confirm" render={({ field }) => <TextField label={t('auth.confirmPassword')} value={field.value} onChangeText={field.onChange} error={errors.confirm && t('validation.passwordMatch')} password />} />
    <Button label={t('security.changePassword')} onPress={save} loading={isSubmitting} /><Button label={t('cancel')} variant="text" onPress={() => router.back()} />
  </Screen>;
}
