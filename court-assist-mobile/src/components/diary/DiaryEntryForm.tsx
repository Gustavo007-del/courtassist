import { useState } from 'react';
import { View } from 'react-native';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../common/AppText';
import { Button } from '../common/Button';
import { Card } from '../common/Card';
import { ChoiceChips } from '../common/ChoiceChips';
import { Notice } from '../common/Notice';
import { TextField } from '../common/TextField';
import { DIARY_CATEGORIES } from '../../constants/diary';
import { caseApi } from '../../services/case-api';
import { hearingApi } from '../../services/hearing-api';
import type { DiaryEntry, DiaryInput } from '../../services/diary-api';
import { friendlyError } from '../../utils/errors';

const localDate = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const optional = ['proceedings_summary', 'judge_directions', 'arguments_summary', 'evidence_notes', 'witness_notes', 'observations', 'next_action'] as const;
type OptionalKey = typeof optional[number];
export function DiaryEntryForm({ item, initialCaseId, initialHearingId, initialDate, initialType, onSubmit }: { item?: DiaryEntry; initialCaseId?: string; initialHearingId?: string; initialDate?: string; initialType?: string; onSubmit: (data: DiaryInput, base?: string) => Promise<void> }) {
  const { t } = useTranslation();
  const [base] = useState(item?.updated_at); const [requestId] = useState(() => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`); const [caseId, setCaseId] = useState(item?.case_id ?? initialCaseId ?? ''); const [hearingId, setHearingId] = useState(item?.hearing_id ?? initialHearingId ?? ''); const [entryDate, setEntryDate] = useState(item?.entry_date ?? initialDate ?? localDate()); const [entryType, setEntryType] = useState(item?.entry_type ?? initialType ?? 'General Note'); const [title, setTitle] = useState(item?.title ?? ''); const [content, setContent] = useState(item?.content ?? ''); const [notes, setNotes] = useState<Record<OptionalKey, string>>({ proceedings_summary: item?.proceedings_summary ?? '', judge_directions: item?.judge_directions ?? '', arguments_summary: item?.arguments_summary ?? '', evidence_notes: item?.evidence_notes ?? '', witness_notes: item?.witness_notes ?? '', observations: item?.observations ?? '', next_action: item?.next_action ?? '' }); const [followUpDate, setFollowUpDate] = useState(item?.follow_up_date ?? ''); const [important, setImportant] = useState(item?.is_important ?? false); const [pinned, setPinned] = useState(item?.is_pinned ?? false); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null); const [search, setSearch] = useState('');
  const cases = useQuery({ queryKey: ['diary-cases', search], queryFn: () => caseApi.list({ q: search, limit: 100 }), enabled: !item });
  const hearings = useQuery({ queryKey: ['diary-hearings', caseId], queryFn: () => hearingApi.caseHistory(caseId), enabled: !!caseId });
  const setNote = (key: OptionalKey, value: string) => setNotes((current) => ({ ...current, [key]: value }));
  const validDate = (value: string) => { if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false; const parsed = new Date(`${value}T12:00:00`); return Number.isFinite(parsed.getTime()) && `${parsed.getFullYear()}-${String(parsed.getMonth() + 1).padStart(2, '0')}-${String(parsed.getDate()).padStart(2, '0')}` === value; };
  const save = async () => {
    if (busy) return;
    if (!caseId || !title.trim() || !validDate(entryDate) || (followUpDate && !validDate(followUpDate))) { setError(t('diary.validation')); return; }
    setBusy(true); setError(null);
    try { await onSubmit({ case_id: caseId, hearing_id: hearingId || null, entry_date: entryDate, entry_type: entryType, title: title.trim(), content, ...Object.fromEntries(optional.map((key) => [key, notes[key].trim() || null])) as Pick<DiaryInput, OptionalKey>, follow_up_date: followUpDate || null, is_important: important, is_pinned: pinned, request_id: requestId }, base); }
    catch (caught) { setError(friendlyError(caught)); }
    finally { setBusy(false); }
  };
  return <View style={{ gap: 8 }}>{error && <Notice message={error} />}<Card><AppText style={{ fontWeight: '800' }}>{t('diary.privateLabel')}</AppText>{item ? <AppText>{item.case_title} · {item.case_number}</AppText> : <><TextField label={t('cases.search')} value={search} onChangeText={setSearch} /><ChoiceChips value={caseId} onChange={(value) => { setCaseId(value); setHearingId(''); }} options={[{ value: '', label: t('diary.selectCase') }, ...(cases.data?.items ?? []).map((record) => ({ value: record.id, label: `${record.case_title} · ${record.case_number}` }))]} /></>}<AppText>{t('diary.relatedHearing')}</AppText><ChoiceChips value={hearingId} onChange={setHearingId} options={[{ value: '', label: t('diary.noHearing') }, ...(hearings.data?.items ?? []).map((hearing) => ({ value: hearing.id, label: `${hearing.hearing_date} · ${t(`hearings.types.${hearing.hearing_type}`, hearing.hearing_type)}` }))]} /><TextField label={t('diary.entryDate')} value={entryDate} onChangeText={setEntryDate} /><AppText>{t('diary.category')}</AppText><ChoiceChips value={entryType} onChange={setEntryType} options={DIARY_CATEGORIES.map((value) => ({ value, label: t(`diary.categories.${value}`) }))} /><TextField label={t('diary.entryTitle')} value={title} onChangeText={setTitle} /><TextField label={t('diary.content')} value={content} onChangeText={setContent} multiline />{optional.map((key) => <TextField key={key} label={t(`diary.fields.${key}`)} value={notes[key]} onChangeText={(value) => setNote(key, value)} multiline />)}<TextField label={t('diary.followUpDate')} value={followUpDate} onChangeText={setFollowUpDate} /><AppText>{t('diary.important')}</AppText><ChoiceChips value={important ? 'yes' : 'no'} onChange={(value) => setImportant(value === 'yes')} options={[{ value: 'no', label: t('settings2.no') }, { value: 'yes', label: t('settings2.yes') }]} /><AppText>{t('diary.pinned')}</AppText><ChoiceChips value={pinned ? 'yes' : 'no'} onChange={(value) => setPinned(value === 'yes')} options={[{ value: 'no', label: t('settings2.no') }, { value: 'yes', label: t('settings2.yes') }]} /></Card><Button label={t('save')} loading={busy} onPress={() => { void save(); }} /><Button label={t('cancel')} variant="secondary" onPress={() => router.back()} /></View>;
}
