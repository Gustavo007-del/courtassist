import { useState } from 'react';
import { Linking } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { File, Paths } from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import { Screen } from '../../components/layout/Screen';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { TextField } from '../../components/common/TextField';
import { Notice } from '../../components/common/Notice';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { clientApi } from '../../services/client-api';
import { caseApi } from '../../services/case-api';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { financeApi } from '../../services/finance-api';
import { apiRequest } from '../../services/api';
import { friendlyError } from '../../utils/errors';
export default function Reports() {
  const { t } = useTranslation();
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [clientId, setClientId] = useState('');
  const [caseId, setCaseId] = useState('');
  const [method, setMethod] = useState('');
  const [category, setCategory] = useState('');
  const clients = useQuery({ queryKey: ['report-clients'], queryFn: () => clientApi.list({ limit: 100 }) });
  const cases = useQuery({ queryKey: ['report-cases'], queryFn: () => caseApi.list({ limit: 100 }) });
  const [params, setParams] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const q = useQuery({ queryKey: ['finance-report', params], queryFn: () => financeApi.report(params) });
  async function download(format: string) {
    try {
      if (format === 'pdf') {
        const signed = await apiRequest<{ url: string }>(
          `/finance/report-pdf?${new URLSearchParams(Object.entries(params).filter(([, value]) => !!value)).toString()}`,
          { method: 'POST' },
        );
        await Linking.openURL(signed.url);
      } else if (q.data) {
        const text = await apiRequest<string>(
          `/finance/export?${new URLSearchParams(Object.entries(params).filter(([, value]) => !!value)).toString()}`,
        );
        const file = new File(Paths.cache, `financial-report-${Date.now()}.csv`);
        file.write(text);
        if (await Sharing.isAvailableAsync()) await Sharing.shareAsync(file.uri, { mimeType: 'text/csv' });
      }
    } catch (e) {
      setError(friendlyError(e));
    }
  }
  return (
    <Screen title={t('work.reports')} back>
      {error && <Notice message={error} />}
      <TextField label={t('work.from')} value={from} onChangeText={setFrom} />
      <TextField label={t('work.to')} value={to} onChangeText={setTo} />
      <AppText>{t('work.client')}</AppText>
      <ChoiceChips
        value={clientId}
        onChange={setClientId}
        options={[
          { value: '', label: t('work.none') },
          ...(clients.data?.items ?? []).map((row) => ({ value: row.id, label: row.full_name })),
        ]}
      />
      <AppText>{t('work.case')}</AppText>
      <ChoiceChips
        value={caseId}
        onChange={setCaseId}
        options={[
          { value: '', label: t('work.none') },
          ...(cases.data?.items ?? []).map((row) => ({ value: row.id, label: row.case_number })),
        ]}
      />
      <TextField label={t('work.method')} value={method} onChangeText={setMethod} />
      <TextField label={t('work.category')} value={category} onChangeText={setCategory} />
      <Button
        label={t('work.apply')}
        onPress={() =>
          setParams({ from_date: from, to_date: to, client_id: clientId, case_id: caseId, method, category })
        }
      />
      {q.isPending ? (
        <LoadingSkeleton />
      ) : q.isError ? (
        <ErrorState message={t('work.error')} retry={() => void q.refetch()} />
      ) : (
        <>
          {Object.entries(q.data.summary).map(([key, value]) => (
            <AppText key={key}>
              {t(`work.${key}`)}: ₹{value}
            </AppText>
          ))}
          <AppText>{t('work.monthly')}</AppText>
          {q.data.monthly.map((row) => (
            <AppText key={row.month}>
              {row.month}: ₹{row.income} − ₹{row.expenses} = ₹{row.net_cash_flow}
            </AppText>
          ))}
          {(['by_method', 'by_category'] as const).map((key) => (
            <AppText key={key}>
              {t(`work.${key}`)}:{' '}
              {Object.entries(q.data[key])
                .map(([name, value]) => `${name}: ₹${value}`)
                .join('; ')}
            </AppText>
          ))}
          {(['by_client', 'by_case', 'annual'] as const).map((key) => (
            <AppText key={key}>
              {t(`work.${key}`)}:{' '}
              {Object.entries(q.data[key])
                .map(
                  ([name, values]) =>
                    `${name}: ${Object.entries(values)
                      .map(([metric, value]) => t(`work.${metric}`, metric) + ' ₹' + value)
                      .join(', ')}`,
                )
                .join('; ')}
            </AppText>
          ))}
          <Button label={t('work.exportCsv')} onPress={() => void download('csv')} />
          <Button label={t('work.exportPdf')} onPress={() => void download('pdf')} />
        </>
      )}
    </Screen>
  );
}
