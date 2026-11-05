import { apiRequest } from './api';
import type { Preferences } from '../features/auth/types';

export const preferencesApi = {
  get: () => apiRequest<Preferences>('/users/me/preferences'),
  update: (changes: Partial<Preferences>) => apiRequest<Preferences>('/users/me/preferences', { method: 'PATCH', body: JSON.stringify(changes) }),
};
