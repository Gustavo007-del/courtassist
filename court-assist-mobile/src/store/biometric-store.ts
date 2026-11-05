import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';
import * as LocalAuthentication from 'expo-local-authentication';
import i18n from '../i18n';

const KEY = 'courtassist.biometric-lock';
type BiometricState = {
  enabled: boolean; locked: boolean;
  hydrate: () => Promise<void>;
  enable: () => Promise<boolean>;
  disable: () => Promise<void>;
  unlock: () => Promise<boolean>;
  lock: () => void;
  reset: () => Promise<void>;
};
export const useBiometricStore = create<BiometricState>((set, get) => ({
  enabled: false, locked: false,
  hydrate: async () => {
    try { const enabled = await SecureStore.getItemAsync(KEY) === '1'; set({ enabled, locked: enabled }); } catch { set({ enabled: false, locked: false }); }
  },
  enable: async () => {
    if (!await LocalAuthentication.hasHardwareAsync() || !await LocalAuthentication.isEnrolledAsync()) return false;
    const result = await LocalAuthentication.authenticateAsync({ promptMessage: i18n.t('security.verifyPrompt') });
    if (!result.success) return false;
    await SecureStore.setItemAsync(KEY, '1'); set({ enabled: true, locked: false }); return true;
  },
  disable: async () => { await SecureStore.deleteItemAsync(KEY); set({ enabled: false, locked: false }); },
  unlock: async () => {
    if (!get().enabled) { set({ locked: false }); return true; }
    const result = await LocalAuthentication.authenticateAsync({ promptMessage: i18n.t('security.unlockPrompt') });
    if (result.success) set({ locked: false });
    return result.success;
  },
  lock: () => { if (get().enabled) set({ locked: true }); },
  reset: async () => { await SecureStore.deleteItemAsync(KEY).catch(() => {}); set({ enabled: false, locked: false }); },
}));
