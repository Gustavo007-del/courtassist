import { useState } from 'react';
import { Alert, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { Notice } from '../../components/common/Notice';
import { Screen } from '../../components/layout/Screen';
import { cachedDocument, secureDownload } from '../../features/vault/download';
import { documentApi } from '../../services/document-api';
import { useAuthStore } from '../../store/auth-store';
import { pinDocument, pinnedFiles, previewPin } from '../../features/sync/files';
import { useSyncState } from '../../features/sync/state';
import { friendlyError } from '../../utils/errors';

export default function VaultDetails() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t } = useTranslation();
  const user = useAuthStore((state) => state.user);
  const cache = useQueryClient();
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<number>();
  const enabled = useSyncState(state => state.enabled);
  const connected = useSyncState(state => state.connected);
  const offlineFiles = useQuery({
    queryKey: ['sync-files', user?.id], queryFn: () => pinnedFiles(user!.id), enabled: enabled && !!user,
  });
  const [error, setError] = useState<string | null>(null);
  const query = useQuery({ queryKey: ['vault-document', id], queryFn: () => documentApi.get(id), enabled: !!id });
  const doc = query.data;
  const action = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try { await fn(); }
    catch (caught) { setError(friendlyError(caught)); }
    finally { setBusy(false); }
  };
  return <Screen record={doc} title={doc?.document_name ?? t('vault.title')} back>
    {query.isPending ? <LoadingSkeleton /> : query.isError || !doc ?
      <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : <>
        {error && <Notice message={error} />}
        <Button label={t('notifications.newReminder')} variant="secondary" onPress={()=>router.push({pathname:'/notifications/create',params:{entity_type:'document',entity_id:id}})}/>
        {!doc.is_archived && doc.current_version_id && <View style={{ gap: 8 }}>
          {(['summarize', 'dates', 'metadata'] as const).map(mode => <Button key={mode} label={t(`ai.kinds.${mode}`)} variant="secondary"
            onPress={() => router.push({ pathname: '/ai/request', params: { mode, documentId: id } })} />)}
        </View>}
        {enabled && user && doc.current_version_id && <View style={{ gap: 8 }}>
          <Button label={t('sync.pin')} variant="secondary" loading={busy} disabled={connected === false ||
            !!offlineFiles.data?.some(file => file.id === doc.id && file.version === doc.current_version_id)}
            onPress={() => void action(async () => {
              setProgress(0);
              try {
                await pinDocument(user.id, doc, setProgress, () => useAuthStore.getState().user?.id === user.id);
                await offlineFiles.refetch();
              } finally { setProgress(undefined); }
            })} />
          {progress !== undefined && <AppText>{t('sync.downloadProgress', { percent: Math.round(progress * 100) })}</AppText>}
          {offlineFiles.data?.some(file => file.id === doc.id && file.version === doc.current_version_id) && <AppText>{t('vault.offlineAvailable')}</AppText>}
        </View>}
        <Card>
          <AppText>{t('vault.category')}: {doc.document_category}</AppText>
          <AppText>{t('vault.status')}: {t(`vaultStatus.${doc.storage_status}`, doc.storage_status)}</AppText>
          <AppText>{t('vault.name')}: {doc.original_filename}</AppText>
          <AppText>{(doc.file_size / 1024 / 1024).toFixed(2)} MB</AppText>
          <AppText>{doc.description}</AppText>
          {user && doc.current_version_id && <AppText>{cachedDocument(user.id, doc).exists ? t('vault.offlineAvailable') : t('vault.cloudOnly')}</AppText>}
        </Card>
        <View style={{ gap: 8, marginTop: 16 }}>
          {!doc.current_version_id && !doc.is_archived && <Button label={t('vault.retryUpload')} onPress={() => router.push({ pathname: '/documents/upload', params: { documentId: id } })} />}
          {doc.current_version_id && <>
            <Button label={t('vault.preview')} loading={busy} onPress={() => { void action(async () => { if (enabled && user && await previewPin(user.id, doc.id, doc.current_version_id ?? undefined)) return;
              const file = await secureDownload(user!.id, doc); await file.preview({ title: doc.document_name, mimeType: doc.mime_type }); }); }} />
            <Button label={t('vault.downloadOffline')} variant="secondary" loading={busy} onPress={() => { void action(async () => { await secureDownload(user!.id, doc); }); }} />
            <Button label={t('vault.versions')} variant="secondary" onPress={() => router.push({ pathname: '/documents/versions', params: { id } })} />
            <Button label={t('vault.ocr')} variant="secondary" onPress={() => router.push({ pathname: '/documents/ocr', params: { id } })} />
            <Button label={t('vault.reviewMetadata')} variant="secondary" onPress={() => router.push({ pathname: '/documents/metadata-review', params: { id } })} />
          </>}
          {!doc.is_archived && <Button label={t('vault.archive')} variant="text" onPress={() => Alert.alert(t('vault.archive'), t('vault.archiveConfirm'), [{ text: t('cancel'), style: 'cancel' }, { text: t('vault.archive'), onPress: () => { void action(async () => { await documentApi.archive(id); await cache.invalidateQueries({ queryKey: ['vault'] }); router.replace('/documents'); }); } }])} />}
        </View>
      </>}
  </Screen>;
}
