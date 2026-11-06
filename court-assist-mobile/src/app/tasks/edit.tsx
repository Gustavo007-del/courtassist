import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { Notice } from '../../components/common/Notice';
import { Screen } from '../../components/layout/Screen';
import { TaskForm } from '../../components/planning/TaskForm';
import { taskApi, type TaskInput } from '../../services/planning-api';
import { syncPlanningReminders } from '../../services/planning-reminders';
import { friendlyError } from '../../utils/errors';
export default function EditTask() { const { id } = useLocalSearchParams<{ id: string }>(); const { t } = useTranslation(); const cache = useQueryClient(); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null); const query = useQuery({ queryKey: ['task', id], queryFn: () => taskApi.get(id) }); const save = async (data: TaskInput, base?: string) => { setBusy(true); setError(null); try { await taskApi.update(id, data, base); await cache.invalidateQueries({ queryKey: ['task', id] }); await cache.invalidateQueries({ queryKey: ['tasks'] }); await cache.invalidateQueries({ queryKey: ['dashboard'] }); await syncPlanningReminders().catch(() => {}); router.back(); } catch (caught) { setError(friendlyError(caught)); } finally { setBusy(false); } }; return <Screen title={t('planning.editTask')} back>{error && <Notice message={error} />}{query.isPending ? <LoadingSkeleton /> : query.data && <TaskForm initial={query.data} onSave={(data, base) => { void save(data, base); }} busy={busy} />}</Screen>; }
