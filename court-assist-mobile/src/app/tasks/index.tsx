import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
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
import { TaskCard } from '../../components/planning/TaskCard';
import { taskApi } from '../../services/planning-api';
import { friendlyError } from '../../utils/errors';

export default function TaskList() {
  const { status: initialStatus, caseId } = useLocalSearchParams<{ status?: string; caseId?: string }>(); const { t } = useTranslation();
  const [q, setQ] = useState(''); const [status, setStatus] = useState(initialStatus ?? ''); const [priority, setPriority] = useState(''); const [sort, setSort] = useState('due'); const [offset, setOffset] = useState(0);
  const query = useQuery({ queryKey: ['tasks', q, status, priority, sort, offset, caseId], queryFn: () => taskApi.list({ q, status, priority, sort, offset, case_id: caseId, limit: 30 }) });
  return <Screen title={t('planning.tasks')} refreshing={query.isRefetching} onRefresh={() => { void query.refetch(); }} back><Button label={t('planning.addTask')} onPress={() => router.push({ pathname: '/tasks/add', params: { caseId: caseId ?? '' } })} /><Button label={t('planning.overdue')} variant="secondary" onPress={() => router.push('/tasks/overdue')} /><Button label={t('planning.completed')} variant="secondary" onPress={() => router.push('/tasks/completed')} /><Button label={t('planning.filters')} variant="secondary" onPress={() => router.push('/tasks/filters')} /><TextField label={t('planning.search')} value={q} onChangeText={(value) => { setQ(value); setOffset(0); }} /><AppText>{t('planning.status')}</AppText><ChoiceChips value={status} onChange={(value) => { setStatus(value); setOffset(0); }} options={[{ value: '', label: t('planning.all') }, ...(['Pending', 'In Progress', 'Completed', 'Cancelled'] as const).map((value) => ({ value, label: t(`planning.taskStatuses.${value}`) }))]} /><AppText>{t('planning.priority')}</AppText><ChoiceChips value={priority} onChange={(value) => { setPriority(value); setOffset(0); }} options={[{ value: '', label: t('planning.all') }, ...(['Low', 'Medium', 'High', 'Urgent'] as const).map((value) => ({ value, label: t(`planning.priorities.${value}`) }))]} /><AppText>{t('planning.sort')}</AppText><ChoiceChips value={sort} onChange={(value) => { setSort(value); setOffset(0); }} options={['due', 'priority', 'created', 'status'].map((value) => ({ value, label: t(`planning.sorts.${value}`) }))} />{query.isPending ? <LoadingSkeleton /> : query.isError ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : query.data.items.length ? query.data.items.map((item) => <TaskCard key={item.id} item={item} onPress={() => router.push({ pathname: '/tasks/[id]', params: { id: item.id } })} />) : <EmptyState title={t('planning.noTasks')} body={t('planning.noTasksDetail')} />}{query.data && <AppText>{offset + 1}–{Math.min(offset + 30, query.data.total)} / {query.data.total}</AppText>}{offset > 0 && <Button label={t('planning.previous')} variant="secondary" onPress={() => setOffset(Math.max(0, offset - 30))} />}{query.data && offset + 30 < query.data.total && <Button label={t('planning.next')} variant="secondary" onPress={() => setOffset(offset + 30)} />}</Screen>;
}
