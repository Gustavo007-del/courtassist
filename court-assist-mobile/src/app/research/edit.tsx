import { useLocalSearchParams } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { ErrorState } from '../../components/common/ErrorState';
import { ResearchItemForm } from '../../components/research/ResearchItemForm';
import { researchApi } from '../../services/research-api';
export default function Edit() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ['research', id], queryFn: () => researchApi.get(id) });
  return q.data ? (
    <ResearchItemForm key={id} initial={q.data} />
  ) : (
    <Screen title={t('research.edit')} back>
      {q.isError ? (
        <ErrorState message={t('work.error')} retry={() => void q.refetch()} />
      ) : (
        <LoadingSkeleton />
      )}
    </Screen>
  );
}
