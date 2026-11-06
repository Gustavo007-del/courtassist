import { useState } from 'react';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { TextField } from '../../components/common/TextField';
import { Screen } from '../../components/layout/Screen';
import { AppointmentCard } from '../../components/planning/AppointmentCard';
import { appointmentApi } from '../../services/planning-api';
import { friendlyError } from '../../utils/errors';
export default function Appointments() { const { t } = useTranslation(); const [q, setQ] = useState(''); const [status, setStatus] = useState(''); const [offset, setOffset] = useState(0); const query = useQuery({ queryKey: ['appointments', q, status, offset], queryFn: () => appointmentApi.list({ q, status, offset, limit: 30 }) }); return <Screen title={t('planning.appointments')} back refreshing={query.isRefetching} onRefresh={() => { void query.refetch(); }}><Button label={t('planning.addAppointment')} onPress={() => router.push('/appointments/add')} /><Button label={t('planning.appointmentCalendar')} variant="secondary" onPress={() => router.push('/appointments/calendar')} /><TextField label={t('planning.search')} value={q} onChangeText={(value) => { setQ(value); setOffset(0); }} /><AppText>{t('planning.status')}</AppText><ChoiceChips value={status} onChange={(value) => { setStatus(value); setOffset(0); }} options={[{ value: '', label: t('planning.all') }, ...(['Scheduled', 'Completed', 'Cancelled', 'No-show'] as const).map((value) => ({ value, label: t(`planning.appointmentStatuses.${value}`) }))]} />{query.isPending ? <LoadingSkeleton /> : query.isError ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : query.data.items.length ? query.data.items.map((item) => <AppointmentCard key={item.id} item={item} onPress={() => router.push({ pathname: '/appointments/[id]', params: { id: item.id } })} />) : <EmptyState title={t('planning.noAppointments')} body={t('planning.noAppointmentsDetail')} />}{query.data && <AppText>{offset + 1}–{Math.min(offset + 30, query.data.total)} / {query.data.total}</AppText>}{offset > 0 && <Button label={t('planning.previous')} variant="secondary" onPress={() => setOffset(Math.max(0, offset - 30))} />}{query.data && offset + 30 < query.data.total && <Button label={t('planning.next')} variant="secondary" onPress={() => setOffset(offset + 30)} />}</Screen>; }
