import { create } from 'zustand';
import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';
import type { Advocate, TokenResponse } from '../features/auth/types';
import { useBiometricStore } from './biometric-store';
import { useScannerStore } from '../features/scanner/store';
import { clearRecords, remember, restore } from '../features/sync/repository';
import { syncDatabase } from '../features/sync/schema';

const REFRESH_KEY = 'courtassist.refresh';
const OWNER_KEY = 'courtassist.offline.owner';
type AuthState = {
  accessToken: string | null; refreshToken: string | null; user: Advocate | null; hydrated: boolean;
  refreshExpiry: number; offlineSession: boolean;
  setTokens: (tokens: TokenResponse, expectedRefresh?: string) => Promise<void>;
  clear: (preserveOffline?: boolean) => Promise<void>;
  hydrate: () => Promise<void>;
  restoreOffline: () => Promise<boolean>;
};
let writes: Promise<unknown> = Promise.resolve();
function authWrite<T>(work: () => Promise<T>) {
  const result = writes.then(work, work);
  writes = result.catch(() => {});
  return result;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  accessToken: null, refreshToken: null, user: null, hydrated: false, refreshExpiry: 0, offlineSession: false,
  setTokens: (tokens, expectedRefresh) => authWrite(async () => {
    if (expectedRefresh && get().refreshToken !== expectedRefresh) return;
    const expiry = Date.now() + tokens.refresh_expires_in * 1000;
    await SecureStore.setItemAsync(REFRESH_KEY, tokens.refresh_token);
    await SecureStore.setItemAsync(OWNER_KEY, tokens.user.id);
    await remember(tokens.user, expiry).catch(() => {});
    set({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token, user: tokens.user,
      hydrated: true, refreshExpiry: expiry, offlineSession: false });
  }),
  clear: (preserveOffline = false) => authWrite(async () => {
    const owner = get().user?.id ?? await SecureStore.getItemAsync(OWNER_KEY).catch(() => null);
    set({ accessToken: null, refreshToken: null, user: null, hydrated: true, refreshExpiry: 0, offlineSession: false });
    await SecureStore.deleteItemAsync(REFRESH_KEY);
    await SecureStore.deleteItemAsync(OWNER_KEY);
    if (!preserveOffline) await useBiometricStore.getState().reset();
    useScannerStore.setState({ userId: null, pages: [], signatureUri: null });
    if (owner && !preserveOffline && Platform.OS !== 'web') {
      const { clearFiles } = await import('../features/sync/files');
      await clearRecords(owner);
      clearFiles(owner, true);
      const db = await syncDatabase();
      if (await db.getFirstAsync("SELECT 1 FROM sqlite_master WHERE type='table' AND name='local_documents'")) {
        await db.runAsync('DELETE FROM local_documents WHERE user_id=?', owner);
      }
    }
  }),
  hydrate: () => authWrite(async () => {
    try {
      const token = await SecureStore.getItemAsync(REFRESH_KEY);
      if (!get().accessToken) set({ refreshToken: token, hydrated: true });
    } catch { set({ hydrated: true }); }
  }),
  restoreOffline: () => authWrite(async () => {
    if (get().user) return true;
    if (!get().refreshToken || Platform.OS === 'web') return false;
    try {
      const owner = await SecureStore.getItemAsync(OWNER_KEY);
      const user = owner ? await restore(owner) : null;
      if (!user || user.id !== owner) return false;
      set({ user, offlineSession: true });
      return true;
    } catch { return false; }
  }),
}));
