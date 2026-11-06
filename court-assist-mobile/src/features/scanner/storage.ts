import { Directory, File, Paths } from 'expo-file-system';
import { openLocalDatabase } from '../../database';
import { scannerId, type LocalDocument, type ScanPage } from './types';

const root = (userId: string) => new Directory(Paths.document, 'private-scans', userId);
const sessionFile = (userId: string) => new File(root(userId), 'session.json');
export function ensureScanDirectory(userId: string) { const folder = root(userId); folder.create({ idempotent: true, intermediates: true }); return folder; }
export async function persistPage(userId: string, sourceUri: string, id: string): Promise<string> {
  const folder = ensureScanDirectory(userId);
  const destination = new File(folder, `${id}.jpg`);
  await new File(sourceUri).copy(destination);
  return destination.uri;
}
export async function persistSignature(userId: string, sourceUri: string, id: string): Promise<string> { const destination = new File(ensureScanDirectory(userId), `${id}.png`); await new File(sourceUri).copy(destination); return destination.uri; }
export async function saveSession(userId: string, pages: ScanPage[]) { ensureScanDirectory(userId); const file = sessionFile(userId); file.create({ overwrite: true }); await file.write(JSON.stringify(pages)); }
export async function loadSession(userId: string): Promise<ScanPage[]> { const file = sessionFile(userId); if (!file.exists) return []; try { const pages = JSON.parse(await file.text()) as ScanPage[]; return pages.filter((page) => new File(page.uri).exists); } catch { return []; } }
export async function discardSession(userId: string, pages: ScanPage[]) { for (const page of pages) { for (const uri of new Set([page.uri, page.originalUri])) { const file = new File(uri); if (file.exists) file.delete(); } } const file = sessionFile(userId); if (file.exists) file.delete(); }
export async function writePermanentPdf(userId: string, id: string, bytes: Uint8Array) { const folder = ensureScanDirectory(userId); const file = new File(folder, `${id}.pdf`); file.create(); await file.write(bytes); return file; }

async function database() {
  const db = await openLocalDatabase();
  await db.execAsync('CREATE TABLE IF NOT EXISTS local_documents (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, case_id TEXT, document_name TEXT NOT NULL, original_filename TEXT NOT NULL, file_type TEXT NOT NULL, file_size INTEGER NOT NULL, page_count INTEGER NOT NULL, document_category TEXT NOT NULL, storage_status TEXT NOT NULL, local_uri TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL); CREATE INDEX IF NOT EXISTS ix_local_documents_user_created ON local_documents(user_id, created_at);');
  return db;
}
export async function saveDocument(item: LocalDocument) { const db = await database(); await db.runAsync('INSERT INTO local_documents (id,user_id,case_id,document_name,original_filename,file_type,file_size,page_count,document_category,storage_status,local_uri,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', item.id, item.user_id, item.case_id, item.document_name, item.original_filename, item.file_type, item.file_size, item.page_count, item.document_category, item.storage_status, item.local_uri, item.created_at, item.updated_at); }
export async function listDocuments(userId: string): Promise<LocalDocument[]> { const db = await database(); return db.getAllAsync<LocalDocument>('SELECT * FROM local_documents WHERE user_id = ? ORDER BY created_at DESC', userId); }
export async function getDocument(userId: string, id: string): Promise<LocalDocument | null> { const db = await database(); return db.getFirstAsync<LocalDocument>('SELECT * FROM local_documents WHERE user_id = ? AND id = ?', userId, id); }
export async function deleteDocument(userId: string, id: string) { const item = await getDocument(userId, id); if (!item) return; const file = new File(item.local_uri); if (file.exists) file.delete(); const db = await database(); await db.runAsync('DELETE FROM local_documents WHERE user_id = ? AND id = ?', userId, id); }
export async function savePdfCopy(userId: string, bytes: Uint8Array, name: string, pageCount: number, caseId: string | null = null, category: LocalDocument['document_category'] = 'Other') {
  const id = scannerId(); const file = await writePermanentPdf(userId, id, bytes); const now = new Date().toISOString();
  const item: LocalDocument = { id, user_id: userId, case_id: caseId, document_name: name, original_filename: `CourtAssist_${now.slice(0, 10)}_${id}.pdf`, file_type: 'application/pdf', file_size: file.size ?? bytes.byteLength, page_count: pageCount, document_category: category, storage_status: 'local_only', local_uri: file.uri, created_at: now, updated_at: now };
  try { await saveDocument(item); } catch (error) { if (file.exists) file.delete(); throw error; }
  return item;
}
