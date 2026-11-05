import { create } from 'zustand';

type AppState = { toast: string | null; showToast: (message: string) => void; clearToast: () => void };
export const useAppStore = create<AppState>((set) => ({ toast: null, showToast: (message) => set({ toast: message }), clearToast: () => set({ toast: null }) }));
