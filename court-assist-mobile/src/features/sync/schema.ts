import { openLocalDatabase } from '../../database';

let migrated: ReturnType<typeof openLocalDatabase> | undefined;
export function syncDatabase() {
  migrated ??= openLocalDatabase().then(async db => {
    await db.execAsync('PRAGMA busy_timeout = 5000; PRAGMA journal_mode = WAL; PRAGMA secure_delete = ON;');
    await db.withExclusiveTransactionAsync(async tx => {
      await tx.execAsync(`
        CREATE TABLE IF NOT EXISTS sync_schema (version INTEGER PRIMARY KEY);
        INSERT OR IGNORE INTO sync_schema VALUES (1);
        CREATE TABLE IF NOT EXISTS sync_control (
          owner TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0, automatic INTEGER NOT NULL DEFAULT 1,
          cursor TEXT NOT NULL DEFAULT '0', last_sync TEXT, device TEXT NOT NULL,
          verified_at INTEGER NOT NULL DEFAULT 0, expires_at INTEGER NOT NULL DEFAULT 0, profile TEXT
        );
        CREATE TABLE IF NOT EXISTS sync_entities (
          owner TEXT NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL, revision TEXT NOT NULL DEFAULT '0',
          local_version INTEGER NOT NULL DEFAULT 0, pending TEXT, deleted INTEGER NOT NULL DEFAULT 0,
          body TEXT, synced_at TEXT, PRIMARY KEY (owner, kind, id)
        );
        CREATE TABLE IF NOT EXISTS sync_queue (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, id TEXT NOT NULL,
          kind TEXT NOT NULL, entity TEXT NOT NULL, status TEXT NOT NULL, retries INTEGER NOT NULL DEFAULT 0,
          next_attempt INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, last_attempt TEXT, upload TEXT,
          error TEXT, body TEXT, result TEXT, UNIQUE (owner, id)
        );
        CREATE INDEX IF NOT EXISTS sync_queue_ready ON sync_queue(owner, status, next_attempt, seq);
        CREATE INDEX IF NOT EXISTS sync_queue_record ON sync_queue(owner, kind, entity, seq);
        CREATE TABLE IF NOT EXISTS sync_http (
          owner TEXT NOT NULL, key TEXT NOT NULL, body TEXT NOT NULL, saved_at INTEGER NOT NULL,
          PRIMARY KEY (owner, key)
        );
        CREATE TABLE IF NOT EXISTS sync_files (
          owner TEXT NOT NULL, id TEXT NOT NULL, version TEXT NOT NULL, purpose TEXT NOT NULL,
          body TEXT NOT NULL, PRIMARY KEY(owner, id, version, purpose)
        );
        CREATE TABLE IF NOT EXISTS sync_runs (
          id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, ran_at TEXT NOT NULL,
          duration INTEGER NOT NULL, status TEXT NOT NULL, applied INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS sync_runs_owner ON sync_runs(owner, id);
      `);
    });
    return db;
  }).catch(error => { migrated = undefined; throw error; });
  return migrated;
}

