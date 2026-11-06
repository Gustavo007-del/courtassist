import { Directory, File, Paths } from 'expo-file-system';
import { CryptoDigestAlgorithm, digest, randomUUID } from 'expo-crypto';
import { networkRequest } from '../../services/api';
import { putPrivateFile, type SignedURL, type VaultDocument } from '../../services/document-api';
import { useAuthStore } from '../../store/auth-store';
import { pack, seal, unpack, unseal } from './crypto';
import { enqueue, serialized } from './repository';
import { syncDatabase } from './schema';
import { isUuid } from './policy';
import type { Data, QueueItem } from './types';

const limit = 25 * 1024 * 1024;
const ownedFolder = (owner: string, temporary = false) => {
  if (!isUuid(owner)) throw new Error('invalid_account');
  return new Directory(temporary ? Paths.cache : Paths.document, temporary ? 'offline-scratch' : 'offline-files', owner);
};
function file(owner: string, identifier: string, temporary = false, suffix = '.bin') {
  if (!isUuid(identifier)) throw new Error('invalid_file');
  const folder = ownedFolder(owner, temporary);
  folder.create({ intermediates: true, idempotent: true });
  return new File(folder, identifier + suffix);
}
const drop = (item: File | Directory) => { if (item.exists) item.delete(); };
const sha256 = async (bytes: Uint8Array) => Array.from(new Uint8Array(await digest(CryptoDigestAlgorithm.SHA256, new Uint8Array(bytes))))
  .map(value => value.toString(16).padStart(2, '0')).join('');
type FileRecord = { id: string; version: string; purpose: string; body: string };
type Meta = { name: string; mime: string; extension: string; checksum: string; blob: string };

async function persist(owner: string, bytes: Uint8Array, metadata: Omit<Meta, 'blob' | 'checksum'>) {
  if (!bytes.length || bytes.length > limit) throw new Error('offline_file_size');
  const blob = randomUUID();
  const destination = file(owner, blob);
  const checksum = await sha256(bytes);
  const encrypted = await (await seal(owner, `file:${blob}`, bytes)).combined();
  destination.create();
  try { destination.write(encrypted); } catch (error) { drop(destination); throw error; }
  return { ...metadata, blob, checksum };
}

export async function stageUpload(owner: string, uri: string, payload: Data) {
  const source = new File(uri);
  if (!source.exists || !source.size || source.size > limit) throw new Error('offline_file_size');
  const meta = await persist(owner, await source.bytes(), {
    name: String(payload.original_filename), mime: String(payload.mime_type), extension: '',
  });
  try {
    const id = randomUUID();
    const staged = await enqueue(owner, 'document', 'create', id, { ...payload, checksum: meta.checksum }, meta.blob);
    return staged;
  } catch (error) {
    drop(file(owner, meta.blob));
    throw error;
  }
}

export async function transfer(owner: string, item: QueueItem) {
  const check = () => { if (useAuthStore.getState().user?.id !== owner) throw new Error('offline_account_changed'); };
  check();
  const identifier = item.operation.entity_id;
  const doc = await networkRequest<VaultDocument>(`/documents/${identifier}`);
  if (doc.current_version_id && doc.storage_status === 'cloud_stored') {
    if (doc.checksum !== item.operation.payload.checksum) throw new Error('offline_file_changed');
    return;
  }
  const blob = item.upload!;
  const encrypted = file(owner, blob);
  const bytes = await unseal(owner, `file:${blob}`, await encrypted.bytes());
  const staging = file(owner, randomUUID(), true);
  try {
    staging.create();
    staging.write(bytes);
    check();
    const signed = await networkRequest<SignedURL>('/documents/upload-url', {
      method: 'POST', body: JSON.stringify({ document_id: identifier }),
    });
    await putPrivateFile(staging.uri, signed, doc.mime_type);
    check();
    await networkRequest('/documents/confirm-upload', {
      method: 'POST', body: JSON.stringify({ document_id: identifier, version_id: signed.version_id }),
    });
  } finally {
    drop(staging);
  }
}

export function finishUpload(owner: string, blob: string) {
  drop(file(owner, blob));
}

export async function pinnedFiles(owner: string) {
  const rows = await (await syncDatabase()).getAllAsync<FileRecord>(
    "SELECT * FROM sync_files WHERE owner=? AND purpose='pin' ORDER BY id", owner);
  return Promise.all(rows.map(async row => ({
    id: row.id, version: row.version, ...(await unpack<Meta>(owner, `pin:${row.id}:${row.version}`, row.body)),
  })));
}

export async function pinDocument(owner: string, doc: VaultDocument, progress: (fraction: number) => void, valid: () => boolean) {
  if (!doc.current_version_id || !doc.checksum || doc.file_size > limit) throw new Error('offline_file_unverified');
  const signed = await networkRequest<SignedURL>(`/documents/${doc.id}/versions/${doc.current_version_id}/download-url`);
  const staging = file(owner, randomUUID(), true);
  let meta: Meta | undefined;
  try {
    const task = File.createDownloadTask(signed.url, staging, {
      onProgress: ({ bytesWritten, totalBytes }) => {
        progress(Math.min(0.95, bytesWritten / (totalBytes || doc.file_size)));
      },
    });
    await task.downloadAsync();
    if (!valid() || staging.size !== doc.file_size) throw new Error('offline_file_changed');
    const bytes = await staging.bytes();
    if (await sha256(bytes) !== doc.checksum) throw new Error('offline_file_changed');
    meta = await persist(owner, bytes, { name: doc.document_name, mime: doc.mime_type, extension: doc.file_extension });
    const saved = meta;
    await serialized(async () => {
      if (!valid()) throw new Error('offline_account_changed');
      const db = await syncDatabase();
      const old = await db.getFirstAsync<FileRecord>("SELECT * FROM sync_files WHERE owner=? AND id=? AND version=? AND purpose='pin'",
        owner, doc.id, signed.version_id);
      const purpose = `pin:${doc.id}:${signed.version_id}`;
      await db.runAsync("INSERT OR REPLACE INTO sync_files VALUES(?,?,?,'pin',?)",
        owner, doc.id, signed.version_id, await pack(owner, purpose, saved));
      meta = undefined;
      if (old) {
        try { drop(file(owner, (await unpack<Meta>(owner, purpose, old.body)).blob)); }
        catch { /* Old encrypted blobs can be removed with the account's offline files. */ }
      }
    });
    progress(1);
  } catch (error) {
    if (meta) drop(file(owner, meta.blob));
    throw error;
  } finally {
    drop(staging);
  }
}

export async function removePin(owner: string, id: string, version: string) {
  await serialized(async () => {
    const db = await syncDatabase();
    const row = await db.getFirstAsync<FileRecord>("SELECT * FROM sync_files WHERE owner=? AND id=? AND version=? AND purpose='pin'",
      owner, id, version);
    if (!row) return;
    const meta = await unpack<Meta>(owner, `pin:${id}:${version}`, row.body);
    await db.runAsync("DELETE FROM sync_files WHERE owner=? AND id=? AND version=? AND purpose='pin'", owner, id, version);
    drop(file(owner, meta.blob));
  });
}

export async function previewPin(owner: string, id: string, version?: string) {
  const row = await (await syncDatabase()).getFirstAsync<FileRecord>(
    "SELECT * FROM sync_files WHERE owner=? AND id=? AND purpose='pin' AND (? IS NULL OR version=?) LIMIT 1",
    owner, id, version ?? null, version ?? null);
  if (!row) return false;
  const meta = await unpack<Meta>(owner, `pin:${id}:${row.version}`, row.body);
  const bytes = await unseal(owner, `file:${meta.blob}`, await file(owner, meta.blob).bytes());
  if (await sha256(bytes) !== meta.checksum) throw new Error('offline_file_changed');
  const suffix = /^\.[a-z0-9]{1,8}$/i.test(meta.extension) ? meta.extension : '.bin';
  const scratch = file(owner, randomUUID(), true, suffix);
  scratch.create();
  try {
    scratch.write(bytes);
    await scratch.preview({ title: meta.name, mimeType: meta.mime });
  } finally {
    // Android may open the content URI after the chooser returns.
    setTimeout(() => drop(scratch), 10 * 60_000);
  }
  return true;
}

export function purgeScratch(owner: string) {
  const folder = ownedFolder(owner, true);
  if (!folder.exists) return;
  for (const entry of folder.list()) {
    if (entry instanceof File && entry.modificationTime && Date.now() - entry.modificationTime > 10 * 60_000) drop(entry);
  }
}

export function clearFiles(owner: string, includeLegacy = false) {
  drop(ownedFolder(owner));
  drop(ownedFolder(owner, true));
  if (includeLegacy) {
    drop(new Directory(Paths.document, 'private-scans', owner));
    drop(new Directory(Paths.document, 'private-vault', owner));
  }
}

