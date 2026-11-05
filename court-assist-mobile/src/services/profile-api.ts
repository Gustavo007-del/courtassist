import { File, UploadType } from 'expo-file-system';
import { apiRequest, ApiError, baseUrl } from './api';
import type { Advocate } from '../features/auth/types';
import { useAuthStore } from '../store/auth-store';

export type ProfileUpdate = Partial<Pick<Advocate,
  'full_name' | 'email' | 'phone_number' | 'date_of_birth' | 'gender' | 'address' |
  'city' | 'district' | 'state' | 'pin_code' | 'enrollment_number' | 'bar_council' |
  'enrollment_date' | 'professional_designation' | 'years_of_experience' | 'office_name' |
  'office_address' | 'office_phone' | 'professional_email' | 'areas_of_practice'>>;

type ImagePurpose = 'profile' | 'signature';
type UploadUrl = { upload_id: string; upload_url: string; expires_at: string; method: 'PUT' };

export const profileApi = {
  me: () => apiRequest<Advocate>('/users/me'),
  update: (data: ProfileUpdate) => apiRequest<Advocate>('/users/me', { method: 'PATCH', body: JSON.stringify(data) }),
  imageUrl: (purpose: ImagePurpose, key: string) => `${baseUrl}/api/v1/users/me/${purpose}-image?v=${encodeURIComponent(key)}`,
  uploadImage: async (purpose: ImagePurpose, uri: string, contentType: 'image/jpeg' | 'image/png' | 'image/webp') => {
    const ticket = await apiRequest<UploadUrl>(`/users/me/${purpose}-image/upload-url`, { method: 'POST', body: JSON.stringify({ content_type: contentType }) });
    if (!baseUrl || !ticket.upload_url.startsWith(`/api/v1/users/me/${purpose}-image/uploads/`)) throw new ApiError(0, 'Invalid upload destination');
    const token = useAuthStore.getState().accessToken;
    if (!token) throw new ApiError(401, 'Authentication required');
    const file = new File(uri);
    if (file.size > 5 * 1024 * 1024) throw new ApiError(413, 'Image exceeds 5 MB');
    const result = await file.upload(`${baseUrl}${ticket.upload_url}`, { httpMethod: 'PUT', uploadType: UploadType.BINARY_CONTENT, mimeType: contentType, headers: { Authorization: `Bearer ${token}`, 'Content-Type': contentType } });
    if (result.status !== 204) throw new ApiError(result.status, 'Image upload failed');
    return apiRequest<Advocate>(`/users/me/${purpose}-image/confirm`, { method: 'POST', body: JSON.stringify({ upload_id: ticket.upload_id }) });
  },
};
