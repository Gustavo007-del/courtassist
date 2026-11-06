import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '../../store/auth-store';
import { pinnedFiles, previewPin, removePin } from '../../features/sync/files';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { Screen } from '../../components/layout/Screen';

export default function OfflineFiles() {
  const { t } = useTranslation();
  const owner = useAuthStore(state => state.user!.id);
  const [error, setError] = useState(false);
  const query = useQuery({ queryKey: ['sync-files', owner], queryFn: () => pinnedFiles(owner) });
  return <Screen title={t('sync.files')} subtitle={t('sync.filesExplanation')} back>
    {error && <AppText>{t('sync.operationError')}</AppText>}
    {query.isPending ? <LoadingSkeleton /> : query.isError ? <ErrorState message={t('work.error')} retry={() => void query.refetch()} /> : <>
      {!query.data.length && <AppText>{t('sync.noFiles')}</AppText>}
      {query.data.map(file => <Card key={file.id + file.version}>
        <AppText>{file.name}</AppText>
        <Button label={t('vault.preview')} onPress={() => void previewPin(owner, file.id, file.version).catch(() => setError(true))} />
        <Button label={t('sync.removeCopy')} variant="text" onPress={() =>
          void removePin(owner, file.id, file.version).then(() => query.refetch()).catch(() => setError(true))} />
      </Card>)}
    </>}
  </Screen>;
}

