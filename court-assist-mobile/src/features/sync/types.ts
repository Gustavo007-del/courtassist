export type Data = Record<string, unknown>;
export type Change = { kind: string; id: string; revision: string; deleted: boolean; record: Data | null };
export type Operation = {
  id: string; kind: string; entity_id: string; action: string; payload: Data;
  base_revision: string; depends_on: string[]; after_operation_id?: string;
  base_updated_at?: string;
  local_version?: number;
};
export type Result = {
  id: string; status: 'applied' | 'conflict' | 'invalid' | 'blocked' | 'retryable';
  error?: string; revision?: string; server?: Change;
};
export type QueueState = 'pending' | 'retry' | 'failed' | 'conflict' | 'blocked' | 'applied' | 'discarded';
export type QueueItem = {
  seq: number; id: string; kind: string; entity: string; status: QueueState; retries: number;
  next_attempt: number; created_at: string; last_attempt: string | null; upload: string | null;
  error: string | null; operation: Operation; result: Result | null;
};
export type Control = {
  enabled: number; automatic: number; cursor: string; last_sync: string | null;
  device: string; verified_at: number; expires_at: number; profile: string | null;
};

