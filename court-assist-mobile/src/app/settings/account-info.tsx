import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { ProfileInfoCard } from '../../components/profile/ProfileInfoCard';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { ErrorState } from '../../components/common/ErrorState';
import { profileApi } from '../../services/profile-api';
import { useAuthStore } from '../../store/auth-store';
import { friendlyError } from '../../utils/errors';
import { formatStoredDate } from '../../utils/dates';

export default function AccountInfo() {
  const { t } = useTranslation(); const fallback = useAuthStore((state) => state.user);
  const { data, isPending, isError, error, refetch } = useQuery({ queryKey: ['me', fallback?.id], queryFn: profileApi.me, enabled: !!fallback });
  const user = data ?? fallback;
  return <Screen title={t('settings2.accountInfo')}>{isPending && !user ? <LoadingSkeleton /> : isError && !user ? <ErrorState message={friendlyError(error)} retry={() => { void refetch(); }} /> : user && <ProfileInfoCard rows={[
    { label: t('auth.email'), value: user.email }, { label: t('profile2.phoneNumber'), value: user.phone_number },
    { label: t('settings2.emailVerified'), value: t(user.is_email_verified ? 'settings2.yes' : 'settings2.no') },
    { label: t('settings2.phoneVerified'), value: t(user.is_phone_verified ? 'settings2.yes' : 'settings2.no') },
    { label: t('settings2.created'), value: formatStoredDate(user.created_at, user.preferences?.date_format) },
  ]} />}</Screen>;
}
