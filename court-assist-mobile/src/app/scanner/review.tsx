import { useState } from 'react';
import { Alert, View } from 'react-native';
import { router } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { EmptyState } from '../../components/common/EmptyState';
import { Notice } from '../../components/common/Notice';
import { TextField } from '../../components/common/TextField';
import { PageThumbnail } from '../../components/scanner/PageThumbnail';
import { Screen } from '../../components/layout/Screen';
import { createPdfFromPages } from '../../features/scanner/pdf-tools';
import { useScannerStore } from '../../features/scanner/store';
import { savePdfCopy } from '../../features/scanner/storage';
import { DOCUMENT_CATEGORIES, type Compression, type DocumentCategory } from '../../features/scanner/types';
import { caseApi } from '../../services/case-api';
import { useAuthStore } from '../../store/auth-store';
import { friendlyError } from '../../utils/errors';

export default function ScanReview() {
  const { t } = useTranslation(); const user = useAuthStore((state) => state.user); const cache = useQueryClient(); const pages = useScannerStore((state) => state.pages); const [name, setName] = useState(''); const [category, setCategory] = useState<DocumentCategory>('Other'); const [caseId, setCaseId] = useState(''); const [caseSearch, setCaseSearch] = useState(''); const [quality, setQuality] = useState<Compression>('high'); const [busy, setBusy] = useState(false); const [progress, setProgress] = useState(''); const [error, setError] = useState<string | null>(null);
  const cases = useQuery({ queryKey: ['scan-cases', caseSearch], queryFn: () => caseApi.list({ q: caseSearch, limit: 100 }) });
  const generate = async () => { if (!user || !pages.length || busy) return; setBusy(true); setError(null); try { if (caseId) await caseApi.get(caseId); const title = name.trim() || t('scanner.defaultName'); const bytes = await createPdfFromPages(pages, quality, (done, total) => setProgress(`${done}/${total}`)); const saved = await savePdfCopy(user.id, bytes, title, pages.length, caseId || null, category); const id = saved.id; await cache.invalidateQueries({ queryKey: ['local-documents', user.id] }); router.replace({ pathname: '/scanner/document-details', params: { id } }); } catch (caught) { setError(friendlyError(caught)); } finally { setBusy(false); setProgress(''); } };
  return <Screen title={t('scanner.review')} subtitle={t('scanner.localOnly')} back>{error && <Notice message={error} />}{!pages.length ? <EmptyState title={t('scanner.noPages')} body={t('scanner.noPagesDetail')} /> : <><TextField label={t('scanner.documentTitle')} value={name} onChangeText={setName} /><AppText>{t('scanner.pages')}: {pages.length}</AppText><AppText>{t('scanner.outputFormat')}: PDF · A4</AppText><AppText>{t('scanner.compression')}</AppText><ChoiceChips value={quality} onChange={setQuality} options={(['high', 'balanced', 'small'] as const).map((value) => ({ value, label: t(`scanner.quality.${value}`) }))} /><AppText>{t('scanner.category')}</AppText><ChoiceChips value={category} onChange={setCategory} options={DOCUMENT_CATEGORIES.map((value) => ({ value, label: t(`scanner.categories.${value}`) }))} /><TextField label={t('cases.search')} value={caseSearch} onChangeText={setCaseSearch} /><ChoiceChips value={caseId} onChange={setCaseId} options={[{ value: '', label: t('scanner.noCase') }, ...(cases.data?.items ?? []).map((item) => ({ value: item.id, label: `${item.case_title} · ${item.case_number}` }))]} /><View style={{ marginTop: 18 }}>{pages.map((page, index) => <PageThumbnail key={page.id} page={page} index={index} total={pages.length} onEdit={() => router.push({ pathname: '/scanner/edit-page', params: { id: page.id } })} onRetake={() => router.push({ pathname: '/scanner/camera', params: { retakeId: page.id } })} onRemove={() => Alert.alert(t('scanner.removePage'), t('scanner.removeConfirm'), [{ text: t('cancel'), style: 'cancel' }, { text: t('scanner.removePage'), style: 'destructive', onPress: () => { void useScannerStore.getState().remove(page.id); } }])} onMove={(direction) => { void useScannerStore.getState().move(page.id, direction); }} />)}</View>{progress && <AppText>{t('scanner.processing')} {progress}</AppText>}<Button label={t('scanner.addPages')} variant="secondary" onPress={() => router.push('/scanner/camera')} /><Button label={t('scanner.generatePdf')} loading={busy} onPress={() => { void generate(); }} /><Button label={t('cancel')} variant="text" onPress={() => router.back()} /></>}</Screen>;
}
