import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { File } from 'expo-file-system';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { EmptyState } from '../../components/common/EmptyState';
import { Notice } from '../../components/common/Notice';
import { TextField } from '../../components/common/TextField';
import { Screen } from '../../components/layout/Screen';
import { reorderPdf, rotatePages } from '../../features/scanner/pdf-tools';
import { listDocuments, savePdfCopy } from '../../features/scanner/storage';
import { useAuthStore } from '../../store/auth-store';
import { friendlyError } from '../../utils/errors';

export default function PdfTools() { const { id } = useLocalSearchParams<{ id?: string }>(); const { t } = useTranslation(); const user = useAuthStore((state) => state.user); const cache = useQueryClient(); const [selected, setSelected] = useState(id ?? ''); const [pages, setPages] = useState('1'); const [order, setOrder] = useState(''); const [angle, setAngle] = useState<90 | 180 | 270>(90); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  const documents = useQuery({ queryKey: ['local-documents', user?.id], queryFn: () => listDocuments(user!.id), enabled: !!user }); const item = documents.data?.find((entry) => entry.id === selected);
  const parse = (value: string) => { if (!item) throw new Error(t('scanner.selectDocument')); const values = value.split(',').map((part) => Number(part.trim())); if (!values.length || values.some((part) => !Number.isInteger(part) || part < 1 || part > item.page_count)) throw new Error(t('scanner.invalidRange')); return values.map((part) => part - 1); };
  const saveCopy = async (kind: 'rotate' | 'order') => { if (!item || !user || busy) return; setBusy(true); setError(null); try { const indices = parse(kind === 'rotate' ? pages : order); const bytes = kind === 'rotate' ? await rotatePages(item.local_uri, indices, angle) : await reorderPdf(item.local_uri, indices); const output = await savePdfCopy(user.id, bytes, `${item.document_name} ${t(kind === 'rotate' ? 'scanner.rotated' : 'scanner.reordered')}`, kind === 'rotate' ? item.page_count : indices.length, item.case_id, item.document_category); await cache.invalidateQueries({ queryKey: ['local-documents', user.id] }); router.push({ pathname: '/scanner/document-details', params: { id: output.id } }); } catch (caught) { setError(friendlyError(caught)); } finally { setBusy(false); } };
  return <Screen title={t('scanner.pdfTools')} subtitle={t('scanner.originalPreserved')} back>{error && <Notice message={error} />}<Button label={t('scanner.merge')} onPress={() => router.push('/scanner/merge')} />{!documents.data?.length ? <EmptyState title={t('scanner.noDocuments')} body={t('scanner.noDocumentsDetail')} /> : <><AppText>{t('scanner.selectDocument')}</AppText><ChoiceChips value={selected} onChange={setSelected} options={documents.data.map((document) => ({ value: document.id, label: document.document_name }))} />{item && <><AppText>{item.page_count} {t('scanner.pages')} · {(item.file_size / 1024 / 1024).toFixed(2)} MB</AppText><Button label={t('scanner.openPdf')} variant="secondary" onPress={() => { void new File(item.local_uri).preview({ title: item.document_name }).catch((caught) => setError(friendlyError(caught))); }} /><Button label={t('scanner.split')} variant="secondary" onPress={() => router.push({ pathname: '/scanner/split', params: { id: item.id } })} /><TextField label={t('scanner.rotatePages')} value={pages} onChangeText={setPages} /><ChoiceChips value={String(angle)} onChange={(value) => setAngle(Number(value) as 90 | 180 | 270)} options={([90, 180, 270] as const).map((value) => ({ value: String(value), label: `${value}°` }))} /><Button label={t('scanner.saveRotated')} loading={busy} onPress={() => { void saveCopy('rotate'); }} /><TextField label={t('scanner.pageOrder')} value={order} onChangeText={setOrder} /><AppText>{t('scanner.orderHint')}</AppText><Button label={t('scanner.savePageOrder')} loading={busy} onPress={() => { void saveCopy('order'); }} /><Button label={t('scanner.annotate')} variant="secondary" onPress={() => router.push({ pathname: '/scanner/annotate', params: { id: item.id } })} /></>}</>}</Screen>;
}
