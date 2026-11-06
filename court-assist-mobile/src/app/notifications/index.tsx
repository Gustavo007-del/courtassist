import { useTheme } from '../../theme/tokens';
import { Bell,CalendarCheck,CalendarClock,CheckSquare,Wallet,FileText,PenLine,Sun } from 'lucide-react-native';
import { View } from 'react-native';
import { useState } from 'react';
import { router,type Href } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Button } from '../../components/common/Button';
import { AppText } from '../../components/common/AppText';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { ErrorState } from '../../components/common/ErrorState';
import { notificationApi } from '../../services/notification-api';
import { useAuthStore } from '../../store/auth-store';
export const notificationCategories=['hearing','task','appointment','payment','document','draft','daily_summary','system'];
const icons:Record<string,typeof Bell>={hearing:CalendarClock,task:CheckSquare,appointment:CalendarCheck,payment:Wallet,document:FileText,draft:PenLine,daily_summary:Sun};
export default function Center(){
 const theme=useTheme();const {t}=useTranslation();const owner=useAuthStore(s=>s.user?.id);const [category,setCategory]=useState('');const [readState,setReadState]=useState(0);const [ascending,setAscending]=useState(false);const [scheduled,setScheduled]=useState(false);const [offset,setOffset]=useState(0);const [error,setError]=useState(false);
 const query=useQuery({queryKey:['notifications',owner,category,readState,scheduled,offset,ascending],queryFn:()=>notificationApi.list({category,unread_only:String(readState===1),read_only:String(readState===2),ascending:String(ascending),scheduled:String(scheduled),offset:String(offset),limit:'30'}),enabled:!!owner,refetchInterval:60_000});
 const filter=(fn:()=>void)=>{fn();setOffset(0);};
 return <Screen back title={t('notifications.center')} onRefresh={()=>void query.refetch()} refreshing={query.isRefetching}>
 <Button label={t('notifications.preferences')} variant="secondary" onPress={()=>router.push('/settings/notifications')}/>
 <Button label={t('notifications.newReminder')} variant="secondary" onPress={()=>router.push('/notifications/create' as Href)}/>
 <Button label={t(['notifications.all','notifications.unread','notifications.read'][readState])} variant="secondary" onPress={()=>filter(()=>setReadState((readState+1)%3))}/>
 <Button label={t(scheduled?'notifications.scheduled':'notifications.due')} variant="secondary" onPress={()=>filter(()=>setScheduled(!scheduled))}/>
 <Button label={category?t(`notifications.categories.${category}`):t('notifications.allCategories')} variant="secondary" onPress={()=>filter(()=>setCategory(notificationCategories[(notificationCategories.indexOf(category)+1)%(notificationCategories.length+1)]??''))}/>
 <Button label={t('notifications.sort')} variant="text" onPress={()=>filter(()=>setAscending(!ascending))}/>
 <Button label={t('notifications.readAll')} variant="text" onPress={()=>{void notificationApi.readAll().then(()=>query.refetch()).catch(()=>setError(true));}}/>
 {error&&<AppText>{t('work.error')}</AppText>}
 {query.isPending?<LoadingSkeleton/>:query.isError?<ErrorState message={t('work.error')} retry={()=>void query.refetch()}/>:<>
 {!query.data.items.length&&<AppText>{t('notifications.empty')}</AppText>}
 {query.data.items.map(item=>{const Icon=icons[item.category]??Bell;return <View key={item.id} style={{flexDirection:'row',alignItems:'center',gap:8}}><Icon size={22} color={theme.colors.text}/><View style={{flex:1}}><Button key={item.id} variant="secondary" label={`${item.read_at?'':'● '}${t(`notifications.categories.${item.category}`,item.category)}\n${item.message}\n${new Date(item.scheduled_at).toLocaleString()} · ${t(`notifications.status.${item.status}`,item.status)}`} onPress={()=>router.push(`/notifications/${item.id}` as Href)}/></View></View>;})}
 {offset>0&&<Button label={t('work.previous')} variant="secondary" onPress={()=>setOffset(Math.max(0,offset-30))}/>}
 {offset+30<query.data.total&&<Button label={t('work.next')} onPress={()=>setOffset(offset+30)}/>}
 </>}
 </Screen>;
}
