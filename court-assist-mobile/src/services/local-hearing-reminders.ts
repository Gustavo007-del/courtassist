import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import type { Reminder } from './hearing-api';
import { syncNotifications } from './notification-manager';
export async function cancelLocalReminder(id:string){
 if(Platform.OS!=='web')await Notifications.cancelScheduledNotificationAsync(`court-assist-hearing-${id}`);
 await syncNotifications();
}
export async function scheduleLocalReminder(_reminder:Reminder,_title:string,_body:string){await syncNotifications();return false;}
