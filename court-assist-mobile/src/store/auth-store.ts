import { create } from 'zustand';
import * as SecureStore from 'expo-secure-store';
import type { Advocate, TokenResponse } from '../features/auth/types';
import { useBiometricStore } from './biometric-store';

const REFRESH_KEY = 'courtassist.refresh';
type AuthState = { accessToken: string | null; refreshToken: string | null; user: Advocate | null; hydrated: boolean; setTokens: (tokens: TokenResponse) => Promise<void>; clear: () => Promise<void>; hydrate: () => Promise<void> };
export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null, refreshToken: null, user: null, hydrated: false,
  setTokens: async (tokens) => { await SecureStore.setItemAsync(REFRESH_KEY, tokens.refresh_token); set({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token, user: tokens.user, hydrated: true }); },
  clear: async () => { await SecureStore.deleteItemAsync(REFRESH_KEY); await useBiometricStore.getState().reset(); set({ accessToken: null, refreshToken: null, user: null, hydrated: true }); },
  hydrate: async () => { try { const token = await SecureStore.getItemAsync(REFRESH_KEY); set({ refreshToken: token, hydrated: true }); } catch { set({ hydrated: true }); } },
}));
