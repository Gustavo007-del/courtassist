import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';
import type { ThemeMode } from '../features/auth/types';

const KEY = 'courtassist.theme';
type ThemeState = { mode: ThemeMode; hydrate: () => Promise<void>; setMode: (mode: ThemeMode) => Promise<void> };
export const useThemeStore = create<ThemeState>((set) => ({
  mode: 'system',
  hydrate: async () => {
    try { const saved = await SecureStore.getItemAsync(KEY); if (saved === 'light' || saved === 'dark' || saved === 'system') set({ mode: saved }); } catch { /* use system */ }
  },
  setMode: async (mode) => { set({ mode }); await SecureStore.setItemAsync(KEY, mode); },
}));
