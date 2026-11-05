import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { SettingsRow, SettingsSection } from '../../components/settings/SettingsSection';

export default function Settings() {
  const { t } = useTranslation();
  return <Screen title={t('settings.title')}>
    <SettingsSection title={t('practice.title')}>
      <SettingsRow label={t('practice.clients')} onPress={() => router.push('/clients')} />
      <SettingsRow label={t('practice.courts')} onPress={() => router.push('/courts')} />
    </SettingsSection>
    <SettingsSection title={t('settings2.account')}>
      <SettingsRow label={t('settings2.viewProfile')} onPress={() => router.push('/(tabs)/profile')} />
      <SettingsRow label={t('settings2.editProfile')} onPress={() => router.push('/profile/edit')} />
      <SettingsRow label={t('settings2.accountInfo')} onPress={() => router.push('/settings/account-info')} />
    </SettingsSection>
    <SettingsSection title={t('settings2.appearance')}><SettingsRow label={t('settings2.theme')} onPress={() => router.push('/settings/theme')} /></SettingsSection>
    <SettingsSection title={t('settings.language')}><SettingsRow label={t('settings.languageDetail')} onPress={() => router.push('/settings/language')} /></SettingsSection>
    <SettingsSection title={t('settings2.regional')}><SettingsRow label={t('settings2.regionalDetail')} onPress={() => router.push('/settings/regional')} /></SettingsSection>
    <SettingsSection title={t('settings2.notifications')}><SettingsRow label={t('settings2.notificationsDetail')} onPress={() => router.push('/settings/notifications')} /></SettingsSection>
    <SettingsSection title={t('settings2.security')}>
      <SettingsRow label={t('security.changePassword')} onPress={() => router.push('/settings/change-password')} />
      <SettingsRow label={t('security.biometricLock')} onPress={() => router.push('/settings/security')} />
      <SettingsRow label={t('security.session')} onPress={() => router.push('/settings/security')} />
    </SettingsSection>
    <SettingsSection title={t('settings2.dataSync')}><SettingsRow label={t('settings2.syncFuture')} /></SettingsSection>
    <SettingsSection title={t('settings2.about')}><SettingsRow label={t('appName')} onPress={() => router.push('/settings/about')} /></SettingsSection>
  </Screen>;
}
