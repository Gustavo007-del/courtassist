import { useState } from 'react';
import { router } from 'expo-router';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import { View } from 'react-native';
import { AppText } from '../common/AppText';
import { Button } from '../common/Button';
import { Card } from '../common/Card';
import { ChoiceChips } from '../common/ChoiceChips';
import { Notice } from '../common/Notice';
import { TextField } from '../common/TextField';
import { caseApi } from '../../services/case-api';
import { courtApi } from '../../services/court-api';
import { hearingApi, type Hearing, type HearingInput } from '../../services/hearing-api';
import { HEARING_TYPES } from '../../constants/hearings';
import { friendlyError } from '../../utils/errors';

const schema = z.object({ hearing_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/), hearing_time: z.string().refine((v) => !v || /^\d{2}:\d{2}$/.test(v)), estimated_end_time: z.string().refine((v) => !v || /^\d{2}:\d{2}$/.test(v)), hearing_type: z.string().min(2), hearing_stage: z.string(), courtroom: z.string(), judge_name: z.string(), purpose: z.string().trim().min(2), reminder_enabled: z.boolean() }).refine((v) => !v.estimated_end_time || !!v.hearing_time && v.estimated_end_time > v.hearing_time, { path: ['estimated_end_time'] });
type Form = z.infer<typeof schema>;
export function HearingForm({ item, initialCaseId, onSubmit }: { item?: Hearing; initialCaseId?: string; onSubmit: (data: HearingInput) => Promise<void> }) {
  const { t } = useTranslation(); const [caseId, setCaseId] = useState(initialCaseId ?? item?.case_id ?? ''); const [courtId, setCourtId] = useState(item?.court_id ?? ''); const [caseSearch, setCaseSearch] = useState(''); const [error, setError] = useState<string | null>(null); const [warnings, setWarnings] = useState<string[]>([]);
  const cases = useQuery({ queryKey: ['hearing-case-options', caseSearch], queryFn: () => caseApi.list({ q: caseSearch, limit: 100 }) }); const courts = useQuery({ queryKey: ['hearing-court-options'], queryFn: () => courtApi.list({ limit: 100 }) });
  const effectiveCourtId = courtId || (!item && cases.data?.items.find((record) => record.id === caseId)?.court_id) || '';
  const { control, handleSubmit, formState: { errors, isSubmitting } } = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { hearing_date: item?.hearing_date ?? new Date().toISOString().slice(0, 10), hearing_time: item?.hearing_time?.slice(0, 5) ?? '', estimated_end_time: item?.estimated_end_time?.slice(0, 5) ?? '', hearing_type: item?.hearing_type ?? 'First Hearing', hearing_stage: item?.hearing_stage ?? '', courtroom: item?.courtroom ?? '', judge_name: item?.judge_name ?? '', purpose: item?.purpose ?? '', reminder_enabled: item?.reminder_enabled ?? true } });
  const field = (name: Exclude<keyof Form, 'reminder_enabled'>, label: string) => <Controller key={name} control={control} name={name} render={({ field: input }) => <TextField label={label} value={input.value} onChangeText={input.onChange} error={errors[name] ? t('validation.required') : undefined} />} />;
  const payload = (values: Form): HearingInput => ({ case_id: caseId, court_id: effectiveCourtId || null, hearing_date: values.hearing_date, hearing_time: values.hearing_time || null, estimated_end_time: values.estimated_end_time || null, hearing_type: values.hearing_type, hearing_stage: values.hearing_stage || null, courtroom: values.courtroom || null, judge_name: values.judge_name || null, purpose: values.purpose.trim(), reminder_enabled: values.reminder_enabled });
  const save = handleSubmit(async (values) => { if (!caseId) { setError(t('hearings.selectCase')); return; } setError(null); try { await onSubmit(payload(values)); } catch (caught) { setError(friendlyError(caught)); } });
  const check = handleSubmit(async (values) => { if (!caseId) { setError(t('hearings.selectCase')); return; } try { const results = await hearingApi.conflicts(payload(values)); setWarnings(results.map((result) => `${t(`hearings.conflictKinds.${result.kind}`)} · ${result.case_title}`)); } catch (caught) { setError(friendlyError(caught)); } });
  return <View style={{ gap: 16 }}>{error && <Notice message={error} />}{warnings.map((warning, index) => <Card key={index}><AppText>{warning}</AppText></Card>)}<Card>{item ? <AppText>{item.case_title} · {item.case_number}</AppText> : <><TextField label={t('cases.search')} value={caseSearch} onChangeText={setCaseSearch} /><AppText>{t('hearings.selectCase')}</AppText><ChoiceChips value={caseId} onChange={(value) => { setCaseId(value); const selected = cases.data?.items.find((record) => record.id === value); setCourtId(selected?.court_id ?? ''); }} options={[{ value: '', label: t('hearings.selectCase') }, ...(cases.data?.items ?? []).map((record) => ({ value: record.id, label: `${record.case_title} · ${record.case_number}` }))]} /><Button label={t('cases.add')} variant="secondary" onPress={() => router.push('/cases/add')} /></>}<AppText>{t('cases.court')}</AppText><ChoiceChips value={effectiveCourtId} onChange={setCourtId} options={[{ value: '', label: t('cases.noCourt') }, ...(courts.data?.items ?? []).map((court) => ({ value: court.id, label: court.name }))]} />{field('hearing_date', t('hearings.date'))}{field('hearing_time', t('hearings.time'))}{field('estimated_end_time', t('hearings.endTime'))}<AppText>{t('hearings.type')}</AppText><Controller control={control} name="hearing_type" render={({ field: input }) => <ChoiceChips value={input.value} onChange={input.onChange} options={HEARING_TYPES.map((value) => ({ value, label: t(`hearings.types.${value}`) }))} />} />{field('purpose', t('hearings.purpose'))}{field('hearing_stage', t('hearings.stage'))}{field('judge_name', t('cases.judge'))}{field('courtroom', t('cases.courtroom'))}<AppText>{t('hearings.reminders')}</AppText><Controller control={control} name="reminder_enabled" render={({ field: input }) => <ChoiceChips value={input.value ? 'yes' : 'no'} onChange={(value) => input.onChange(value === 'yes')} options={[{ value: 'yes', label: t('settings2.yes') }, { value: 'no', label: t('settings2.no') }]} />} /></Card><Button label={t('hearings.checkConflicts')} variant="secondary" onPress={() => { void check(); }} /><Button label={t('save')} loading={isSubmitting} onPress={() => { void save(); }} /></View>;
}
