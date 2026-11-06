import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { financeApi, type FinanceKind } from '../../services/finance-api';
export default function Finance() {
  const { t } = useTranslation();
  const { clientId, caseId } = useLocalSearchParams<{ clientId?: string; caseId?: string }>();
  const [range, setRange] = useState({ from_date: '', to_date: '' });
  const query = useQuery({
    queryKey: ['finance-report', range, clientId, caseId],
    queryFn: () => financeApi.report({ ...range, client_id: clientId ?? '', case_id: caseId ?? '' }),
  });
  const options: [FinanceKind, string][] = [
    ['fee-agreements', 'agreements'],
    ['payments', 'payments'],
    ['expenses', 'expenses'],
    ['invoices', 'invoices'],
  ];
  function start(period: string) {
    const now = new Date();
    const begin = new Date(now);
    const end = new Date(now);
    if (period === 'year') {
      begin.setMonth(0, 1);
      end.setMonth(11, 31);
    } else if (period === 'month') {
      begin.setDate(1);
      end.setMonth(end.getMonth() + 1, 0);
    } else if (period === 'week') {
      begin.setDate(begin.getDate() - ((begin.getDay() + 6) % 7));
      end.setDate(begin.getDate() + 6);
    }
    const format = (d: Date) =>
      `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    setRange(
      period === 'all' ? { from_date: '', to_date: '' } : { from_date: format(begin), to_date: format(end) },
    );
  }

  return (
    <Screen
      title={t('work.finance')}
      back
      onRefresh={() => void query.refetch()}
      refreshing={query.isRefetching}
    >
      {['allTime', 'today', 'week', 'month', 'year'].map((period) => (
        <Button
          key={period}
          variant="secondary"
          label={t(`work.${period}`)}
          onPress={() => start(period === 'allTime' ? 'all' : period)}
        />
      ))}
      {query.isPending ? (
        <LoadingSkeleton />
      ) : query.isError ? (
        <ErrorState message={t('work.error')} retry={() => void query.refetch()} />
      ) : (
        Object.entries(query.data.summary).map(([key, value]) => (
          <AppText key={key} style={{ marginVertical: 8, fontSize: 17 }}>
            {t(`work.${key}`)}: ₹{value}
          </AppText>
        ))
      )}
      {options.map(([kind, label]) => (
        <Button
          key={kind}
          label={t(`work.${label}`)}
          onPress={() =>
            router.push({
              pathname: '/finance/records',
              params: { kind, clientId: clientId ?? '', caseId: caseId ?? '' },
            })
          }
        />
      ))}
      <Button label={t('work.reports')} onPress={() => router.push('/finance/reports')} />
    </Screen>
  );
}
