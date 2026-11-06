import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Notice } from '../../components/common/Notice';
import { Screen } from '../../components/layout/Screen';
import { TaskForm, newTask } from '../../components/planning/TaskForm';
import { taskApi, type TaskInput } from '../../services/planning-api';
import { syncPlanningReminders } from '../../services/planning-reminders';
import { friendlyError } from '../../utils/errors';
export default function AddTask() { const { caseId, clientId, hearingId } = useLocalSearchParams<{ caseId?: string; clientId?: string; hearingId?: string }>(); const { t } = useTranslation(); const cache = useQueryClient(); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null); const save = async (data: TaskInput) => { setBusy(true); setError(null); try { const item = await taskApi.create(data); await cache.invalidateQueries({ queryKey: ['tasks'] }); await cache.invalidateQueries({ queryKey: ['dashboard'] }); await syncPlanningReminders().catch(() => {}); router.replace({ pathname: '/tasks/[id]', params: { id: item.id } }); } catch (caught) { setError(friendlyError(caught)); } finally { setBusy(false); } }; return <Screen title={t('planning.addTask')} back>{error && <Notice message={error} />}<TaskForm initial={newTask(caseId, clientId, hearingId)} onSave={(data) => { void save(data); }} busy={busy} /></Screen>; }
