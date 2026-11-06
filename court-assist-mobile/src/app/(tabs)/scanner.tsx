import { useEffect, useState } from 'react';
import { Alert, Platform, View } from 'react-native';
import { router } from 'expo-router';
import { CameraView } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import * as ImageManipulator from 'expo-image-manipulator';
import { File } from 'expo-file-system';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { EmptyState } from '../../components/common/EmptyState';
import { Notice } from '../../components/common/Notice';
import { Screen } from '../../components/layout/Screen';
import { useScannerStore } from '../../features/scanner/store';
import { listDocuments } from '../../features/scanner/storage';
import { useAuthStore } from '../../store/auth-store';
import { friendlyError } from '../../utils/errors';

export default function Scanner() {
  const { t } = useTranslation(); const user = useAuthStore((state) => state.user); const pages = useScannerStore((state) => state.pages); const hydrate = useScannerStore((state) => state.hydrate); const add = useScannerStore((state) => state.add); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  useEffect(() => { if (user?.id) void hydrate(user.id).catch((caught) => setError(friendlyError(caught))); }, [hydrate, user?.id]);
  const documents = useQuery({ queryKey: ['local-documents', user?.id], queryFn: () => listDocuments(user!.id), enabled: !!user?.id });
  const nativeScan = async () => { if (Platform.OS === 'web' || !CameraView.isDocumentScannerAvailable) { setError(t('scanner.nativeUnavailable')); return; } setBusy(true); setError(null); try { const result = await CameraView.scanDocumentAsync({ requestPdf: false }); if (result) { for (const uri of result.pages) { const image = await ImageManipulator.manipulateAsync(uri, [], { format: ImageManipulator.SaveFormat.JPEG, compress: 1 }); await add(image.uri, image.width, image.height); for (const temporaryUri of new Set([uri, image.uri])) { const temporary = new File(temporaryUri); if (temporary.exists) temporary.delete(); } } router.push('/scanner/review'); } } catch (caught) { setError(friendlyError(caught)); } finally { setBusy(false); } };
  const importImages = async () => { setBusy(true); setError(null); try { const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsMultipleSelection: true, quality: 1 }); if (!result.canceled) { for (const asset of result.assets) { const image = await ImageManipulator.manipulateAsync(asset.uri, [], { format: ImageManipulator.SaveFormat.JPEG, compress: 1 }); await add(image.uri, image.width, image.height); if (image.uri !== asset.uri) { const temporary = new File(image.uri); if (temporary.exists) temporary.delete(); } } router.push('/scanner/review'); } } catch (caught) { setError(friendlyError(caught)); } finally { setBusy(false); } };
  return <Screen title={t('scanner.title')} subtitle={t('scanner.localOnly')} refreshing={documents.isRefetching} onRefresh={() => { void documents.refetch(); }}>{error && <Notice message={error} />}<View style={{ gap: 8 }}><Button label={t('scanner.nativeScan')} loading={busy} onPress={() => { void nativeScan(); }} /><Button label={t('scanner.camera')} variant="secondary" onPress={() => router.push('/scanner/camera')} /><Button label={t('scanner.importImages')} variant="secondary" loading={busy} onPress={() => { void importImages(); }} />{pages.length > 0 && <Button label={`${t('scanner.resume')} · ${pages.length}`} variant="secondary" onPress={() => router.push('/scanner/review')} />}<Button label={t('scanner.pdfTools')} variant="secondary" onPress={() => router.push('/scanner/pdf-tools')} /></View><Card style={{ marginTop: 20 }}><AppText>{t('scanner.nativeNote')}</AppText></Card><View style={{ marginTop: 18 }}><AppText style={{ fontSize: 20, fontWeight: '800' }}>{t('scanner.savedDocuments')}</AppText>{documents.data?.length ? documents.data.map((document) => <Button key={document.id} label={`${document.document_name} · ${document.page_count} ${t('scanner.pages')}`} variant="text" onPress={() => router.push({ pathname: '/scanner/document-details', params: { id: document.id } })} />) : <EmptyState title={t('scanner.noDocuments')} body={t('scanner.noDocumentsDetail')} />}</View><Button label={t('scanner.discardDraft')} variant="text" disabled={!pages.length} onPress={() => Alert.alert(t('scanner.discardDraft'), t('scanner.discardConfirm'), [{ text: t('cancel'), style: 'cancel' }, { text: t('scanner.discardDraft'), style: 'destructive', onPress: () => { void useScannerStore.getState().clear(); } }])} /></Screen>;
}
