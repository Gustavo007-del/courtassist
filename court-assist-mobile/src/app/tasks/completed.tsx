import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { EmptyState } from '../../components/common/EmptyState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { Screen } from '../../components/layout/Screen';
import { TaskCard } from '../../components/planning/TaskCard';
import { taskApi } from '../../services/planning-api';
export default function CompletedTasks() { const { t } = useTranslation(); const query = useQuery({ queryKey: ['tasks-completed'], queryFn: () => taskApi.list({ status: 'Completed', limit: 100 }) }); return <Screen title={t('planning.completed')} back>{query.isPending ? <LoadingSkeleton /> : query.data?.items.length ? query.data.items.map((item) => <TaskCard key={item.id} item={item} onPress={() => router.push({ pathname: '/tasks/[id]', params: { id: item.id } })} />) : <EmptyState title={t('planning.noTasks')} body={t('planning.noTasksDetail')} />}</Screen>; }
