import { useState } from 'react';
import { Alert, Platform, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { Directory, File } from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import * as Print from 'expo-print';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { Notice } from '../../components/common/Notice';
import { Screen } from '../../components/layout/Screen';
import { deleteDocument, getDocument } from '../../features/scanner/storage';
import { useAuthStore } from '../../store/auth-store';
import { friendlyError } from '../../utils/errors';

export default function DocumentDetails() {
  const { id } = useLocalSearchParams<{ id: string }>(); const { t } = useTranslation(); const user = useAuthStore((state) => state.user); const cache = useQueryClient(); const [error, setError] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  const query = useQuery({ queryKey: ['local-document', user?.id, id], queryFn: () => getDocument(user!.id, id), enabled: !!user?.id && !!id }); const item = query.data;
  const action = async (fn: () => Promise<unknown>) => { setBusy(true); setError(null); try { await fn(); } catch (caught) { setError(friendlyError(caught)); } finally { setBusy(false); } };
  return <Screen title={item?.document_name ?? t('scanner.documentDetails')} subtitle={t('scanner.localOnly')} back>{query.isPending ? <LoadingSkeleton /> : query.isError || !item ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : <>{error && <Notice message={error} />}<Card><AppText>{t('scanner.category')}: {t(`scanner.categories.${item.document_category}`)}</AppText><AppText>{t('scanner.pages')}: {item.page_count}</AppText><AppText>{t('scanner.fileSize')}: {(item.file_size / 1024 / 1024).toFixed(2)} MB</AppText><AppText>{t('scanner.storageStatus')}: {t('scanner.localOnly')}</AppText><AppText>{t('scanner.created')}: {new Date(item.created_at).toLocaleString()}</AppText></Card><View style={{ gap: 8, marginTop: 16 }}><Button label={t('vault.upload')} onPress={() => router.push({ pathname: '/documents/upload', params: { localId: id, caseId: item.case_id ?? '' } })} /><Button label={t('scanner.openPdf')} loading={busy} onPress={() => { void action(async () => { const file = new File(item.local_uri); if (!file.exists) throw new Error(t('scanner.fileMissing')); await file.preview({ title: item.document_name, mimeType: 'application/pdf' }); }); }} /><Button label={t('scanner.share')} variant="secondary" loading={busy} onPress={() => { void action(async () => { if (!await Sharing.isAvailableAsync()) throw new Error(t('scanner.shareUnavailable')); await Sharing.shareAsync(item.local_uri, { mimeType: 'application/pdf', dialogTitle: item.document_name }); }); }} /><Button label={t('scanner.export')} variant="secondary" loading={busy} onPress={() => { void action(async () => { if (Platform.OS === 'web') throw new Error(t('scanner.exportUnavailable')); if (Platform.OS === 'ios') { await Sharing.shareAsync(item.local_uri, { mimeType: 'application/pdf' }); return; } const folder = await Directory.pickDirectoryAsync(); const destination = new File(folder, item.original_filename); await new File(item.local_uri).copy(destination); }); }} /><Button label={t('scanner.print')} variant="secondary" loading={busy} onPress={() => { void action(() => Print.printAsync({ uri: item.local_uri })); }} /><Button label={t('scanner.pdfTools')} variant="secondary" onPress={() => router.push({ pathname: '/scanner/pdf-tools', params: { id } })} /><Button label={t('scanner.annotate')} variant="secondary" onPress={() => router.push({ pathname: '/scanner/annotate', params: { id } })} /><Button label={t('scanner.deleteDocument')} variant="text" onPress={() => Alert.alert(t('scanner.deleteDocument'), t('scanner.deleteConfirm'), [{ text: t('cancel'), style: 'cancel' }, { text: t('scanner.deleteDocument'), style: 'destructive', onPress: () => { void action(async () => { await deleteDocument(user!.id, id); await cache.invalidateQueries({ queryKey: ['local-documents', user!.id] }); router.replace('/(tabs)/scanner'); }); } }])} /></View></>}</Screen>;
}
