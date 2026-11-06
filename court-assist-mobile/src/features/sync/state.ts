import { create } from 'zustand';

type State = {
  connected: boolean | null; running: boolean; enabled: boolean; pending: number;
  failed: number; conflicts: number; lastSync: string | null; phase: 'pull' | 'push' | 'upload' | null;
};
export const initialSyncState: State = {
  connected: null, running: false, enabled: false, pending: 0, failed: 0, conflicts: 0, lastSync: null, phase: null,
};
export const useSyncState = create<State>(() => initialSyncState);

