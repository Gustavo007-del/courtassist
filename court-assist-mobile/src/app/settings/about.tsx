import Constants from 'expo-constants';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { SettingsRow, SettingsSection } from '../../components/settings/SettingsSection';

export default function About() {
  const { t } = useTranslation();
  return <Screen title={t('settings2.about')}><SettingsSection title={t('appName')}>
    <SettingsRow label={t('settings2.version')} detail={Constants.expoConfig?.version ?? '0.1.0'} />
    <SettingsRow label={t('settings2.privacyFuture')} />
    <SettingsRow label={t('settings2.termsFuture')} />
    <SettingsRow label={t('settings2.helpFuture')} />
  </SettingsSection></Screen>;
}
