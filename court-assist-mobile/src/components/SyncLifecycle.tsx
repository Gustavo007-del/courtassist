import { useEffect } from 'react';
import { AppState, Platform } from 'react-native';
import * as Network from 'expo-network';
import { useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../store/auth-store';
import { onApiMutation } from '../services/api';
import { setBackgroundSync } from '../features/sync/background';
import { publishStatus, syncNow } from '../features/sync/engine';
import { control } from '../features/sync/repository';
import { purgeScratch } from '../features/sync/files';
import { canRestore } from '../features/sync/policy';
import { initialSyncState, useSyncState } from '../features/sync/state';

export function SyncLifecycle() {
  const owner = useAuthStore(state => state.user?.id);
  const cache = useQueryClient();
  useEffect(() => {
    if (Platform.OS === 'web') return;
    let active = true;
    let debounce: ReturnType<typeof setTimeout> | undefined;
    const attempt = async () => {
      if (!active || AppState.currentState !== 'active' || !owner) return;
      const info = await control(owner);
      if (!active || useAuthStore.getState().user?.id !== owner) return;
      if (info?.enabled && useSyncState.getState().connected === false
          && !canRestore(info.verified_at, info.expires_at, Date.now())) {
        await useAuthStore.getState().clear(true);
        return;
      }
      const changed = await syncNow(owner);
      if (active && changed) void cache.invalidateQueries();
    };
    const schedule = () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => void attempt().catch(() => {}), 700);
    };
    const update = (network: Network.NetworkState) => {
      if (!active) return;
      const connected = network.isConnected === undefined ? null : network.isConnected;
      useSyncState.setState({ connected });
      schedule();
    };
    const network = Network.addNetworkStateListener(update);
    void Network.getNetworkStateAsync().then(update).catch(() => {});
    const app = AppState.addEventListener('change', state => {
      if (state === 'active') {
        if (owner) purgeScratch(owner);
        void Network.getNetworkStateAsync().then(update).catch(() => {});
      }
    });
    const offMutation = onApiMutation(schedule);
    const timer = setInterval(schedule, 60_000);
    if (owner) {
      void publishStatus(owner).catch(() => {});
      void control(owner).then(info => { if (active) return setBackgroundSync(!!info?.enabled && !!info.automatic); }).catch(() => {});
    } else {
      useSyncState.setState(initialSyncState);
      void setBackgroundSync(false).catch(() => {});
    }
    return () => { active = false; clearTimeout(debounce); clearInterval(timer); network.remove(); app.remove(); offMutation(); };
  }, [cache, owner]);
  return null;
}

