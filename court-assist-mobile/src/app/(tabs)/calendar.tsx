import { useState } from 'react';
import { Pressable, View } from 'react-native';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '../../components/common/Button';
import { AppText } from '../../components/common/AppText';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { TextField } from '../../components/common/TextField';
import { HearingCard } from '../../components/hearings/HearingCard';
import { Screen } from '../../components/layout/Screen';
import { CASE_CATEGORIES } from '../../constants/cases';
import { HEARING_STATUSES } from '../../constants/hearings';
import { courtApi } from '../../services/court-api';
import { hearingApi } from '../../services/hearing-api';
import { planningCalendarApi } from '../../services/planning-api';
import { useTheme } from '../../theme/tokens';
import { friendlyError } from '../../utils/errors';
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
type Mode = 'month' | 'week' | 'day' | 'list';
export default function Calendar() {
  const { t } = useTranslation(); const theme = useTheme(); const [selected, setSelected] = useState(iso(new Date())); const [mode, setMode] = useState<Mode>('month'); const [courtId, setCourtId] = useState(''); const [status, setStatus] = useState(''); const [category, setCategory] = useState('');
  const parsedDate = /^\d{4}-\d{2}-\d{2}$/.test(selected) ? new Date(`${selected}T12:00:00`) : new Date(NaN);
  const validDate = Number.isFinite(parsedDate.getTime()) && iso(parsedDate) === selected;
  const selectedDate = validDate ? parsedDate : new Date(); const first = new Date(selectedDate); const last = new Date(selectedDate);
  if (mode === 'month') { first.setDate(1); last.setMonth(last.getMonth() + 1, 0); } else if (mode === 'week') { first.setDate(first.getDate() - ((first.getDay() + 6) % 7)); last.setTime(first.getTime()); last.setDate(last.getDate() + 6); } else if (mode === 'list') { last.setDate(last.getDate() + 60); }
  const from = iso(first), to = iso(last);
  const query = useQuery({ queryKey: ['calendar', mode, from, to, courtId, status, category], queryFn: () => hearingApi.calendar(from, to, { court_id: courtId, status, category }) });
  const combined = useQuery({ queryKey: ['planning-agenda', from, to], queryFn: () => planningCalendarApi.agenda(from, to) });
  const courts = useQuery({ queryKey: ['calendar-courts'], queryFn: () => courtApi.list({ limit: 100 }) });
  const move = (direction: number) => { const date = new Date(selectedDate); if (mode === 'month') date.setMonth(date.getMonth() + direction); else date.setDate(date.getDate() + direction * (mode === 'week' ? 7 : 1)); setSelected(iso(date)); };
  const days = Array.from({ length: Math.round((last.getTime() - first.getTime()) / 86400000) + 1 }, (_, index) => { const day = new Date(first); day.setDate(day.getDate() + index); return iso(day); });
  const agenda = query.data?.items.filter((item) => mode === 'list' || item.hearing_date === selected) ?? [];
  return <Screen title={t('hearings.calendar')} refreshing={query.isRefetching || combined.isRefetching} onRefresh={() => { void query.refetch(); void combined.refetch(); }}><View style={{ gap: 8 }}><Button label={t('hearings.schedule')} onPress={() => router.push('/hearings/add')} /><Button label={t('planning.addTask')} variant="secondary" onPress={() => router.push('/tasks/add')} /><Button label={t('planning.addAppointment')} variant="secondary" onPress={() => router.push('/appointments/add')} /><Button label={t('hearings.dailySchedule')} variant="secondary" onPress={() => router.push({ pathname: '/hearings/daily-schedule', params: { day: selected } })} /><ChoiceChips value={mode} onChange={setMode} options={(['month', 'week', 'day', 'list'] as const).map((value) => ({ value, label: t(`hearings.views.${value}`) }))} /><View style={{ flexDirection: 'row', gap: 8 }}><View style={{ flex: 1 }}><Button label={t('hearings.previous')} variant="secondary" onPress={() => move(-1)} /></View><View style={{ flex: 1 }}><Button label={t('hearings.today')} variant="secondary" onPress={() => setSelected(iso(new Date()))} /></View><View style={{ flex: 1 }}><Button label={t('hearings.next')} variant="secondary" onPress={() => move(1)} /></View></View><TextField label={t('hearings.selectDate')} value={selected} onChangeText={setSelected} /><ChoiceChips value={courtId} onChange={setCourtId} options={[{ value: '', label: t('hearings.allCourts') }, ...(courts.data?.items ?? []).map((court) => ({ value: court.id, label: court.name }))]} /><ChoiceChips value={status} onChange={setStatus} options={[{ value: '', label: t('hearings.allStatuses') }, ...HEARING_STATUSES.map((value) => ({ value, label: t(`hearings.statuses.${value}`) }))]} /><ChoiceChips value={category} onChange={setCategory} options={[{ value: '', label: t('cases.allTypes') }, ...CASE_CATEGORIES.map((value) => ({ value, label: t(`cases.categories.${value}`) }))]} /></View>
    {(mode === 'month' || mode === 'week') && <View style={{ flexDirection: 'row', flexWrap: 'wrap', marginVertical: 18 }}>{days.map((day) => <Pressable key={day} onPress={() => setSelected(day)} style={{ width: '14.28%', minHeight: 58, padding: 4, borderWidth: 1, borderColor: day === selected ? theme.colors.accent : theme.colors.border, backgroundColor: day === selected ? theme.colors.input : theme.colors.surface }}><AppText style={{ textAlign: 'center', fontSize: 13 }}>{Number(day.slice(-2))}</AppText>{(['hearing', 'task', 'appointment'] as const).map((kind) => combined.data?.some((item) => item.date === day && item.kind === kind) ? <View key={kind} style={{ width: 6, height: 6, borderRadius: 3, alignSelf: 'center', backgroundColor: kind === 'hearing' ? theme.colors.accent : kind === 'task' ? theme.colors.navy : theme.colors.success }} /> : null)}</Pressable>)}</View>}
    <AppText>{t('planning.agenda')}</AppText>{combined.data?.filter((item) => mode === 'list' || item.date === selected).map((item) => <Button key={`${item.kind}-${item.id}`} label={`${t(`planning.eventKinds.${item.kind}`)} · ${item.date} ${item.time?.slice(0, 5) ?? ''} · ${item.title}`} variant="secondary" onPress={() => router.push(item.kind === 'hearing' ? { pathname: '/hearings/[id]', params: { id: item.id } } : item.kind === 'task' ? { pathname: '/tasks/[id]', params: { id: item.id } } : { pathname: '/appointments/[id]', params: { id: item.id } })} />)}
    {query.isPending ? <LoadingSkeleton /> : query.isError ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : agenda.length === 0 ? <EmptyState title={t('hearings.none')} body={t('hearings.noneDetail')} /> : <View style={{ gap: 9, marginTop: 16 }}>{agenda.map((item) => <HearingCard key={item.id} item={item} onPress={() => router.push({ pathname: '/hearings/[id]', params: { id: item.id } })} />)}</View>}
  </Screen>;
}
