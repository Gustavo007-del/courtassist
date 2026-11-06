import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Notice } from '../../components/common/Notice';
import { Screen } from '../../components/layout/Screen';
import { AppointmentForm, newAppointment } from '../../components/planning/AppointmentForm';
import { appointmentApi, type AppointmentInput } from '../../services/planning-api';
import { syncPlanningReminders } from '../../services/planning-reminders';
import { friendlyError } from '../../utils/errors';
export default function AddAppointment() { const { caseId, clientId } = useLocalSearchParams<{ caseId?: string; clientId?: string }>(); const { t } = useTranslation(); const cache = useQueryClient(); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null); const save = async (data: AppointmentInput) => { setBusy(true); setError(null); try { const item = await appointmentApi.create(data); await cache.invalidateQueries({ queryKey: ['appointments'] }); await cache.invalidateQueries({ queryKey: ['dashboard'] }); await syncPlanningReminders().catch(() => {}); router.replace({ pathname: '/appointments/[id]', params: { id: item.id } }); } catch (caught) { setError(friendlyError(caught)); } finally { setBusy(false); } }; return <Screen title={t('planning.addAppointment')} back>{error && <Notice message={error} />}<AppointmentForm initial={newAppointment(caseId, clientId)} onSave={(data) => { void save(data); }} busy={busy} /></Screen>; }
