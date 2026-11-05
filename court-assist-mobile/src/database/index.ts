import * as SQLite from 'expo-sqlite';

// Future offline modules own their tables and migrations. No case data is cached in Phase 1.
export async function openLocalDatabase() {
  return SQLite.openDatabaseAsync('court-assist.db');
}
