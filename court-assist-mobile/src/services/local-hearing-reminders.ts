import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import type { Reminder } from './hearing-api';

const identifier = (id: string) => `court-assist-hearing-${id}`;

export async function cancelLocalReminder(id: string) {
  if (Platform.OS === 'web') return;
  await Notifications.cancelScheduledNotificationAsync(identifier(id));
}

export async function scheduleLocalReminder(reminder: Reminder, title: string, body: string) {
  if (Platform.OS === 'web' || reminder.delivery_channel !== 'local') return false;
  await cancelLocalReminder(reminder.id);
  if (reminder.status === 'cancelled') return false;
  const date = new Date(reminder.scheduled_at);
  if (!Number.isFinite(date.getTime()) || date.getTime() <= Date.now()) return false;
  const permission = await Notifications.getPermissionsAsync();
  const allowed = permission.granted || (await Notifications.requestPermissionsAsync()).granted;
  if (!allowed) throw new Error('Notification permission was denied');
  await Notifications.scheduleNotificationAsync({
    identifier: identifier(reminder.id),
    content: { title, body },
    trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date },
  });
  return true;
}
