import { useState } from 'react';
import { View } from 'react-native';
import { Controller, useForm, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { AppText } from '../common/AppText';
import { Button } from '../common/Button';
import { Card } from '../common/Card';
import { ChoiceChips } from '../common/ChoiceChips';
import { Notice } from '../common/Notice';
import { TextField } from '../common/TextField';
import type { Client, ClientInput } from '../../services/client-api';
import { friendlyError } from '../../utils/errors';

const optionalEmail = z.string().trim().refine((value) => !value || z.email().safeParse(value).success);
const optionalPhone = z.string().trim().refine((value) => !value || /^\+?[0-9 ().-]{7,32}$/.test(value));
const schema = z.object({
  client_type: z.enum(['individual', 'organization']), full_name: z.string().trim().min(2).max(160), organization_name: z.string().trim().max(200), phone_number: optionalPhone.refine(Boolean), alternate_phone: optionalPhone, email: optionalEmail,
  address: z.string().trim().min(2).max(500), city: z.string().trim().min(1).max(120), district: z.string().trim().min(1).max(120), state: z.string().trim().min(1).max(120), postal_code: z.string().trim().min(3).max(12).regex(/^[A-Za-z0-9 -]+$/), occupation: z.string().trim().max(160), notes: z.string().trim().max(5000),
}).superRefine((data, context) => { if (data.client_type === 'organization' && !data.organization_name) context.addIssue({ code: 'custom', path: ['organization_name'], message: 'required' }); });
type FormState = z.infer<typeof schema>;
const empty: FormState = { client_type: 'individual', full_name: '', organization_name: '', phone_number: '', alternate_phone: '', email: '', address: '', city: '', district: '', state: '', postal_code: '', occupation: '', notes: '' };
const fromClient = (client?: Client): FormState => client ? { client_type: client.client_type, full_name: client.full_name, organization_name: client.organization_name ?? '', phone_number: client.phone_number, alternate_phone: client.alternate_phone ?? '', email: client.email ?? '', address: client.address, city: client.city, district: client.district, state: client.state, postal_code: client.postal_code, occupation: client.occupation ?? '', notes: client.notes ?? '' } : empty;

export function ClientForm({ initial, submitLabel, onSubmit }: { initial?: Client; submitLabel: string; onSubmit: (data: ClientInput) => Promise<void> }) {
  const { t } = useTranslation(); const [submitError, setSubmitError] = useState<string | null>(null); const { control, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormState>({ resolver: zodResolver(schema), defaultValues: fromClient(initial) }); const clientType = useWatch({ control, name: 'client_type' });
  const field = (name: Exclude<keyof FormState, 'client_type'>, label: string, options: { keyboardType?: 'default' | 'email-address' | 'phone-pad' | 'numeric'; autoCapitalize?: 'none' | 'words'; multiline?: boolean } = {}) => <Controller key={name} control={control} name={name} render={({ field: input }) => <TextField label={label} value={input.value} onChangeText={input.onChange} error={errors[name] ? t(name.includes('phone') ? 'validation2.phone' : name === 'email' ? 'validation.email' : name === 'postal_code' ? 'validation2.postal' : name === 'full_name' ? 'validation.name' : 'validation.required') : undefined} {...options} />} />;
  const save = handleSubmit(async (values) => { setSubmitError(null); const optional = (value: string) => value.trim() || null; try { await onSubmit({ client_type: values.client_type, full_name: values.full_name.trim(), organization_name: optional(values.organization_name), phone_number: values.phone_number.trim(), alternate_phone: optional(values.alternate_phone), email: optional(values.email), address: values.address.trim(), city: values.city.trim(), district: values.district.trim(), state: values.state.trim(), postal_code: values.postal_code.trim(), occupation: optional(values.occupation), notes: optional(values.notes) }); } catch (caught) { setSubmitError(friendlyError(caught)); } });
  return <View style={{ gap: 16 }}>{submitError && <Notice message={submitError} />}<Card><AppText style={{ fontWeight: '600', marginBottom: 8 }}>{t('clients.type')}</AppText><Controller control={control} name="client_type" render={({ field: input }) => <ChoiceChips value={input.value} onChange={input.onChange} options={[{ value: 'individual', label: t('clients.individual') }, { value: 'organization', label: t('clients.organization') }]} />} />
    {field('full_name', t('auth.fullName'), { autoCapitalize: 'words' })}{clientType === 'organization' && field('organization_name', t('clients.organizationName'), { autoCapitalize: 'words' })}{field('phone_number', t('profile2.phoneNumber'), { keyboardType: 'phone-pad' })}{field('alternate_phone', t('clients.alternatePhone'), { keyboardType: 'phone-pad' })}{field('email', t('auth.email'), { keyboardType: 'email-address' })}{field('address', t('profile2.address'), { multiline: true, autoCapitalize: 'words' })}{field('city', t('profile2.city'), { autoCapitalize: 'words' })}{field('district', t('profile2.district'), { autoCapitalize: 'words' })}{field('state', t('profile2.state'), { autoCapitalize: 'words' })}{field('postal_code', t('clients.postalCode'))}{field('occupation', t('clients.occupation'), { autoCapitalize: 'words' })}{field('notes', t('clients.privateNotes'), { multiline: true })}</Card><Button label={submitLabel} onPress={() => { void save(); }} loading={isSubmitting} /></View>;
}
