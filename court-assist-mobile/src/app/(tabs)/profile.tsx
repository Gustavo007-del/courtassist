import { Image, View } from 'react-native';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Card } from '../../components/common/Card';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Avatar } from '../../components/common/Avatar';
import { SectionHeader } from '../../components/common/SectionHeader';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { ProfileInfoCard } from '../../components/profile/ProfileInfoCard';
import { profileApi } from '../../services/profile-api';
import { useAuthStore } from '../../store/auth-store';
import { useTheme } from '../../theme/tokens';
import { friendlyError } from '../../utils/errors';
import { formatStoredDate } from '../../utils/dates';

export default function Profile() {
  const { t } = useTranslation(); const theme = useTheme();
  const fallback = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.accessToken);
  const { data, isPending, isError, error, isRefetching, refetch } = useQuery({ queryKey: ['me', fallback?.id], queryFn: profileApi.me, enabled: !!fallback });
  const user = data ?? fallback;
  return <Screen title={t('profile.title')} refreshing={isRefetching} onRefresh={() => { void refetch(); }}>
    {isPending && !user ? <LoadingSkeleton /> : isError && !user ? <ErrorState message={friendlyError(error)} retry={() => { void refetch(); }} /> : user && <>
      {isError && <ErrorState message={friendlyError(error)} retry={() => { void refetch(); }} />}
      <Card style={{ alignItems: 'center', gap: 8 }}><Avatar imageKey={user.profile_image} size={88} /><AppText style={{ fontSize: 23, fontWeight: '800', textAlign: 'center' }}>{user.full_name}</AppText><AppText style={{ color: theme.colors.muted, textAlign: 'center' }}>{user.professional_designation || t('profile2.none')}</AppText>{user.enrollment_number && <AppText style={{ color: theme.colors.accent, fontSize: 14 }}>{user.enrollment_number}</AppText>}</Card>
      <View style={{ marginTop: 18, gap: 10 }}><Button label={t('profile2.edit')} onPress={() => router.push('/profile/edit')} /><Button label={t('profile.settings')} variant="secondary" onPress={() => router.push('/settings')} /></View>
      <SectionHeader title={t('profile2.personal')} /><ProfileInfoCard rows={[
        { label: t('auth.email'), value: user.email }, { label: t('profile2.phoneNumber'), value: user.phone_number },
        { label: t('profile2.dateOfBirth'), value: user.date_of_birth ? formatStoredDate(user.date_of_birth, user.preferences?.date_format) : null }, { label: t('profile2.gender'), value: user.gender ? t(`profile2.gender${user.gender === 'female' ? 'Female' : user.gender === 'male' ? 'Male' : user.gender === 'non_binary' ? 'NonBinary' : 'PreferNot'}`) : null },
        { label: t('profile2.address'), value: user.address }, { label: t('profile2.city'), value: user.city },
        { label: t('profile2.district'), value: user.district }, { label: t('profile2.state'), value: user.state }, { label: t('profile2.pinCode'), value: user.pin_code },
      ]} />
      <SectionHeader title={t('profile2.professional')} /><ProfileInfoCard rows={[
        { label: t('profile.enrollment'), value: user.enrollment_number }, { label: t('profile.barCouncil'), value: user.bar_council },
        { label: t('profile2.enrollmentDate'), value: user.enrollment_date ? formatStoredDate(user.enrollment_date, user.preferences?.date_format) : null }, { label: t('profile2.designation'), value: user.professional_designation },
        { label: t('profile2.experience'), value: user.years_of_experience?.toString() }, { label: t('profile2.officeName'), value: user.office_name },
        { label: t('profile2.officeAddress'), value: user.office_address }, { label: t('profile2.officePhone'), value: user.office_phone },
        { label: t('profile2.professionalEmail'), value: user.professional_email }, { label: t('profile2.areas'), value: user.areas_of_practice.join(', ') },
      ]} />
      {user.signature_image && token && <><SectionHeader title={t('profile2.signature')} /><Card><Image source={{ uri: profileApi.imageUrl('signature', user.signature_image), headers: { Authorization: `Bearer ${token}` } }} style={{ width: '100%', height: 100, resizeMode: 'contain' }} /></Card></>}
      <SectionHeader title={t('profile2.preferences')} /><ProfileInfoCard rows={[
        { label: t('profile2.timezone'), value: user.preferences?.timezone },
        { label: t('profile2.dateFormat'), value: user.preferences?.date_format },
        { label: t('profile2.timeFormat'), value: user.preferences?.time_format },
      ]} />
    </>}
  </Screen>;
}
