import { useState } from 'react';
import { Alert } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { TextField } from '../../components/common/TextField';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { Notice } from '../../components/common/Notice';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { researchApi, type Extraction } from '../../services/research-api';
import { friendlyError } from '../../utils/errors';
export default function Metadata() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t } = useTranslation();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const q = useQuery({
    queryKey: ['research-extraction', id],
    queryFn: () => researchApi.extraction(id),
    refetchInterval: (query) =>
      ['pending', 'processing'].includes(query.state.data?.processing_status ?? '') ? 2500 : false,
  });
  async function start() {
    setBusy(true);
    try {
      await researchApi.extract(id);
      setError('');
      void q.refetch();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen title={t('research.metadata')} subtitle={t('research.extractionNotice')} back>
      {error && <Notice message={error} />}
      <Button label={t('research.extract')} loading={busy} onPress={() => void start()} />
      <Button
        label={t('research.upload')}
        variant="secondary"
        onPress={() => router.push({ pathname: '/research/upload', params: { id } })}
      />
      {q.isPending ? (
        <LoadingSkeleton />
      ) : q.isError ? (
        <ErrorState message={t('work.error')} retry={() => void q.refetch()} />
      ) : (
        <>
          <AppText>{t(`research.processing.${q.data.processing_status}`, q.data.processing_status)}</AppText>
          {q.data.error_message && <Notice message={q.data.error_message} />}
          <AppText>
            {t('research.unavailable')}:{' '}
            {q.data.unavailable_fields.map((field) => t(`research.fields.${field}`, field)).join(', ')}
          </AppText>
          {q.data.metadata_id && ['completed', 'needs_review'].includes(q.data.processing_status) && (
            <Review key={q.data.metadata_id} id={id} result={q.data} />
          )}
        </>
      )}
    </Screen>
  );
}
function Review({ id, result }: { id: string; result: Extraction }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [choices, setChoices] = useState(
    result.suggestions.map((suggestion) => ({ ...suggestion, status: '' })),
  );
  const [page, setPage] = useState(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function apply() {
    const selected = choices
      .filter((choice) => !!choice.status)
      .map((choice) => ({
        field: choice.field,
        source_value: result.suggestions[choices.indexOf(choice)].value,
        value: choice.value,
        status: choice.status,
      }));
    if (!selected.length || selected.length > 100) {
      setError(t('research.selectSuggestions'));
      return;
    }
    setBusy(true);
    try {
      await researchApi.confirmMetadata(id, { metadata_id: result.metadata_id, choices: selected });
      void qc.invalidateQueries({ queryKey: ['research'] });
      router.replace({ pathname: '/research/[id]', params: { id } });
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      {error && <Notice message={error} />}{' '}
      {choices.slice(page * 20, (page + 1) * 20).map((choice, local) => {
        const index = page * 20 + local;
        return (
          <ReviewChoice
            key={index}
            value={choice.value}
            field={choice.field}
            source={choice.source_text}
            page={choice.page_number}
            original={result.suggestions[index].value}
            status={choice.status}
            onChange={(value, status) =>
              setChoices((current) =>
                current.map((row, i) =>
                  i === index
                    ? { ...row, value, status }
                    : ['accepted', 'edited'].includes(status) &&
                        row.field === choice.field &&
                        ['accepted', 'edited'].includes(row.status)
                      ? { ...row, status: '' }
                      : row,
                ),
              )
            }
          />
        );
      })}
      {page > 0 && <Button label="←" variant="secondary" onPress={() => setPage(page - 1)} />}{' '}
      {(page + 1) * 20 < choices.length && (
        <Button label="→" variant="secondary" onPress={() => setPage(page + 1)} />
      )}
      <Button
        label={t('research.applyMetadata')}
        disabled={!choices.some((choice) => !!choice.status)}
        loading={busy}
        onPress={() =>
          Alert.alert(t('work.confirm'), t('research.confirmMetadataNotice'), [
            { text: t('work.cancel'), style: 'cancel' },
            { text: t('work.confirm'), onPress: () => void apply() },
          ])
        }
      />
    </>
  );
}
function ReviewChoice({
  field,
  value,
  source,
  page,
  original,
  status,
  onChange,
}: {
  field: string;
  value: string;
  source: string;
  page: number | null;
  original: string;
  status: string;
  onChange: (value: string, status: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <>
      <AppText>
        {page === null ? t('research.unpaginated') : t('research.page') + ' ' + page} · {source}
      </AppText>
      <TextField
        label={t(`research.fields.${field}`, field)}
        value={value}
        onChangeText={(text) => onChange(text, 'edited')}
      />
      <ChoiceChips
        value={status}
        onChange={(next) => onChange(next === 'accepted' ? original : value, next)}
        options={['accepted', 'edited', 'rejected'].map((option) => ({
          value: option,
          label: t(`research.${option}`),
        }))}
      />
    </>
  );
}
