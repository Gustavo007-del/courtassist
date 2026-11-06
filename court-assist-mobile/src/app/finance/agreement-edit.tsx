import { useState } from 'react';
import { Alert } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { TextField } from '../../components/common/TextField';
import { Button } from '../../components/common/Button';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { Notice } from '../../components/common/Notice';
import { AppText } from '../../components/common/AppText';
import { financeApi, type FinancialRecord } from '../../services/finance-api';
import { apiRequest } from '../../services/api';
import { friendlyError } from '../../utils/errors';
export default function AgreementEdit() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t } = useTranslation();
  const q = useQuery({
    queryKey: ['agreement-edit', id],
    queryFn: () => financeApi.detail('fee-agreements', id),
  });
  return q.data ? (
    <Form initial={q.data} />
  ) : (
    <Screen title={t('work.agreement')} back>
      <AppText>{q.isError ? t('work.error') : t('work.saving')}</AppText>
    </Screen>
  );
}
function Form({ initial }: { initial: FinancialRecord }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [amount, setAmount] = useState(initial.amount ?? '');
  const [description, setDescription] = useState(initial.description ?? '');
  const [status, setStatus] = useState(initial.status ?? 'active');
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    try {
      await apiRequest(`/fee-agreements/${initial.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ amount, description, status, reason }),
      });
      void qc.invalidateQueries({ queryKey: ['finance'] });
      void qc.invalidateQueries({ queryKey: ['finance-detail'] });
      void qc.invalidateQueries({ queryKey: ['finance-report'] });
      router.back();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen title={t('work.agreement')} back>
      {error && <Notice message={error} />}
      <TextField label={t('work.amount')} value={amount} onChangeText={setAmount} />
      <TextField label={t('work.description')} value={description} onChangeText={setDescription} />
      <ChoiceChips
        value={status}
        onChange={setStatus}
        options={['draft', 'active', 'completed', 'cancelled'].map((value) => ({
          value,
          label: t(`work.${value}`, value),
        }))}
      />
      <TextField label={t('work.reason')} value={reason} onChangeText={setReason} />
      <Button
        label={t('work.save')}
        loading={busy}
        onPress={() =>
          Alert.alert(t('work.confirm'), t('work.confirmBody'), [
            { text: t('work.cancel'), style: 'cancel' },
            { text: t('work.confirm'), onPress: () => void save() },
          ])
        }
      />
    </Screen>
  );
}
