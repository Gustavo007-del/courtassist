import { useState } from 'react';
import { View } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Notice } from '../../components/common/Notice';
import { TextField } from '../../components/common/TextField';
import { Screen } from '../../components/layout/Screen';
import { documentApi } from '../../services/document-api';
import { friendlyError } from '../../utils/errors';

type Review = {
  field: string;
  source_value: string;
  status: 'accepted' | 'edited' | 'rejected';
  value: string;
};
export default function MetadataReview() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t } = useTranslation();
  const [reviews, setReviews] = useState<Record<string, Review>>({});
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const query = useQuery({
    queryKey: ['vault-suggestions', id],
    queryFn: () => documentApi.suggestions(id),
    retry: false,
  });
  const key = (field: string, value: string) => `${field}:${value}`;
  const setReview = (field: string, source_value: string, status: Review['status'], value: string) =>
    setReviews((current) => ({
      ...current,
      [key(field, source_value)]: { field, source_value, status, value },
    }));
  const confirm = async () => {
    setError(null);
    try {
      await documentApi.confirmSuggestions(id, Object.values(reviews));
      setSaved(true);
    } catch (caught) {
      setError(friendlyError(caught));
    }
  };
  return (
    <Screen title={t('vault.reviewMetadata')} subtitle={t('vault.suggestionsWarning')} back>
      {error && <Notice message={error} />}
      {query.isError && <Notice message={friendlyError(query.error)} />}
      {query.data?.suggestions.map((item, index) => {
        const entry = reviews[key(item.field, item.value)];
        return (
          <View key={`${item.field}-${index}`} style={{ gap: 6, marginVertical: 8 }}>
            <AppText>
              {item.field} ·{' '}
              {item.page_number === null
                ? t('research.unpaginated')
                : t('vault.page') + ' ' + item.page_number}
              : {item.value}
            </AppText>
            <TextField
              label={t('vault.reviewedValue')}
              value={entry?.value ?? item.value}
              onChangeText={(value) => setReview(item.field, item.value, 'edited', value)}
            />
            <Button
              label={t('vault.accept')}
              variant="secondary"
              onPress={() => setReview(item.field, item.value, 'accepted', item.value)}
            />
            <Button
              label={t('vault.reject')}
              variant="text"
              onPress={() => setReview(item.field, item.value, 'rejected', '')}
            />
            {entry && <AppText>{entry.status}</AppText>}
          </View>
        );
      })}
      {query.data?.suggestions.length === 0 && <AppText>{t('vault.noSuggestions')}</AppText>}
      <Button
        label={t('vault.confirmReview')}
        onPress={() => {
          void confirm();
        }}
      />
      {saved && <AppText>{t('vault.reviewSaved')}</AppText>}
    </Screen>
  );
}
