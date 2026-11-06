import { useState } from 'react';
import { router,useLocalSearchParams,type Href } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Button } from '../../components/common/Button';
import { TextField } from '../../components/common/TextField';
import { AppText } from '../../components/common/AppText';
import { notificationApi } from '../../services/notification-api';
import { apiRequest } from '../../services/api';
import { syncNotifications } from '../../services/notification-manager';
export default function Create(){
 const params=useLocalSearchParams<{entity_type?:string;entity_id?:string;replaces?:string}>();const {t}=useTranslation();
 const [kind,setKind]=useState(params.entity_type??'document');const [entity,setEntity]=useState(params.entity_id??'');const [search,setSearch]=useState('');const [day,setDay]=useState('');const [clock,setClock]=useState('09:00');const [priority,setPriority]=useState('normal');const [purpose,setPurpose]=useState('general');const [error,setError]=useState(false);const [busy,setBusy]=useState(false);
 const preferences=useQuery({queryKey:['notification-preferences'],queryFn:notificationApi.preferences});
 const paths:Record<string,string>={document:'/documents',draft:'/draft-documents',agreement:'/fee-agreements',invoice:'/invoices'};
 const records=useQuery({queryKey:['reminder-records',kind,search],queryFn:()=>apiRequest<{items?:{id:string;title?:string;document_title?:string;invoice_number?:string;document_name?:string;number?:string;category?:string}[]}|{id:string;title?:string;invoice_number?:string;document_name?:string;number?:string;category?:string}[]>(`${paths[kind]}?q=${encodeURIComponent(search)}&limit=30`),enabled:!params.entity_id});
 const save=async()=>{setError(false);setBusy(true);try{const row=await notificationApi.manual({entity_type:kind,entity_id:entity,local_date:day,local_time:clock,priority,purpose,replaces:params.replaces});await syncNotifications().catch(()=>{});router.replace(`/notifications/${row.id}` as Href);}catch{setError(true);}finally{setBusy(false);}};
 const items=Array.isArray(records.data)?records.data:records.data?.items??[];
 return <Screen back title={t('notifications.newReminder')} subtitle={t('notifications.followupExplanation')}>
 <AppText>{t('notifications.timezone')}: {preferences.data?.preferences.timezone??'…'}</AppText>
 {!params.entity_id&&<><Button variant="secondary" label={t(`notifications.entities.${kind}`)} onPress={()=>{const kinds=['document','draft','agreement','invoice'];setKind(kinds[(kinds.indexOf(kind)+1)%4]);setEntity('');}}/><TextField label={t('work.search')} value={search} onChangeText={setSearch}/>{items.map(item=><Button key={item.id} variant="secondary" label={`${entity===item.id?'✓ ':''}${item.title||item.document_name||item.number||item.invoice_number||item.category||item.id}`} onPress={()=>setEntity(item.id)}/>)}</>}
 <TextField label={t('notifications.date')} value={day} onChangeText={setDay}/>
 <TextField label={t('notifications.time')} value={clock} onChangeText={setClock}/>
 <Button variant="secondary" label={t(`notifications.priorities.${priority}`)} onPress={()=>{const values=['normal','high','urgent'];setPriority(values[(values.indexOf(priority)+1)%3]);}}/>
 <Button variant="secondary" label={t(`notifications.purposes.${purpose}`)} onPress={()=>{const values=['general','review','filing','collection','payment'];setPurpose(values[(values.indexOf(purpose)+1)%5]);}}/>
 {error&&<AppText>{t('notifications.saveError')}</AppText>}<Button label={t('save')} loading={busy} disabled={!entity||!day||!clock} onPress={()=>void save()}/>
 </Screen>;
}
