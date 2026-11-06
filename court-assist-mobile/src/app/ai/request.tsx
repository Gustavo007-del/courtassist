import { useRef, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { randomUUID } from 'expo-crypto';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { ContextPicker, ExternalConsent, Pagination, Toggle } from '../../components/ai/Controls';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { TextField } from '../../components/common/TextField';
import { Screen } from '../../components/layout/Screen';
import { aiApi, aiErrorKey, type ContextRow, type JobKind, type Language } from '../../services/ai-api';
import { useSyncState } from '../../features/sync/state';
import { caseApi } from '../../services/case-api';
import { diaryApi } from '../../services/diary-api';
import { documentApi } from '../../services/document-api';
import { draftingApi } from '../../services/drafting-api';

type Params = { mode?: JobKind; caseId?: string; documentId?: string; draftId?: string; entryId?: string; conversationId?: string; previousJobId?: string };
const documentOperations = { summarize: 'summarize', dates: 'extract-dates', metadata: 'extract-metadata' } as const;
const languages = ['source', 'en', 'ml'] as const;
const draftActions = ['improve', 'rewrite', 'organize', 'summarize', 'translate'] as const;
const diaryActions = ['improve', 'organize', 'actions', 'chronological'] as const;

export default function AIRequest() {
  const params = useLocalSearchParams<Params>();
  const mode = params.mode ?? 'ask';
  const { t } = useTranslation();
  const cache = useQueryClient();
  const config = useQuery({ queryKey: ['ai', 'preferences'], queryFn: aiApi.preferences });
  const [caseId, setCaseId] = useState(params.caseId);
  const [documentId, setDocumentId] = useState(params.documentId);
  const [draftId, setDraftId] = useState(params.draftId);
  const [scope, setScope] = useState<ContextRow[]>([]);
  const [text, setText] = useState('');
  const [language, setLanguage] = useState<Language>('source');
  const [action, setAction] = useState<string>('organize');
  const [external, setExternal] = useState(false);
  const [includePrevious, setIncludePrevious] = useState(false);
  const [pages, setPages] = useState<Record<string, { first: string; last: string }>>({});
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const attempt = useRef<{ payload: string; id: string } | null>(null);

  const assistant = mode === 'ask' || mode === 'chronology';
  const documentMode = mode === 'summarize' || mode === 'dates' || mode === 'metadata';
  const writing = mode === 'draft' || mode === 'diary';
  const selectedCase = useQuery({ queryKey: ['case', caseId], queryFn: () => caseApi.get(caseId!), enabled: !!caseId });
  const selectedDoc = useQuery({ queryKey: ['vault-document', documentId], queryFn: () => documentApi.get(documentId!), enabled: documentMode && !!documentId });
  const selectedDraft = useQuery({ queryKey: ['draft', draftId], queryFn: () => draftingApi.get(draftId!), enabled: mode === 'draft' && !!draftId });
  const diary = useQuery({ queryKey: ['diary-entry', params.entryId], queryFn: () => diaryApi.get(params.entryId!), enabled: mode === 'diary' && !!params.entryId });
  const drafts = useQuery({
    queryKey: ['ai', 'draft-options', offset], queryFn: () => draftingApi.list({ limit: '20', offset: String(offset) }),
    enabled: mode === 'draft' && !draftId && !!config.data?.enabled && !!config.data.available,
  });
  const prefs = config.data;
  const usesDocument = documentMode || scope.some(row => row.kind === 'document');
  const offline = useSyncState(state => state.connected === false);
  const blocked = offline || !prefs?.available || !prefs.enabled
    || (assistant && !prefs.assistant) || (usesDocument && !prefs.documents)
    || (mode === 'ask' && usesDocument && !prefs.embeddings_available)
    || (prefs.external_provider && (!prefs.external || !external));
  const incomplete = (assistant && scope.length === 0) || (mode === 'chronology' && !caseId)
    || (mode === 'ask' && !text.trim()) || (writing && !text.trim())
    || (mode === 'draft' && !selectedDraft.data) || (documentMode && !selectedDoc.data);

  function pageRange(id: string) {
    const bounds = pages[id];
    if (!bounds || (!bounds.first && !bounds.last)) return {};
    const first = Number(bounds.first);
    const last = Number(bounds.last);
    if (!Number.isInteger(first) || !Number.isInteger(last) || first < 1 || first > last || last > 500) {
      throw new Error('invalid_page_range');
    }
    return { first_page: first, last_page: last };
  }

  async function submit() {
    if (blocked || incomplete) return;
    setBusy(true);
    setError('');
    try {
      const sources = scope.map(({ kind, id }) => ({ kind, id, ...(kind === 'document' ? pageRange(id) : {}) }));
      const range = documentMode && documentId ? pageRange(documentId) : {};
      const confirmation = prefs?.external_provider && external ? prefs.external_confirmation : undefined;
      const fingerprint = JSON.stringify({ mode, caseId, documentId, draftId, text, language, action, sources, range, confirmation, includePrevious });
      if (attempt.current?.payload !== fingerprint) attempt.current = { payload: fingerprint, id: randomUUID() };
      const base = { request_id: attempt.current.id, language, external_confirmation: confirmation };
      const job = mode === 'ask' ? await aiApi.ask({
        ...base, question: text, case_id: caseId, sources, previous_job_id: includePrevious ? params.previousJobId : undefined,
      }, params.conversationId)
        : mode === 'chronology' ? await aiApi.chronology(caseId!, { ...base, sources })
        : documentMode ? await aiApi.document(documentId!, documentOperations[mode], { ...base, ...range })
        : mode === 'draft' ? await aiApi.draft(draftId!, action, { ...base, text })
        : await aiApi.diary({ ...base, text, action, case_id: caseId, entry_id: params.entryId });
      void cache.invalidateQueries({ queryKey: ['ai'] });
      router.replace({ pathname: '/ai/job', params: { id: job.id } });
    } catch (caught) {
      const key = caught instanceof Error && caught.message === 'invalid_page_range'
        ? 'ai.errors.invalid_page_range' : aiErrorKey(caught);
      setError(t(key, { defaultValue: t('work.error') }));
    } finally {
      setBusy(false);
    }
  }

  const pageFields = (id: string) => <Card>
    <AppText>{t('ai.pagesOptional')}</AppText>
    <TextField label={t('ai.firstPage')} keyboardType="numeric" value={pages[id]?.first ?? ''}
      onChangeText={first => setPages(current => ({ ...current, [id]: { first, last: current[id]?.last ?? '' } }))} />
    <TextField label={t('ai.lastPage')} keyboardType="numeric" value={pages[id]?.last ?? ''}
      onChangeText={last => setPages(current => ({ ...current, [id]: { first: current[id]?.first ?? '', last } }))} />
  </Card>;

  return <Screen back title={t(`ai.kinds.${mode}`)} subtitle={t('ai.disclaimer')}>
    {offline && <AppText>{t('sync.errors.offline_online_required')}</AppText>}
    {error && <AppText>{error}</AppText>}
    {config.isPending ? <LoadingSkeleton /> : config.isError || !prefs
      ? <ErrorState message={t('work.error')} retry={() => void config.refetch()} />
      : !prefs.available || !prefs.enabled ? <>
        <AppText>{t(prefs.available ? 'ai.disabled' : 'ai.unavailable')}</AppText>
        <Button label={t('ai.preferences')} onPress={() => router.push('/ai/preferences')} />
      </> : <>
        {(assistant || mode === 'diary') && <>
          <AppText>{t('ai.caseScope')}</AppText>
          {caseId ? <Button variant="secondary" label={selectedCase.data?.case_title ?? t('ai.sources.case')}
            onPress={() => { setCaseId(undefined); setScope([]); }} />
            : <ContextPicker only="case" selected={[]} onPick={row => { setCaseId(row.id); setScope([]); }} />}
        </>}
        {assistant && <>
          <AppText>{t('ai.contextExplanation', { count: scope.length })}</AppText>
          <ContextPicker key={caseId ?? 'all'} caseId={caseId} selected={scope} onPick={row => setScope(current => {
            const chosen = current.some(item => item.kind === row.kind && item.id === row.id);
            return chosen ? current.filter(item => item.kind !== row.kind || item.id !== row.id) : current.length < 30 ? [...current, row] : current;
          })} />
          {scope.map(row => <Card key={row.kind + row.id}>
            <AppText>{row.title}</AppText>
            {row.kind === 'document' && pageFields(row.id)}
            <Button label={t('ai.removeSource')} variant="text" onPress={() => setScope(current => current.filter(item => item !== row))} />
          </Card>)}
        </>}
        {documentMode && (documentId ? <>
          {selectedDoc.isError ? <ErrorState message={t('work.error')} retry={() => void selectedDoc.refetch()} />
            : <Button variant="secondary" label={selectedDoc.data?.document_name ?? t('ai.sources.document')} onPress={() => setDocumentId(undefined)} />}
          {pageFields(documentId)}
          <Button variant="text" label={t('ai.documentResults')} onPress={() => router.push({
            pathname: '/ai/history', params: { documentId },
          })} />
        </> : <ContextPicker only="document" selected={[]} onPick={row => setDocumentId(row.id)} />)}
        {mode === 'draft' && (draftId
          ? <Button variant="secondary" label={selectedDraft.data?.title ?? t('ai.kinds.draft')} onPress={() => setDraftId(undefined)} />
          : <Card>
            {drafts.isPending ? <LoadingSkeleton rows={2} /> : drafts.isError
              ? <ErrorState message={t('work.error')} retry={() => void drafts.refetch()} />
              : <>
                {!drafts.data.length && <AppText>{t('ai.emptySources')}</AppText>}
                {drafts.data.map(draft => <Button key={draft.id} label={draft.title} variant="secondary" onPress={() => setDraftId(draft.id)} />)}
                <Pagination offset={offset} hasMore={drafts.data.length === 20} setOffset={setOffset} />
              </>}
          </Card>)}
        {mode === 'diary' && diary.data && <Button variant="secondary" label={t('ai.copyDiaryText')} onPress={() => setText(diary.data.content)} />}
        {writing && <ChoiceChips value={action} onChange={setAction}
          options={(mode === 'draft' ? draftActions : diaryActions).map(value => ({ value, label: t(`ai.actions.${value}`) }))} />}
        {(mode === 'ask' || writing) && <TextField multiline label={t(mode === 'ask' ? 'ai.question' : 'ai.selectedText')}
          value={text} onChangeText={setText} />}
        {mode === 'ask' && params.previousJobId &&
          <Toggle label={t('ai.includePrevious')} value={includePrevious} onChange={setIncludePrevious} />}
        {writing
          ? <ChoiceChips value={language} onChange={setLanguage} options={languages.map(value => ({ value, label: t(`ai.languages.${value}`) }))} />
          : <AppText>{t('ai.originalQuotes')}</AppText>}
        {assistant && !prefs.assistant && <AppText>{t('ai.errors.assistant_consent_required')}</AppText>}
        {usesDocument && !prefs.documents && <AppText>{t('ai.errors.document_consent_required')}</AppText>}
        {mode === 'ask' && usesDocument && !prefs.embeddings_available && <AppText>{t('ai.errors.embedding_model_required')}</AppText>}
        <ExternalConsent prefs={prefs} allowed={external} onChange={setExternal} />
        {blocked && <Button variant="text" label={t('ai.preferences')} onPress={() => router.push('/ai/preferences')} />}
        <Button label={t('ai.submit')} loading={busy} disabled={blocked || incomplete} onPress={() => void submit()} />
      </>}
  </Screen>;
}

