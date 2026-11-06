import { useState } from 'react';
import { Alert, Linking } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { TextField } from '../../components/common/TextField';
import { Notice } from '../../components/common/Notice';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { financeApi, type FinanceKind } from '../../services/finance-api';
import { apiRequest } from '../../services/api';
import { friendlyError } from '../../utils/errors';
export default function FinancialDetail() {
  const { kind, id } = useLocalSearchParams<{ kind: FinanceKind; id: string }>();
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [reason, setReason] = useState('');
  const [amount, setAmount] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const q = useQuery({ queryKey: ['finance-detail', kind, id], queryFn: () => financeApi.detail(kind, id) });
  const history = useQuery({
    queryKey: ['financial-history', kind, id],
    queryFn: () =>
      apiRequest<{ id: string; reason: string; amount: string; created_at: string }[]>(
        `/${kind}/${id}/history`,
      ),
    enabled: kind === 'payments' || kind === 'expenses',
  });
  async function action(name: string, body?: unknown) {
    setBusy(true);
    try {
      await financeApi.action(kind, id, name, body);
      void q.refetch();
      void history.refetch();
      void qc.invalidateQueries({ queryKey: ['finance'] });
      void qc.invalidateQueries({ queryKey: ['finance-report'] });
      setError('');
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  function confirm(name: string, body?: unknown) {
    Alert.alert(t('work.confirm'), t('work.confirmBody'), [
      { text: t('work.cancel'), style: 'cancel' },
      { text: t('work.confirm'), onPress: () => void action(name, body) },
    ]);
  }
  async function pdf() {
    setBusy(true);
    try {
      const signed = await financeApi.pdf(kind, id);
      await Linking.openURL(signed.url);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen title={q.data?.number ?? t(`work.${kind === 'fee-agreements' ? 'agreement' : kind}`)} back>
      {error && <Notice message={error} />}{' '}
      {(kind==='fee-agreements'||kind==='invoices')&&<Button label={t('notifications.newReminder')} variant="secondary" onPress={()=>router.push({pathname:'/notifications/create',params:{entity_type:kind==='invoices'?'invoice':'agreement',entity_id:id}})}/>}
      {q.isPending ? (
        <LoadingSkeleton />
      ) : q.isError ? (
        <ErrorState message={t('work.error')} retry={() => void q.refetch()} />
      ) : (
        <>
          <AppText style={{ fontSize: 24, marginBottom: 16 }}>₹{q.data.amount ?? q.data.total}</AppText>
          <AppText>
            {t('work.status')}: {t(`work.${q.data.status}`, q.data.status ?? '')}
          </AppText>
          <AppText>{q.data.description ?? q.data.reference ?? ''}</AppText>
          {q.data.snapshot && (
            <>
              <AppText>{q.data.snapshot.advocate}</AppText>
              <AppText>{q.data.snapshot.client}</AppText>
              {q.data.snapshot.rows?.map((row, i) => (
                <AppText key={i}>{row.join(' · ')}</AppText>
              ))}
            </>
          )}
          {q.data.lines?.map((line, i) => (
            <AppText key={i}>
              {line.description} · {line.quantity} × ₹{line.unit_price}
            </AppText>
          ))}
          {kind === 'invoices' && q.data.status === 'draft' && (
            <Button label={t('work.issue')} loading={busy} onPress={() => confirm('issue')} />
          )}{' '}
          {kind === 'invoices' && q.data.status !== 'draft' && (
            <Button label={t('work.pdf')} loading={busy} onPress={() => void pdf()} />
          )}{' '}
          {kind === 'invoices' && q.data.status !== 'cancelled' && (
            <Button
              label={t('work.cancelInvoice')}
              variant="secondary"
              loading={busy}
              onPress={() => confirm('cancel')}
            />
          )}{' '}
          {kind === 'payments' && q.data.status === 'received' && (
            <>
              <Button label={t('work.pdf')} loading={busy} onPress={() => void pdf()} />
              <TextField label={t('work.reason')} value={reason} onChangeText={setReason} />
              <Button
                label={t('work.reverse')}
                variant="secondary"
                loading={busy}
                onPress={() =>
                  reason.trim().length >= 3 ? confirm('reverse', { reason }) : setError(t('work.invalid'))
                }
              />
            </>
          )}{' '}
          {((kind === 'payments' && q.data.status === 'pending') ||
            (kind === 'expenses' && q.data.status === 'draft')) && (
            <>
              <TextField label={t('work.reason')} value={reason} onChangeText={setReason} />
              <Button
                label={t('work.confirm')}
                loading={busy}
                onPress={() =>
                  reason.trim().length >= 3 ? confirm('confirm', { reason }) : setError(t('work.invalid'))
                }
              />
            </>
          )}{' '}
          {kind === 'payments' && q.data.status === 'reversed' && (
            <Button label={t('work.pdf')} loading={busy} onPress={() => void pdf()} />
          )}{' '}
          {kind === 'expenses' && q.data.status === 'confirmed' && (
            <>
              <TextField label={t('work.reason')} value={reason} onChangeText={setReason} />
              <TextField label={t('work.adjustAmount')} value={amount} onChangeText={setAmount} />
              <Button
                label={t('work.adjust')}
                loading={busy}
                onPress={() =>
                  reason.trim().length >= 3 && /^-?\d+(\.\d{1,2})?$/.test(amount)
                    ? confirm('adjust', { reason, amount })
                    : setError(t('work.invalid'))
                }
              />
            </>
          )}
          {kind === 'fee-agreements' && (
            <Button
              label={t('work.edit')}
              onPress={() => router.push({ pathname: '/finance/agreement-edit', params: { id } })}
            />
          )}
          {kind === 'expenses' && (
            <Button label={t('work.archive')} variant="secondary" onPress={() => confirm('archive')} />
          )}
          <AppText>{t('work.history')}</AppText>
          {history.data?.map((row) => (
            <AppText key={row.id}>
              {row.created_at.slice(0, 10)} · ₹{row.amount} · {row.reason}
            </AppText>
          ))}
        </>
      )}
    </Screen>
  );
}
