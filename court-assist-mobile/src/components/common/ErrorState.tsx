import { View } from 'react-native';
import { useTranslation } from 'react-i18next';
import { Notice } from './Notice';
import { Button } from './Button';

export function ErrorState({ message, retry }: { message: string; retry: () => void }) {
  const { t } = useTranslation();
  return <View><Notice message={message} /><Button label={t('dashboard.retry')} onPress={retry} variant="secondary" /></View>;
}
