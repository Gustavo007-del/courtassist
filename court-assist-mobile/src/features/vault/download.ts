import { Directory, File, Paths } from 'expo-file-system';
import { documentApi, type VaultDocument } from '../../services/document-api';

export function cachedDocument(userId: string, doc: VaultDocument, versionId?: string) {
  return new File(new Directory(Paths.document, 'private-vault', userId), `${doc.id}_${versionId ?? doc.current_version_id}${doc.file_extension}`);
}

export async function secureDownload(userId: string, doc: VaultDocument, versionId?: string) {
  const destination = cachedDocument(userId, doc, versionId);
  if (destination.exists) return destination;
  const folder = new Directory(Paths.document, 'private-vault', userId);
  folder.create({ idempotent: true, intermediates: true });
  for (let attempt = 0; attempt < 2; attempt++) {
    const signed = await documentApi.downloadUrl(doc.id, versionId);
    try { return await File.downloadFileAsync(signed.url, destination); }
    catch (error) { if (destination.exists) destination.delete(); if (attempt === 1) throw error; }
  }
  throw new Error('Secure download failed');
}
