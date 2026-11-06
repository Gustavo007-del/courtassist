import { useEffect,useState } from 'react';
import { router,useLocalSearchParams,type Href } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Button } from '../../components/common/Button';
import { AppText } from '../../components/common/AppText';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { ErrorState } from '../../components/common/ErrorState';
import { notificationApi } from '../../services/notification-api';
import { notificationDestination,syncNotifications } from '../../services/notification-manager';
export default function Detail(){
 const {id}=useLocalSearchParams<{id:string}>();const {t}=useTranslation();const [error,setError]=useState(false);
 const query=useQuery({queryKey:['notification',id],queryFn:()=>notificationApi.get(id)});
 useEffect(()=>{void notificationApi.read(id).catch(()=>{});},[id]);
 const row=query.data;
 return <Screen back title={t('notifications.detail')}>
 {query.isPending?<LoadingSkeleton/>:query.isError?<ErrorState message={t('work.error')} retry={()=>void query.refetch()}/>:row&&<>
 <AppText>{row.message}</AppText><AppText>{new Date(row.scheduled_at).toLocaleString()}</AppText>
 <AppText>{t(`notifications.status.${row.status}`,row.status)}</AppText>
 {row.summary&&Object.entries(row.summary).filter(([key])=>key!=='generated_at'&&key!=='date').map(([key,value])=><AppText key={key}>{t(`notifications.summary.${key}`,key)}: {value}</AppText>)}
 {row.summary&&<><Button variant="secondary" label={t('notifications.summary.hearings')} onPress={()=>router.push('/hearings/daily-schedule')}/><Button variant="secondary" label={t('notifications.summary.appointments')} onPress={()=>router.push('/appointments')}/><Button variant="secondary" label={t('notifications.summary.tasks_due_today')} onPress={()=>router.push('/tasks')}/><Button variant="secondary" label={t('notifications.summary.overdue_tasks')} onPress={()=>router.push('/tasks/overdue')}/><Button variant="secondary" label={t('notifications.summary.pending_followups')} onPress={()=>router.push('/notifications')}/></>}
 {notificationDestination(row)&&<Button label={t('notifications.openRecord')} onPress={()=>router.push(notificationDestination(row) as Href)}/>}
 {row.manual&&!row.cancelled_at&&<Button variant="secondary" label={t('notifications.reschedule')} onPress={()=>router.push({pathname:'/notifications/create',params:{entity_type:row.entity_type??'',entity_id:row.entity_id??'',replaces:row.id}} as Href)}/>}
 <Button label={t('notifications.dismiss')} variant="secondary" onPress={()=>{void notificationApi.dismiss(id).then(()=>syncNotifications()).then(()=>router.back()).catch(()=>setError(true));}}/>
 <AppText>{t('notifications.deliveryExplanation')}</AppText>
 {row.deliveries?.map(d=><AppText key={d.id}>{t(`notifications.channels.${d.channel}`,d.channel)} · {t(`notifications.status.${d.status}`,d.status)} · {t('notifications.attempts')}: {d.attempt_count}{d.error_code?` (${d.error_code})`:''}</AppText>)}
 </>}{error&&<AppText>{t('work.error')}</AppText>}
 </Screen>;
}
