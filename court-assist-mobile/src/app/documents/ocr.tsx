import { useState } from 'react';
import { useLocalSearchParams, router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import * as Clipboard from 'expo-clipboard';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Notice } from '../../components/common/Notice';
import { TextField } from '../../components/common/TextField';
import { Screen } from '../../components/layout/Screen';
import { documentApi } from '../../services/document-api';
import { friendlyError } from '../../utils/errors';

export default function DocumentOcr() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t } = useTranslation();
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const result = useQuery({
    queryKey: ['vault-ocr', id],
    queryFn: () => documentApi.ocr(id),
    retry: false,
    refetchInterval: (query) =>
      ['pending', 'processing'].includes(query.state.data?.processing_status ?? '') ? 3000 : false,
  });
  const action = async (retry: boolean) => {
    setBusy(true);
    setError(null);
    try {
      if (retry) await documentApi.retryOcr(id);
      else await documentApi.startOcr(id);
      await result.refetch();
    } catch (caught) {
      setError(friendlyError(caught));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Screen title={t('vault.ocr')} subtitle={t('vault.ocrWarning')} back>
      {error && <Notice message={error} />}
      <AppText>
        {t('vault.status')}: {result.data?.processing_status ?? t('vault.notStarted')}
      </AppText>
      {result.data?.error_message && <Notice message={result.data.error_message} />}
      <Button
        label={t('vault.startOcr')}
        loading={busy}
        onPress={() => {
          void action(false);
        }}
      />
      <Button
        label={t('vault.retryOcr')}
        variant="secondary"
        loading={busy}
        onPress={() => {
          void action(true);
        }}
      />
      {result.data?.extracted_text && (
        <>
          <TextField label={t('vault.searchWithin')} value={search} onChangeText={setSearch} />
          <Button
            label={t('vault.copyText')}
            variant="secondary"
            onPress={() => {
              void Clipboard.setStringAsync(result.data!.extracted_text);
            }}
          />
          <Button
            label={t('vault.reviewMetadata')}
            variant="secondary"
            onPress={() => router.push({ pathname: '/documents/metadata-review', params: { id } })}
          />
          {result.data.page_results
            .filter((page) => !search || page.extracted_text.toLowerCase().includes(search.toLowerCase()))
            .map((page, index) => (
              <AppText key={page.page_number ?? index}>
                {page.page_number === null
                  ? t('research.unpaginated')
                  : t('vault.page') + ' ' + page.page_number}
                {'\n'}
                {page.extracted_text}
              </AppText>
            ))}
        </>
      )}
    </Screen>
  );
}
