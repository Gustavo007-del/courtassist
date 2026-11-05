import { ApiError } from '../services/api';
import i18n from '../i18n';

export function friendlyError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) return i18n.t('networkError');
    if (error.status === 409) return i18n.t('auth.accountExists');
    if (error.status === 401) return i18n.t('auth.invalidCredentials');
    if (error.status === 413) return i18n.t('profile2.photoTooLarge');
    if (error.status === 415) return i18n.t('profile2.photoType');
  }
  return i18n.t('error');
}
