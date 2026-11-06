import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { Notice } from '../../components/common/Notice';
import { TextField } from '../../components/common/TextField';
import { Screen } from '../../components/layout/Screen';
import { extractPages } from '../../features/scanner/pdf-tools';
import { getDocument, savePdfCopy } from '../../features/scanner/storage';
import { useAuthStore } from '../../store/auth-store';
import { friendlyError } from '../../utils/errors';

export default function SplitPdf() { const { id } = useLocalSearchParams<{ id: string }>(); const { t } = useTranslation(); const user = useAuthStore((state) => state.user); const cache = useQueryClient(); const [selection, setSelection] = useState('1'); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null); const query = useQuery({ queryKey: ['local-document', user?.id, id], queryFn: () => getDocument(user!.id, id), enabled: !!user && !!id }); const item = query.data;
  const extract = async () => { if (!item || !user || busy) return; setBusy(true); setError(null); try { const indices = new Set<number>(); for (const part of selection.split(',')) { const match = /^\s*(\d+)(?:\s*-\s*(\d+))?\s*$/.exec(part); if (!match) throw new Error(t('scanner.invalidRange')); const start = Number(match[1]), end = Number(match[2] ?? match[1]); if (start < 1 || end > item.page_count || start > end) throw new Error(t('scanner.invalidRange')); for (let page = start; page <= end; page++) indices.add(page - 1); } const pages = [...indices].sort((a, b) => a - b); const bytes = await extractPages(item.local_uri, pages); const saved = await savePdfCopy(user.id, bytes, `${item.document_name} ${t('scanner.extracted')}`, pages.length, item.case_id, item.document_category); await cache.invalidateQueries({ queryKey: ['local-documents', user.id] }); router.replace({ pathname: '/scanner/document-details', params: { id: saved.id } }); } catch (caught) { setError(friendlyError(caught)); } finally { setBusy(false); } };
  return <Screen title={t('scanner.split')} back>{query.isPending ? <LoadingSkeleton /> : query.isError || !item ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : <>{error && <Notice message={error} />}<AppText>{item.document_name} · {item.page_count} {t('scanner.pages')}</AppText><TextField label={t('scanner.pageRange')} value={selection} onChangeText={setSelection} /><AppText>{t('scanner.rangeHint')}</AppText><Button label={t('scanner.extract')} loading={busy} onPress={() => { void extract(); }} /></>}</Screen>;
}
