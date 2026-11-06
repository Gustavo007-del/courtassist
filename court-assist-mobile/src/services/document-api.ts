import { File } from 'expo-file-system';
import { fetch as expoFetch } from 'expo/fetch';
import { apiRequest } from './api';

export type VaultDocument = { id: string; user_id: string; case_id: string | null; client_id: string | null; hearing_id: string | null; document_name: string; original_filename: string; file_extension: string; mime_type: string; file_size: number; page_count: number | null; document_category: string; description: string; storage_provider: string; storage_status: string; checksum: string | null; is_archived: boolean; current_version_id: string | null; uploaded_at: string | null; created_at: string; updated_at: string; case_number?: string | null; client_name?: string | null; snippet?: string | null; page_number?: number | null };
export type VaultVersion = { id: string; document_id: string; user_id: string; version_number: number; original_filename: string; file_size: number; checksum: string | null; change_description: string; storage_status: string; created_at: string };
export type VaultOCR = { id: string; document_id: string; document_version_id: string; processing_status: string; processing_provider: string; extracted_text: string; language_detected: string | null; page_results: { page_number: number | null; extracted_text: string; language: string | null; confidence_score: number | null; processing_status: string }[]; error_message: string | null; processed_at: string | null };
export type SignedURL = { url: string; expires_in: number; document_id: string; version_id: string };
type Filters = Record<string, string | number | boolean | null | undefined>;
const qs = (filters: Filters) => new URLSearchParams(Object.entries(filters).filter(([, value]) => value !== null && value !== undefined && value !== '').map(([key, value]) => [key, String(value)])).toString();

export const documentApi = {
  list: (filters: Filters = {}) => apiRequest<VaultDocument[]>(`/documents?${qs(filters)}`),
  search: (q: string, filters: Filters = {}) => apiRequest<{ items: VaultDocument[] }>(`/documents/search?${qs({ q, ...filters })}`),
  get: (id: string) => apiRequest<VaultDocument>(`/documents/${id}`),
  create: (data: object) => apiRequest<VaultDocument>('/documents', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: object) => apiRequest<VaultDocument>(`/documents/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  archive: (id: string) => apiRequest<void>(`/documents/${id}`, { method: 'DELETE' }),
  uploadUrl: (documentId: string, versionId?: string) => apiRequest<SignedURL>('/documents/upload-url', { method: 'POST', body: JSON.stringify({ document_id: documentId, version_id: versionId ?? null }) }),
  confirm: (documentId: string, versionId: string) => apiRequest<VaultDocument>('/documents/confirm-upload', { method: 'POST', body: JSON.stringify({ document_id: documentId, version_id: versionId }) }),
  downloadUrl: (id: string, versionId?: string) => apiRequest<SignedURL>(versionId ? `/documents/${id}/versions/${versionId}/download-url` : `/documents/${id}/download-url`),
  versions: (id: string) => apiRequest<VaultVersion[]>(`/documents/${id}/versions`),
  createVersion: (id: string, data: object) => apiRequest<VaultVersion>(`/documents/${id}/versions`, { method: 'POST', body: JSON.stringify(data) }),
  ocr: (id: string) => apiRequest<VaultOCR>(`/documents/${id}/ocr`),
  startOcr: (id: string) => apiRequest<VaultOCR>(`/documents/${id}/ocr`, { method: 'POST' }),
  retryOcr: (id: string) => apiRequest<VaultOCR>(`/documents/${id}/ocr/retry`, { method: 'POST' }),
  suggestions: (id: string) => apiRequest<{ suggestions: { field: string; value: string; source_text: string; page_number: number | null; confidence: number | null }[] }>(`/documents/${id}/extracted-metadata`),
  confirmSuggestions: (id: string, reviewed: { field: string; source_value: string; status: 'accepted' | 'edited' | 'rejected'; value: string }[]) => apiRequest<object>(`/documents/${id}/extracted-metadata/confirm`, { method: 'POST', body: JSON.stringify({ reviewed }) }),
  caseDocuments: (id: string) => apiRequest<VaultDocument[]>(`/cases/${id}/documents`),
  clientDocuments: (id: string) => apiRequest<VaultDocument[]>(`/clients/${id}/documents`),
  hearingDocuments: (id: string) => apiRequest<VaultDocument[]>(`/hearings/${id}/documents`),
};

export async function putPrivateFile(uri: string, signed: SignedURL, mimeType: string) {
  const file = new File(uri);
  if (!file.exists) throw new Error('Local file is unavailable');
  const response = await expoFetch(signed.url, { method: 'PUT', headers: { 'Content-Type': mimeType }, body: file });
  if (!response.ok) throw new Error(response.status === 403 ? 'Upload URL expired; retry the upload' : 'Private upload failed');
}
