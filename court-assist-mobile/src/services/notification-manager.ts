import { ApiError } from './api';
import { Platform, Linking } from 'react-native';
import * as Notifications from 'expo-notifications';
import * as SecureStore from 'expo-secure-store';
import * as Crypto from 'expo-crypto';
import { notificationApi, type NotificationItem } from './notification-api';
import { notificationPrefix,planActions } from './notification-plan';
import { useAuthStore } from '../store/auth-store';

let currentDevice:{owner:string;id:string}|null=null;
let chain:Promise<unknown>=Promise.resolve();
const serialized=<T>(run:()=>Promise<T>):Promise<T>=>{const result=chain.then(run,run);chain=result.catch(()=>{});return result;};
const sameOwner=(owner:string)=>useAuthStore.getState().user?.id===owner;
export function notificationDestination(row:NotificationItem):string|null{
 if(!row.entity_id||! /^[0-9a-f-]{36}$/i.test(row.entity_id))return null;
 if(row.entity_type==='draft')return `/practice-tools/draft-editor?id=${row.entity_id}`;
 if(row.entity_type==='agreement'||row.entity_type==='invoice')return `/finance/detail?kind=${row.entity_type==='agreement'?'fee-agreements':'invoices'}&id=${row.entity_id}`;
 const routes:Record<string,string>={hearing:'hearings',task:'tasks',appointment:'appointments',document:'documents',draft:'drafting',agreement:'finance/agreements',invoice:'finance/invoices'};
 return row.entity_type&&routes[row.entity_type]?`/${routes[row.entity_type]}/${row.entity_id}`:null;
}
async function channel(){
 if(Platform.OS==='android')await Notifications.setNotificationChannelAsync('court-assist-reminders',{name:'Court Assist',importance:3,lockscreenVisibility:0,bypassDnd:false});
}
export async function requestNotificationPermission(){
 if(Platform.OS==='web')return false;
 await channel();const permission=await Notifications.getPermissionsAsync();
 const asked=await SecureStore.getItemAsync('courtassist.notificationPermissionAsked');
 if(!permission.granted&&asked){await Linking.openSettings();return false;}
 if(!permission.granted){await SecureStore.setItemAsync('courtassist.notificationPermissionAsked','1');if(!(await Notifications.requestPermissionsAsync()).granted)return false;}
 await syncNotifications(true);return true;
}
export function getNotificationDeviceId(){return currentDevice?.id??null;}
async function clearNative(){
 currentDevice=null;if(Platform.OS==='web')return;
 for(const row of await Notifications.getAllScheduledNotificationsAsync())if(row.identifier.startsWith('court-assist-'))await Notifications.cancelScheduledNotificationAsync(row.identifier);
 await Notifications.dismissAllNotificationsAsync();
 try{await Notifications.unregisterForNotificationsAsync();}catch{/* Native Firebase may be unconfigured. */}
}
export function clearNotifications(){return serialized(clearNative);}
export function syncNotifications(reactivate=false){return serialized(async()=>{
 if(Platform.OS==='web')return;
 const owner=useAuthStore.getState().user?.id;if(!owner)return;
 const config=await notificationApi.preferences();if(!sameOwner(owner))return;
 await channel();const permission=await Notifications.getPermissionsAsync();
 let installation=await SecureStore.getItemAsync('courtassist.installation');
 if(!installation){installation=Crypto.randomUUID();await SecureStore.setItemAsync('courtassist.installation',installation);}
 let token:string|null=null;
 if(config.preferences.push_notifications&&config.capabilities.push_configured&&permission.granted&&Platform.OS==='android'){
  try{token=String((await Notifications.getDevicePushTokenAsync()).data);}catch{/* Development build and Firebase client config required. */}
 }
 if(!sameOwner(owner))return;
 let device;
 try{device=await notificationApi.register({installation_id:installation,platform:Platform.OS==='android'?'android':'ios',label:Platform.OS,token,reactivate});}
 catch(error){if(error instanceof ApiError&&error.status===409){await clearNative();return;}throw error;}
 if(!sameOwner(owner))return;currentDevice={owner,id:device.id};
 const result=await notificationApi.localPlan(device.id,permission.granted);if(!sameOwner(owner))return;
 const scheduled=await Notifications.getAllScheduledNotificationsAsync();
 const actions=planActions(permission.granted?result.active_ids:[],permission.granted?result.plans:[],scheduled.map(row=>({identifier:row.identifier,at:typeof row.content.data?.scheduled_at==='string'?row.content.data.scheduled_at:undefined})),Date.now());
 for(const id of actions.cancel)await Notifications.cancelScheduledNotificationAsync(id);
 for(const plan of actions.schedule){
  if(!sameOwner(owner))return;
  const identifier=notificationPrefix+plan.id;
  await Notifications.scheduleNotificationAsync({identifier,content:{title:plan.title,body:plan.message,data:{notification_id:plan.id,scheduled_at:plan.scheduled_at}},trigger:{type:Notifications.SchedulableTriggerInputTypes.DATE,date:new Date(plan.scheduled_at),channelId:'court-assist-reminders'}});
  try{await notificationApi.ack(device.id,plan);}catch{await Notifications.cancelScheduledNotificationAsync(identifier);}
 }
});}
export function notificationId(data:Record<string,unknown>|undefined){const value=data?.notification_id;return typeof value==='string'&&/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)?value:null;}
export async function observeNotification(id:string){if(currentDevice&&sameOwner(currentDevice.owner))await notificationApi.observed(id,currentDevice.id);}
