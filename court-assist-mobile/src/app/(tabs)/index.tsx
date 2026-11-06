import { notificationApi } from '../../services/notification-api';
import { Pressable, View } from 'react-native';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { Bell } from 'lucide-react-native';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { AppText } from '../../components/common/AppText';
import { Avatar } from '../../components/common/Avatar';
import { SectionHeader } from '../../components/common/SectionHeader';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { ErrorState } from '../../components/common/ErrorState';
import { EmptyState } from '../../components/common/EmptyState';
import { ActivityList } from '../../components/dashboard/ActivityList';
import { QuickActionGrid } from '../../components/dashboard/QuickActionGrid';
import { SummaryCard } from '../../components/dashboard/SummaryCard';
import { dashboardApi } from '../../services/dashboard-api';
import { phase10Api } from '../../services/phase10-api';
import { taskApi, appointmentApi } from '../../services/planning-api';
import { useAuthStore } from '../../store/auth-store';
import { useTheme } from '../../theme/tokens';
import { friendlyError } from '../../utils/errors';

export default function Home() {
  const { t, i18n } = useTranslation(); const theme = useTheme();
  const user = useAuthStore((state) => state.user);
  const { data, isPending, isError, error, isRefetching, refetch } = useQuery({ queryKey: ['dashboard', user?.id], queryFn: dashboardApi.overview, enabled: !!user });
  const tasks = useQuery({ queryKey: ['dashboard-tasks', user?.id], queryFn: taskApi.upcoming, enabled: !!user });
  const appointments = useQuery({ queryKey: ['dashboard-appointments', user?.id], queryFn: appointmentApi.upcoming, enabled: !!user });
  const finance = useQuery({ queryKey: ['finance-overview', user?.id], queryFn: phase10Api.finance, enabled: !!user });
  const notifications=useQuery({queryKey:['notification-count',user?.id],queryFn:notificationApi.unread,enabled:!!user,refetchInterval:30_000});
  const hour = new Date().getHours();
  const greeting = t(hour < 12 ? 'dashboard.morning' : hour < 17 ? 'dashboard.afternoon' : 'dashboard.evening');
  const date = data?.today_date ? new Date(`${data.today_date}T00:00:00`).toLocaleDateString(i18n.language === 'ml' ? 'ml-IN' : 'en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) : '';
  const firstName = data?.profile.full_name.trim().split(/\s+/)[0] ?? user?.full_name.trim().split(/\s+/)[0] ?? '';
  const metrics = data ? [
    ['todayHearings', data.summary.today_hearings, data.module_availability.hearings],
    ['tomorrowHearings', data.summary.tomorrow_hearings, data.module_availability.hearings],
    ['activeCases', data.summary.active_cases, data.module_availability.cases],
    ['pendingTasks', data.summary.pending_tasks, data.module_availability.tasks],
    ['overdueTasks', data.summary.overdue_tasks, data.module_availability.tasks],
    ['upcomingDeadlines', data.summary.upcoming_deadlines, data.module_availability.deadlines],
    ['tasksDueToday', data.summary.tasks_due_today, data.module_availability.tasks],
    ['highPriorityTasks', data.summary.high_priority_tasks, data.module_availability.tasks],
    ['upcomingAppointments', data.summary.upcoming_appointments, data.module_availability.appointments],
    ['recentlyCompletedTasks', data.summary.recently_completed_tasks, data.module_availability.tasks],
  ] as const : [];
  return <Screen refreshing={isRefetching} onRefresh={() => { void refetch(); }}>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14, marginBottom: 26 }}>
      <Pressable accessibilityRole="button" accessibilityLabel={t('tabs.profile')} onPress={() => router.push('/(tabs)/profile')}><Avatar imageKey={data?.profile.profile_image ?? user?.profile_image} size={54} /></Pressable>
      <View style={{ flex: 1 }}><AppText style={{ color: theme.colors.muted, fontSize: 14 }}>{greeting}</AppText><AppText style={{ fontSize: 26, lineHeight: 32, fontWeight: '800' }}>{firstName}</AppText><AppText style={{ color: theme.colors.muted, fontSize: 13 }}>{date}</AppText></View>
      <Pressable accessibilityRole="button" accessibilityLabel={t('settings2.notifications')} onPress={() => router.push('/notifications')} style={{ width: 44, height: 44, alignItems: 'center', justifyContent: 'center', borderRadius: 14, backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: 1 }}><Bell color={theme.colors.navy} size={21} />{!!notifications.data?.count&&<AppText style={{fontSize:10}}>{notifications.data.count}</AppText>}</Pressable>
    </View>
    {isPending ? <LoadingSkeleton rows={5} /> : isError ? <ErrorState message={friendlyError(error)} retry={() => { void refetch(); }} /> : data && <>
      <SectionHeader title={t('dashboard.overview')} subtitle={t('dashboard.unavailable')} />
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', rowGap: 10 }}>{metrics.map(([key, count, available]) => <SummaryCard key={key} label={t(`dashboard.${key}`)} count={count} available={available} onPress={() => router.push(key === 'overdueTasks' ? '/tasks/overdue' : key === 'upcomingAppointments' ? '/appointments' : key === 'todayHearings' || key === 'tomorrowHearings' ? '/(tabs)/calendar' : key === 'activeCases' ? '/(tabs)/cases' : key === 'recentlyCompletedTasks' ? '/tasks/completed' : '/tasks')} />)}</View>
      <SectionHeader title={t('work.finance')} /><Card>{finance.data && <><AppText>{t('work.received')}: ₹{finance.data.received}</AppText><AppText>{t('work.outstanding')}: ₹{finance.data.outstanding}</AppText></>}<Button label={t('work.finance')} variant="text" onPress={() => router.push('/finance')} /></Card>
      <SectionHeader title={t('planning.upcomingTasks')} /><Card>{tasks.data?.slice(0, 5).map((item) => <Pressable key={item.id} onPress={() => router.push({ pathname: '/tasks/[id]', params: { id: item.id } })}><AppText>{item.due_date} · {item.title}</AppText></Pressable>)}<Button label={t('planning.tasks')} variant="text" onPress={() => router.push('/tasks')} /></Card>
      <SectionHeader title={t('planning.upcomingAppointments')} /><Card>{appointments.data?.slice(0, 5).map((item) => <Pressable key={item.id} onPress={() => router.push({ pathname: '/appointments/[id]', params: { id: item.id } })}><AppText>{item.appointment_date} · {item.title}</AppText></Pressable>)}<Button label={t('planning.appointments')} variant="text" onPress={() => router.push('/appointments')} /></Card>
      <SectionHeader title={t('dashboard.todaysSchedule')} /><Card>{data.today_schedule.length ? data.today_schedule.map((entry) => <Pressable key={entry.id} onPress={() => router.push({ pathname: '/hearings/[id]', params: { id: entry.id } })}><AppText style={{ fontWeight: '700' }}>{entry.case_title} · {entry.hearing_time ? new Date(entry.hearing_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : t('hearings.timeUnknown')}</AppText><AppText style={{ color: theme.colors.muted }}>{entry.court_name}</AppText></Pressable>) : <EmptyState title={t('dashboard.nothingYet')} body={t('hearings.noneDetail')} />}</Card><View style={{ marginTop: 8 }}><Button label={t('hearings.dailySchedule')} variant="secondary" onPress={() => router.push('/hearings/daily-schedule')} /></View>
      <SectionHeader title={t('hearings.summary')} /><Card><AppText>{t('hearings.thisWeek')}: {data.hearing_summary.this_week}</AppText><AppText>{t('hearings.recentCompleted')}: {data.hearing_summary.recently_completed}</AppText><AppText>{t('hearings.potentialConflicts')}: {data.hearing_summary.potential_conflicts_today}</AppText><Button label={t('hearings.calendar')} variant="text" onPress={() => router.push('/(tabs)/calendar')} /></Card>
      <SectionHeader title={t('dashboard.todayActivity')} /><Card><ActivityList items={data.today_activities} emptyBody={t('dashboard.noRecent')} /></Card>
      <SectionHeader title={t('dashboard.upcoming')} /><Card>{data.upcoming_activities.length ? data.upcoming_activities.map((item) => <Pressable key={item.id} onPress={() => router.push({ pathname: '/hearings/[id]', params: { id: item.id } })} style={{ marginBottom: 10 }}><AppText style={{ fontWeight: '700' }}>{item.title}</AppText><AppText style={{ color: theme.colors.muted }}>{item.hearing_date} · {item.scheduled_at ? new Date(item.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : t('hearings.timeUnknown')}</AppText></Pressable>) : <EmptyState title={t('dashboard.nothingYet')} body={t('dashboard.noUpcoming')} />}</Card>
      <SectionHeader title={t('dashboard.quickActions')} /><QuickActionGrid />
      <SectionHeader title={t('dashboard.recent')} /><Card><ActivityList items={data.recent_activities} emptyBody={t('dashboard.noRecent')} /></Card>
    </>}
  </Screen>;
}
