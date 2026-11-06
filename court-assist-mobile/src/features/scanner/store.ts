import { create } from 'zustand';
import { File } from 'expo-file-system';
import { discardSession, loadSession, persistPage, saveSession } from './storage';
import { scannerId, type ScanPage } from './types';

type ScannerState = { userId: string | null; pages: ScanPage[]; busy: boolean; signatureUri: string | null; setSignature: (uri: string | null) => void;
  hydrate: (userId: string) => Promise<void>;
  add: (uri: string, width: number, height: number) => Promise<void>;
  replace: (id: string, uri: string, width: number, height: number) => Promise<void>;
  update: (id: string, changes: Partial<ScanPage>) => Promise<void>;
  remove: (id: string) => Promise<void>;
  move: (id: string, direction: -1 | 1) => Promise<void>;
  clear: () => Promise<void>;
};
const persist = async (userId: string | null, pages: ScanPage[]) => { if (userId) await saveSession(userId, pages); };
export const useScannerStore = create<ScannerState>((set, get) => ({
  userId: null, pages: [], busy: false, signatureUri: null, setSignature: (uri) => { const old = get().signatureUri; set({ signatureUri: uri }); if (old && old !== uri) { const file = new File(old); if (file.exists) file.delete(); } },
  hydrate: async (userId) => { if (get().userId === userId) return; set({ busy: true }); try { set({ userId, pages: await loadSession(userId) }); } finally { set({ busy: false }); } },
  add: async (uri, width, height) => { const { userId, pages } = get(); if (!userId) throw new Error('Scanner session is unavailable'); const id = scannerId(); const saved = await persistPage(userId, uri, id); const next = [...pages, { id, originalUri: saved, uri: saved, originalWidth: width, originalHeight: height, width, height, rotation: 0 }]; await persist(userId, next); set({ pages: next }); },
  replace: async (id, uri, width, height) => { const { userId, pages } = get(); if (!userId) throw new Error('Scanner session is unavailable'); const saved = await persistPage(userId, uri, scannerId()); const previous = pages.find((page) => page.id === id); const next = pages.map((page) => page.id === id ? { id, originalUri: saved, uri: saved, originalWidth: width, originalHeight: height, width, height, rotation: 0 } : page); await persist(userId, next); set({ pages: next }); if (previous) for (const oldUri of new Set([previous.originalUri, previous.uri])) { const file = new File(oldUri); if (file.exists) file.delete(); } },
  update: async (id, changes) => { const { userId, pages } = get(); const next = pages.map((page) => page.id === id ? { ...page, ...changes } : page); await persist(userId, next); set({ pages: next }); },
  remove: async (id) => { const { userId, pages } = get(); const target = pages.find((page) => page.id === id); const next = pages.filter((page) => page.id !== id); await persist(userId, next); set({ pages: next }); if (target) for (const uri of new Set([target.originalUri, target.uri])) { const file = new File(uri); if (file.exists) file.delete(); } },
  move: async (id, direction) => { const { userId, pages } = get(); const index = pages.findIndex((page) => page.id === id); const target = index + direction; if (index < 0 || target < 0 || target >= pages.length) return; const next = [...pages]; [next[index], next[target]] = [next[target], next[index]]; await persist(userId, next); set({ pages: next }); },
  clear: async () => { const { userId, pages } = get(); if (userId) await discardSession(userId, pages); set({ pages: [] }); },
}));
