export type ScanPage = { id: string; originalUri: string; uri: string; originalWidth: number; originalHeight: number; width: number; height: number; rotation: number; crop?: { originX: number; originY: number; width: number; height: number } };
export type Compression = 'high' | 'balanced' | 'small';
export type DocumentCategory = 'Petition' | 'Counter Affidavit' | 'Judgment' | 'Court Order' | 'Vakalath' | 'Evidence' | 'Notice' | 'Case Records' | 'Identity Documents' | 'Other';
export const DOCUMENT_CATEGORIES: DocumentCategory[] = ['Petition', 'Counter Affidavit', 'Judgment', 'Court Order', 'Vakalath', 'Evidence', 'Notice', 'Case Records', 'Identity Documents', 'Other'];
export type LocalDocument = { id: string; user_id: string; case_id: string | null; document_name: string; original_filename: string; file_type: 'application/pdf'; file_size: number; page_count: number; document_category: DocumentCategory; storage_status: 'local_only'; local_uri: string; created_at: string; updated_at: string };
export const scannerId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
