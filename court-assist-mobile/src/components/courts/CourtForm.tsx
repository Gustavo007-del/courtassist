import { useState } from 'react';
import { View } from 'react-native';
import { useTranslation } from 'react-i18next';
import { AppText } from '../common/AppText';
import { Button } from '../common/Button';
import { Card } from '../common/Card';
import { ChoiceChips } from '../common/ChoiceChips';
import { Notice } from '../common/Notice';
import { TextField } from '../common/TextField';
import { COURT_TYPES } from '../../constants/courts';
import type { Court, CourtInput } from '../../services/court-api';
import { friendlyError } from '../../utils/errors';

type Form = { name: string; court_type: CourtInput['court_type']; state: string; district: string; address: string; phone_number: string; email: string; official_website: string; jurisdiction: string; notes: string };
const empty: Form = { name: '', court_type: 'District Court', state: '', district: '', address: '', phone_number: '', email: '', official_website: '', jurisdiction: '', notes: '' };
const fromCourt = (court?: Court): Form => court ? { name: court.name, court_type: court.court_type, state: court.state, district: court.district, address: court.address, phone_number: court.phone_number ?? '', email: court.email ?? '', official_website: court.official_website ?? '', jurisdiction: court.jurisdiction ?? '', notes: court.notes ?? '' } : empty;

export function CourtForm({ initial, submitLabel, onSubmit }: { initial?: Court; submitLabel: string; onSubmit: (data: CourtInput) => Promise<void> }) {
  const { t } = useTranslation(); const [form, setForm] = useState<Form>(() => fromCourt(initial)); const [error, setError] = useState<string | null>(null); const [saving, setSaving] = useState(false);
  const update = (key: keyof Form) => (value: string) => setForm((current) => ({ ...current, [key]: value }));
  const save = async () => {
    if ([form.name, form.state, form.district, form.address].some((value) => !value.trim())) { setError(t('validation.required')); return; }
    setSaving(true); setError(null);
    try { const optional = (value: string) => value.trim() || null; await onSubmit({ name: form.name.trim(), court_type: form.court_type, state: form.state.trim(), district: form.district.trim(), address: form.address.trim(), phone_number: optional(form.phone_number), email: optional(form.email), official_website: optional(form.official_website), jurisdiction: optional(form.jurisdiction), notes: optional(form.notes) }); } catch (caught) { setError(friendlyError(caught)); } finally { setSaving(false); }
  };
  return <View style={{ gap: 16 }}>{error && <Notice message={error} />}<Card>
    <TextField label={t('courts.name')} value={form.name} onChangeText={update('name')} autoCapitalize="words" />
    <AppText style={{ fontWeight: '600', marginBottom: 8 }}>{t('courts.type')}</AppText><ChoiceChips value={form.court_type} onChange={(court_type) => setForm((current) => ({ ...current, court_type }))} options={COURT_TYPES.map((value) => ({ value, label: t(`courts.types.${value}`) }))} />
    <TextField label={t('courts.state')} value={form.state} onChangeText={update('state')} autoCapitalize="words" /><TextField label={t('courts.district')} value={form.district} onChangeText={update('district')} autoCapitalize="words" /><TextField label={t('courts.address')} value={form.address} onChangeText={update('address')} multiline autoCapitalize="words" /><TextField label={t('courts.phone')} value={form.phone_number} onChangeText={update('phone_number')} keyboardType="phone-pad" /><TextField label={t('courts.email')} value={form.email} onChangeText={update('email')} keyboardType="email-address" /><TextField label={t('courts.website')} value={form.official_website} onChangeText={update('official_website')} /><TextField label={t('courts.jurisdiction')} value={form.jurisdiction} onChangeText={update('jurisdiction')} multiline /><TextField label={t('courts.notes')} value={form.notes} onChangeText={update('notes')} multiline />
  </Card><Button label={submitLabel} onPress={() => { void save(); }} loading={saving} /></View>;
}
