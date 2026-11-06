import { Platform } from 'react-native';
import * as BackgroundTask from 'expo-background-task';
import * as TaskManager from 'expo-task-manager';
import * as Network from 'expo-network';
import { useAuthStore } from '../../store/auth-store';
import { control } from './repository';
import { syncNow } from './engine';
import { useSyncState } from './state';

const task = 'courtassist-private-sync';
if (Platform.OS !== 'web') {
  TaskManager.defineTask(task, async () => {
    try {
      const auth = useAuthStore.getState();
      if (!auth.hydrated) await auth.hydrate();
      if (!await auth.restoreOffline()) return BackgroundTask.BackgroundTaskResult.Success;
      const owner = useAuthStore.getState().user?.id;
      if (!owner || !(await control(owner))?.automatic) return BackgroundTask.BackgroundTaskResult.Success;
      const network = await Network.getNetworkStateAsync();
      useSyncState.setState({ connected: network.isConnected !== false });
      if (network.isConnected !== false) await syncNow(owner, false, true);
      return BackgroundTask.BackgroundTaskResult.Success;
    } catch {
      return BackgroundTask.BackgroundTaskResult.Failed;
    }
  });
}

export async function setBackgroundSync(enabled: boolean) {
  if (Platform.OS === 'web' || !await TaskManager.isAvailableAsync()) return;
  const registered = await TaskManager.isTaskRegisteredAsync(task);
  if (enabled && !registered && await BackgroundTask.getStatusAsync() === BackgroundTask.BackgroundTaskStatus.Available) {
    await BackgroundTask.registerTaskAsync(task, { minimumInterval: 30 });
  } else if (!enabled && registered) {
    await BackgroundTask.unregisterTaskAsync(task);
  }
}

