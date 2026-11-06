import { useEffect, useRef } from 'react';
import { AppState, Platform } from 'react-native';
import { router, type Href } from 'expo-router';
import * as Notifications from 'expo-notifications';
import { useAuthStore } from '../store/auth-store';
import { useBiometricStore } from '../store/biometric-store';
import { clearNotifications,syncNotifications,notificationId,observeNotification } from '../services/notification-manager';
import { notificationApi } from '../services/notification-api';
import { onApiMutation } from '../services/api';

Notifications.setNotificationHandler({handleNotification:async()=>({shouldShowBanner:true,shouldShowList:true,shouldPlaySound:false,shouldSetBadge:false})});
export function NotificationLifecycle(){
 const owner=useAuthStore(state=>state.user?.id);const previous=useRef<string|undefined>(undefined);const pending=useRef<string|null>(null);
 useEffect(()=>{
  if(Platform.OS==='web')return;
  const open=async(id:string)=>{
   if(!useAuthStore.getState().user){pending.current=id;return;}
   // API ownership check precedes navigation. Native payloads never supply routes.
   const owner=useAuthStore.getState().user?.id;
   try{await notificationApi.get(id);if(useAuthStore.getState().user?.id!==owner)return;pending.current=null;router.push(`/notifications/${id}` as Href);}catch{pending.current=null;}
  };
  const subscription=Notifications.addNotificationResponseReceivedListener(response=>{const id=notificationId(response.notification.request.content.data);if(id)void open(id);});
  const received=Notifications.addNotificationReceivedListener(notification=>{const id=notificationId(notification.request.content.data);if(id)void observeNotification(id).catch(()=>{});});
  const token=Notifications.addPushTokenListener(()=>{void syncNotifications().catch(()=>{});});
  void Notifications.getLastNotificationResponseAsync().then(response=>{const id=notificationId(response?.notification.request.content.data);if(id){void open(id);void Notifications.clearLastNotificationResponseAsync();}});
  return()=>{subscription.remove();received.remove();token.remove();};
 },[]);
 useEffect(()=>{
  if(previous.current!==owner){void clearNotifications().then(()=>owner?syncNotifications():undefined).catch(()=>{});previous.current=owner;}
  if(owner&&pending.current){const id=pending.current;pending.current=null;void notificationApi.get(id).then(()=>{if(useAuthStore.getState().user?.id===owner)router.push(`/notifications/${id}` as Href);}).catch(()=>{});}
  const sync=()=>{if(owner&&AppState.currentState==='active')void syncNotifications().catch(()=>{});};
  const subscription=AppState.addEventListener('change',state=>{if(state==='active')sync();else useBiometricStore.getState().lock();});
  const interval=setInterval(sync,60_000);let timer:ReturnType<typeof setTimeout>|undefined;
  const unsubscribe=onApiMutation(()=>{clearTimeout(timer);timer=setTimeout(sync,500);});
  return()=>{subscription.remove();clearInterval(interval);clearTimeout(timer);unsubscribe();};
 },[owner]);
 return null;
}
