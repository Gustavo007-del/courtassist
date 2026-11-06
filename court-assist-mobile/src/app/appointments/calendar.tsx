import { useState } from 'react';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Button } from '../../components/common/Button';
import { TextField } from '../../components/common/TextField';
import { Screen } from '../../components/layout/Screen';
import { AppointmentCard } from '../../components/planning/AppointmentCard';
import { appointmentApi } from '../../services/planning-api';
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
export default function AppointmentCalendar() { const { t } = useTranslation(); const [day, setDay] = useState(() => iso(new Date())); const query = useQuery({ queryKey: ['appointments-calendar', day], queryFn: () => appointmentApi.calendar(day, day), enabled: /^\d{4}-\d{2}-\d{2}$/.test(day) }); return <Screen title={t('planning.appointmentCalendar')} back><TextField label={t('planning.date')} value={day} onChangeText={setDay} /><Button label={t('planning.addAppointment')} onPress={() => router.push('/appointments/add')} />{query.data?.map((item) => <AppointmentCard key={item.id} item={item} onPress={() => router.push({ pathname: '/appointments/[id]', params: { id: item.id } })} />)}</Screen>; }
