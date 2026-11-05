import { useEffect, useState } from 'react';
import { Alert, Pressable, View } from 'react-native';
import { router, usePreventRemove } from 'expo-router';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Card } from '../../components/common/Card';
import { TextField } from '../../components/common/TextField';
import { Button } from '../../components/common/Button';
import { Notice } from '../../components/common/Notice';
import { AppText } from '../../components/common/AppText';
import { SectionHeader } from '../../components/common/SectionHeader';
import { ImagePickerField, type PickedImage } from '../../components/profile/ImagePickerField';
import { profileApi, type ProfileUpdate } from '../../services/profile-api';
import { useAuthStore } from '../../store/auth-store';
import { useAppStore } from '../../store/app-store';
import { useTheme } from '../../theme/tokens';
import { friendlyError } from '../../utils/errors';
import type { Advocate } from '../../features/auth/types';

const validDate = (value: string) => !value || /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(`${value}T00:00:00Z`)) && new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value && value <= new Date().toISOString().slice(0, 10);
const optionalEmail = z.string().refine((value) => !value || z.email().safeParse(value).success);
const optionalPhone = z.string().refine((value) => !value || /^\+?[0-9 ()-]{8,22}$/.test(value));
const schema = z.object({
  full_name: z.string().trim().min(2), email: optionalEmail, phone_number: optionalPhone,
  date_of_birth: z.string().refine(validDate), gender: z.string(), address: z.string().max(500),
  city: z.string().max(120), district: z.string().max(120), state: z.string().max(120),
  pin_code: z.string().refine((value) => !value || /^\d{6}$/.test(value)),
  enrollment_number: z.string().max(100), bar_council: z.string().max(160),
  enrollment_date: z.string().refine(validDate), professional_designation: z.string().max(120),
  years_of_experience: z.string().refine((value) => !value || /^\d{1,2}$/.test(value) && Number(value) <= 80),
  office_name: z.string().max(160), office_address: z.string().max(500), office_phone: optionalPhone,
  professional_email: optionalEmail, areas_of_practice: z.string().refine((value) => !value || value.split(',').length <= 12 && value.split(',').every((part) => !!part.trim() && part.trim().length <= 80)),
}).refine((data) => !!data.email.trim() || !!data.phone_number.trim(), { path: ['email'] });
type Form = z.infer<typeof schema>;
const emptyForm: Form = { full_name: '', email: '', phone_number: '', date_of_birth: '', gender: '', address: '', city: '', district: '', state: '', pin_code: '', enrollment_number: '', bar_council: '', enrollment_date: '', professional_designation: '', years_of_experience: '', office_name: '', office_address: '', office_phone: '', professional_email: '', areas_of_practice: '' };
function toForm(user: Advocate): Form {
  const values = { ...emptyForm };
  for (const key of Object.keys(values) as (keyof Form)[]) {
    if (key === 'areas_of_practice') values[key] = user.areas_of_practice.join(', ');
    else if (key === 'years_of_experience') values[key] = user.years_of_experience?.toString() ?? '';
    else values[key] = (user[key] as string | null) ?? '';
  }
  return values;
}
const personal: { name: keyof Form; label: string; keyboard?: 'email-address' | 'phone-pad' | 'numeric'; multiline?: boolean }[] = [
  { name: 'full_name', label: 'auth.fullName' }, { name: 'email', label: 'auth.email', keyboard: 'email-address' },
  { name: 'phone_number', label: 'profile2.phoneNumber', keyboard: 'phone-pad' }, { name: 'date_of_birth', label: 'profile2.dateOfBirth' },
  { name: 'address', label: 'profile2.address', multiline: true }, { name: 'city', label: 'profile2.city' },
  { name: 'district', label: 'profile2.district' }, { name: 'state', label: 'profile2.state' }, { name: 'pin_code', label: 'profile2.pinCode', keyboard: 'numeric' },
];
const professional: typeof personal = [
  { name: 'enrollment_number', label: 'profile.enrollment' }, { name: 'bar_council', label: 'profile.barCouncil' },
  { name: 'enrollment_date', label: 'profile2.enrollmentDate' }, { name: 'professional_designation', label: 'profile2.designation' },
  { name: 'years_of_experience', label: 'profile2.experience', keyboard: 'numeric' }, { name: 'office_name', label: 'profile2.officeName' },
  { name: 'office_address', label: 'profile2.officeAddress', multiline: true }, { name: 'office_phone', label: 'profile2.officePhone', keyboard: 'phone-pad' },
  { name: 'professional_email', label: 'profile2.professionalEmail', keyboard: 'email-address' }, { name: 'areas_of_practice', label: 'profile2.areas' },
];

export default function EditProfile() {
  const { t } = useTranslation(); const theme = useTheme(); const client = useQueryClient();
  const fallback = useAuthStore((state) => state.user);
  const { data } = useQuery({ queryKey: ['me', fallback?.id], queryFn: profileApi.me, enabled: !!fallback });
  const user = data ?? fallback;
  const { control, handleSubmit, reset, formState: { errors, isSubmitting, isDirty } } = useForm<Form>({ resolver: zodResolver(schema), defaultValues: user ? toForm(user) : emptyForm });
  const [photo, setPhoto] = useState<PickedImage | null>(null);
  const [signature, setSignature] = useState<PickedImage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [allowLeave, setAllowLeave] = useState(false);
  useEffect(() => { if (data && !isDirty && !photo && !signature) reset(toForm(data)); }, [data, isDirty, photo, signature, reset]);
  usePreventRemove(!allowLeave && (isDirty || !!photo || !!signature), ({ repeat }) => {
    Alert.alert(t('profile2.unsavedTitle'), t('profile2.unsavedDetail'), [
      { text: t('cancel'), style: 'cancel' },
      { text: t('profile2.discard'), style: 'destructive', onPress: () => { setAllowLeave(true); repeat(); } },
    ]);
  });
  const field = ({ name, label, keyboard, multiline }: typeof personal[number]) => <Controller key={name} control={control} name={name} render={({ field: input }) => <TextField label={t(label)} value={input.value} onChangeText={input.onChange} keyboardType={keyboard} multiline={multiline} autoCapitalize={name === 'full_name' || name === 'city' || name === 'district' || name === 'state' ? 'words' : 'none'} error={errors[name] && t(name.includes('date') ? 'validation2.date' : name === 'pin_code' ? 'validation2.pin' : name === 'years_of_experience' ? 'validation2.experience' : name.includes('phone') ? 'validation2.phone' : name.includes('email') ? 'validation.email' : name === 'areas_of_practice' ? 'validation2.areas' : 'validation.required')} />} />;
  const save = handleSubmit(async (values) => {
    if (!user) return;
    setError(null);
    const optional = (value: string) => value.trim() || null;
    const payload: ProfileUpdate = {
      full_name: values.full_name.trim(), email: optional(values.email), phone_number: optional(values.phone_number),
      date_of_birth: optional(values.date_of_birth), gender: optional(values.gender), address: optional(values.address),
      city: optional(values.city), district: optional(values.district), state: optional(values.state), pin_code: optional(values.pin_code),
      enrollment_number: optional(values.enrollment_number), bar_council: optional(values.bar_council), enrollment_date: optional(values.enrollment_date),
      professional_designation: optional(values.professional_designation), years_of_experience: values.years_of_experience ? Number(values.years_of_experience) : null,
      office_name: optional(values.office_name), office_address: optional(values.office_address), office_phone: optional(values.office_phone),
      professional_email: optional(values.professional_email), areas_of_practice: values.areas_of_practice ? values.areas_of_practice.split(',').map((item) => item.trim()) : [],
    };
    try {
      let updated = await profileApi.update(payload);
      if (photo) updated = await profileApi.uploadImage('profile', photo.uri, photo.contentType);
      if (signature) updated = await profileApi.uploadImage('signature', signature.uri, signature.contentType);
      useAuthStore.setState({ user: updated });
      client.setQueryData(['me', user.id], updated);
      await Promise.all([client.invalidateQueries({ queryKey: ['dashboard'] }), client.invalidateQueries({ queryKey: ['activities'] })]);
      reset(toForm(updated)); setPhoto(null); setSignature(null); setAllowLeave(true);
      useAppStore.getState().showToast(t('profile2.saved'));
      router.back();
    } catch (caught) { setError(friendlyError(caught)); }
  });
  return <Screen title={t('profile2.edit')}>
    {error && <Notice message={error} />}
    <Card><ImagePickerField purpose="profile" imageKey={user?.profile_image} selected={photo} onPick={setPhoto} /><ImagePickerField purpose="signature" imageKey={user?.signature_image} selected={signature} onPick={setSignature} /></Card>
    <SectionHeader title={t('profile2.personal')} /><Card>{personal.map(field)}<AppText style={{ fontWeight: '600', marginBottom: 8 }}>{t('profile2.gender')}</AppText><Controller control={control} name="gender" render={({ field: gender }) => <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>{[
      ['', 'profile2.none'], ['female', 'profile2.genderFemale'], ['male', 'profile2.genderMale'], ['non_binary', 'profile2.genderNonBinary'], ['prefer_not_to_say', 'profile2.genderPreferNot'],
    ].map(([value, label]) => <Pressable key={value} accessibilityRole="radio" accessibilityState={{ selected: gender.value === value }} onPress={() => gender.onChange(value)} style={{ paddingHorizontal: 12, paddingVertical: 9, borderRadius: 12, borderWidth: 1, borderColor: gender.value === value ? theme.colors.accent : theme.colors.border, backgroundColor: theme.colors.input }}><AppText style={{ fontSize: 13 }}>{t(label)}</AppText></Pressable>)}</View>} /></Card>
    <SectionHeader title={t('profile2.professional')} /><Card>{professional.map(field)}<AppText style={{ color: theme.colors.muted, fontSize: 13 }}>{t('profile2.areasHint')}</AppText></Card>
    <View style={{ marginTop: 24, gap: 8 }}><Button label={t('profile2.saveChanges')} onPress={save} loading={isSubmitting} /><Button label={t('cancel')} variant="text" onPress={() => router.back()} /></View>
  </Screen>;
}
