import { useState } from 'react';
import { Alert } from 'react-native';
import { router } from 'expo-router';
import { useQueryClient } from '@tanstack/react-query';
import * as DocumentPicker from 'expo-document-picker';
import { File } from 'expo-file-system';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { TextField } from '../../components/common/TextField';
import { Button } from '../../components/common/Button';
import { AppText } from '../../components/common/AppText';
import { Notice } from '../../components/common/Notice';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { researchApi, type ImportBatch } from '../../services/research-api';
import { apiRequest } from '../../services/api';
import { friendlyError } from '../../utils/errors';
export default function Import() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [csv, setCsv] = useState('');
  const [batch, setBatch] = useState<ImportBatch>();
  const [allowDuplicates, setAllowDuplicates] = useState(false);
  const [page, setPage] = useState(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function choose() {
    try {
      const selected = await DocumentPicker.getDocumentAsync({
        type: ['text/csv', 'text/plain', 'text/comma-separated-values'],
        copyToCacheDirectory: true,
      });
      if (selected.canceled) return;
      const file = new File(selected.assets[0].uri);
      if (file.size > 1000000) throw Error(t('research.csvLimit'));
      setCsv(await file.text());
      setBatch(undefined);
    } catch (e) {
      setError(friendlyError(e));
    }
  }
  async function preview() {
    setBusy(true);
    try {
      setBatch(await researchApi.import({ csv_text: csv }));
      setPage(0);
      setError('');
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  async function confirm() {
    if (!batch) return;
    setBusy(true);
    try {
      await researchApi.import({
        batch_id: batch.batch_id,
        confirm: true,
        allow_duplicates: allowDuplicates,
      });
      void qc.invalidateQueries({ queryKey: ['research'] });
      void qc.invalidateQueries({ queryKey: ['research-tags'] });
      router.replace('/research');
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen title={t('research.import')} subtitle={t('research.csvNotice')} back>
      {error && <Notice message={error} />}
      <Button label={t('research.chooseCsv')} variant="secondary" onPress={() => void choose()} />
      <Button
        label={t('research.sampleCsv')}
        variant="secondary"
        onPress={() => {
          void apiRequest<string>('/research-items/import/sample')
            .then((text) => {
              setCsv(text);
              setBatch(undefined);
            })
            .catch((e) => setError(friendlyError(e)));
        }}
      />
      <TextField
        label="CSV"
        value={csv}
        onChangeText={(value) => {
          setCsv(value);
          setBatch(undefined);
        }}
        multiline
      />
      <Button
        label={t('research.previewImport')}
        disabled={!csv}
        loading={busy}
        onPress={() => void preview()}
      />
      {batch && (
        <>
          <AppText>
            {batch.rows.length} {t('research.validRows')} · {batch.errors.length} {t('research.invalidRows')}
          </AppText>
          {batch.errors.map((row, index) => (
            <Notice key={index} message={`${row.row}: ${row.message}`} />
          ))}
          {batch.rows.slice(page * 30, (page + 1) * 30).map((row) => (
            <AppText key={row.row}>
              {row.row}. {row.data.title} · {row.data.citation} · {row.data.court}{' '}
              {row.duplicate ? '⚠ ' + t('research.duplicate') : ''}
            </AppText>
          ))}
          {page > 0 && <Button label="←" variant="secondary" onPress={() => setPage(page - 1)} />}{' '}
          {(page + 1) * 30 < batch.rows.length && (
            <Button label="→" variant="secondary" onPress={() => setPage(page + 1)} />
          )}
          <AppText>{t('research.allowDuplicates')}</AppText>
          <ChoiceChips
            value={String(allowDuplicates)}
            onChange={(value) => setAllowDuplicates(value === 'true')}
            options={[
              { value: 'false', label: t('research.noDuplicates') },
              { value: 'true', label: t('research.allowDuplicates') },
            ]}
          />
          <Button
            label={t('research.confirmImport')}
            disabled={!!batch.errors.length || !batch.rows.length}
            loading={busy}
            onPress={() =>
              Alert.alert(t('work.confirm'), t('research.confirmImportNotice'), [
                { text: t('work.cancel'), style: 'cancel' },
                { text: t('work.confirm'), onPress: () => void confirm() },
              ])
            }
          />
        </>
      )}
    </Screen>
  );
}
