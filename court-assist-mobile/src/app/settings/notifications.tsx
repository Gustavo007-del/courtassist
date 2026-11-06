import { useState } from 'react';
import { Linking,Switch,View } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { TextField } from '../../components/common/TextField';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { ErrorState } from '../../components/common/ErrorState';
import { notificationApi,type NotificationPreferences } from '../../services/notification-api';
import { requestNotificationPermission,syncNotifications,getNotificationDeviceId,clearNotifications } from '../../services/notification-manager';
const toggles=['local_notifications','push_notifications','email_notifications','hearing_reminders','task_reminders','appointment_reminders','payment_reminders','document_reminders','draft_reminders','hearing_auto_reminders','task_due_today','task_overdue_alerts','task_high_priority','finance_auto_reminders','daily_summary','urgent_quiet_override'] as const;
export default function Preferences(){
 const {t}=useTranslation();const query=useQuery({queryKey:['notification-preferences'],queryFn:notificationApi.preferences});
 const deviceQuery=useQuery({queryKey:['notification-devices'],queryFn:notificationApi.devices});
 const [edited,setValues]=useState<NotificationPreferences|null>(null);const values=edited??query.data?.preferences;const [busy,setBusy]=useState(false);const [message,setMessage]=useState('');const [days,setDays]=useState<string|null>(null);const [repeat,setRepeat]=useState<string|null>(null);const [paymentDays,setPaymentDays]=useState<string|null>(null);
 const save=async()=>{if(!values)return;setBusy(true);setMessage('');try{const data=await notificationApi.updatePreferences({...values,hearing_reminder_days:(days??values.hearing_reminder_days.join(',')).split(',').filter(Boolean).map(Number),overdue_repeat_days:repeat===null?values.overdue_repeat_days:repeat?Number(repeat):null,payment_due_days:paymentDays===null?values.payment_due_days:Number(paymentDays)});setValues(data.preferences);await syncNotifications().catch(()=>{});setMessage(t('notifications.saved'));await query.refetch();}catch{setMessage(t('notifications.preferenceError'));}finally{setBusy(false);}};
 return <Screen back title={t('notifications.preferences')} subtitle={t('notifications.privacy')}>
 {message&&<AppText>{message}</AppText>}
 {query.isPending?<LoadingSkeleton/>:query.isError?<ErrorState message={t('work.error')} retry={()=>void query.refetch()}/>:values&&<>
 {!query.data?.capabilities.push_configured&&<AppText>{t('notifications.fcmSetup')}</AppText>}
 {(!query.data?.capabilities.email_configured||!query.data.capabilities.email_verified)&&<AppText>{t('notifications.emailSetup')}</AppText>}
 <Button label={t('notifications.enablePermission')} variant="secondary" onPress={()=>{void requestNotificationPermission().then(ok=>setMessage(t(ok?'notifications.permissionGranted':'notifications.permissionDenied'))).catch(()=>setMessage(t('work.error')));}}/>
 <Button label={t('notifications.deviceSettings')} variant="text" onPress={()=>void Linking.openSettings()}/>
 {toggles.map(key=><View key={key} style={{flexDirection:'row',alignItems:'center',gap:12,minHeight:54}}><AppText style={{flex:1}}>{t(`notifications.preferencesLabels.${key}`)}</AppText><Switch value={values[key]} onValueChange={value=>setValues({...values,[key]:value})}/></View>)}
 <TextField label={t('notifications.timezone')} value={values.timezone} onChangeText={timezone=>setValues({...values,timezone})}/>
 <TextField label={t('notifications.reminderTime')} value={values.reminder_time.slice(0,5)} onChangeText={reminder_time=>setValues({...values,reminder_time})}/>
 <TextField label={t('notifications.summaryTime')} value={values.daily_summary_time.slice(0,5)} onChangeText={daily_summary_time=>setValues({...values,daily_summary_time})}/>
 <TextField label={t('notifications.hearingDays')} value={days??values.hearing_reminder_days.join(',')} onChangeText={setDays}/>
 <TextField label={t('notifications.paymentDays')} value={paymentDays??String(values.payment_due_days)} onChangeText={setPaymentDays} keyboardType="numeric"/>
 <TextField label={t('notifications.repeatDays')} value={repeat??values.overdue_repeat_days?.toString()??''} onChangeText={setRepeat} keyboardType="numeric"/>
 <TextField label={t('notifications.quietStart')} value={values.quiet_start?.slice(0,5)??''} onChangeText={value=>setValues({...values,quiet_start:value||null})}/>
 <TextField label={t('notifications.quietEnd')} value={values.quiet_end?.slice(0,5)??''} onChangeText={value=>setValues({...values,quiet_end:value||null})}/>
 <AppText>{t('notifications.quietExplanation')}</AppText>
 <Button label={t('save')} loading={busy} onPress={()=>void save()}/>
 </>}
 <AppText>{t('notifications.devices')}</AppText>
 {deviceQuery.isError&&<ErrorState message={t('work.error')} retry={()=>void deviceQuery.refetch()}/>}
 {deviceQuery.data?.filter(device=>!device.revoked_at).map(device=><View key={device.id}><AppText>{device.label||device.platform} · {t(device.push_registered?'notifications.pushRegistered':'notifications.localOnly')}</AppText><AppText>{new Date(device.last_seen_at).toLocaleString()}</AppText><Button variant="text" label={t('notifications.revoke')} onPress={()=>{void notificationApi.revoke(device.id).then(async()=>{if(getNotificationDeviceId()===device.id)await clearNotifications();await deviceQuery.refetch();}).catch(()=>setMessage(t('work.error')));}}/></View>)}
 <AppText>{t('notifications.whatsapp')}</AppText>
 </Screen>;
}
