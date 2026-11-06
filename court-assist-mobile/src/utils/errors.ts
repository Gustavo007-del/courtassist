import { ApiError } from '../services/api';
import i18n from '../i18n';

export function friendlyError(error: unknown): string {
  if (error instanceof Error && /^offline_[a-z_]+$/.test(error.message)) {
    return i18n.t(`sync.errors.${error.message}`, { defaultValue: i18n.t('sync.operationError') });
  }
  if (error instanceof ApiError) {
    if (error.status === 0) return i18n.t('networkError');
    if (error.status === 409) return /account|email/i.test(error.message) ? i18n.t('auth.accountExists') : error.message;
    if (error.status === 410 || error.status === 422 || error.status === 503) return error.message;
    if (error.status === 401) return i18n.t('auth.invalidCredentials');
    if (error.status === 413) return i18n.t('profile2.photoTooLarge');
    if (error.status === 415) return i18n.t('profile2.photoType');
  }
  return i18n.t('error');
}
