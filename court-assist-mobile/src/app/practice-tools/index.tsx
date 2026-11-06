import { useTranslation } from 'react-i18next';
import { router } from 'expo-router';
import { Button } from '../../components/common/Button';
import { Screen } from '../../components/layout/Screen';
export default function PracticeTools() {
  const { t } = useTranslation();
  return (
    <Screen title={t('dashboard.actions.practiceTools')} back>
      <Button label={t('work.drafting')} onPress={() => router.push('/practice-tools/drafting')} />
      <Button label={t('work.finance')} onPress={() => router.push('/practice-tools/finance')} />
      <Button label={t('ai.title')} variant="secondary" onPress={() => router.push('/ai')} />
      <Button label={t('research.library')} onPress={() => router.push('/practice-tools/research')} />
    </Screen>
  );
}
