import { useEffect, useRef, useState } from 'react';
import { Alert, AppState, Linking } from 'react-native';
import { router, useLocalSearchParams, useNavigation, usePreventRemove } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { TextField } from '../../components/common/TextField';
import { Notice } from '../../components/common/Notice';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { ErrorState } from '../../components/common/ErrorState';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { RichEditor } from '../../components/drafting/RichEditor';
import { draftingApi, type DraftRecord, type DraftVersion } from '../../services/drafting-api';
import { apiRequest, ApiError } from '../../services/api';
import { friendlyError } from '../../utils/errors';

export default function DraftEditor() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t } = useTranslation();
  const q = useQuery({ queryKey: ['draft', id], queryFn: () => draftingApi.get(id) });
  return q.isPending ? (
    <Screen title={t('work.drafting')} back>
      <LoadingSkeleton />
    </Screen>
  ) : q.isError ? (
    <Screen back>
      <ErrorState message={t('work.error')} retry={() => void q.refetch()} />
    </Screen>
  ) : (
    <EditorBody key={id} initial={q.data} />
  );
}
function EditorBody({ initial }: { initial: DraftRecord }) {
  const { t } = useTranslation();
  const navigation = useNavigation();
  const qc = useQueryClient();
  const [title, setTitle] = useState(initial.title);
  const [html, setHtml] = useState(initial.content);
  const [status, setStatus] = useState(initial.status);
  const [saved, setSaved] = useState(JSON.stringify([initial.title, initial.content, initial.status]));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState(false);
  const [replacement, setReplacement] = useState<{ html: string; key: number }>();
  const [showClauses, setShowClauses] = useState(false);
  const [clauseSearch, setClauseSearch] = useState('');
  const [version, setVersion] = useState<DraftVersion>();
  const [autofill, setAutofill] = useState<Record<string, string>>();
  const revision = useRef(initial.updated_at);
  const savedRef = useRef(saved);
  useEffect(() => {
    if (JSON.stringify([initial.title, initial.content, initial.status]) === savedRef.current) {
      revision.current = initial.updated_at;
    }
  }, [initial]);
  const current = useRef({ title, html, status });
  useEffect(() => {
    current.current = { title, html, status };
  }, [title, html, status]);
  const inflight = useRef<Promise<boolean> | null>(null);
  const dirty = JSON.stringify([title, html, status]) !== saved;
  const versions = useQuery({
    queryKey: ['draft-versions', initial.id],
    queryFn: () => draftingApi.versions(initial.id),
  });
  const clauses = useQuery({
    queryKey: ['draft-clause-options', clauseSearch],
    queryFn: () => draftingApi.library('draft-clauses', clauseSearch),
    enabled: showClauses,
  });
  async function save(): Promise<boolean> {
    while (inflight.current) await inflight.current;
    const value = { ...current.current };
    const serialized = JSON.stringify([value.title, value.html, value.status]);
    if (serialized === savedRef.current) return true;
    setBusy(true);
    const task = (async () => {
      try {
        const row = await draftingApi.save(initial.id, {
          title: value.title,
          content: value.html,
          status: value.status,
          expected_updated_at: revision.current,
        });
        revision.current = row.updated_at;
        savedRef.current = serialized;
        setSaved(serialized);
        qc.setQueryData(['draft', initial.id], row);
        setError('');
        void qc.invalidateQueries({ queryKey: ['drafts'] });
        void versions.refetch();
        return true;
      } catch (e) {
        setError(e instanceof ApiError && e.status === 409 ? t('work.conflict') : friendlyError(e));
        return false;
      }
    })();
    inflight.current = task;
    try {
      return await task;
    } finally {
      inflight.current = null;
      setBusy(false);
    }
  }
  const saveRef = useRef(save);
  useEffect(() => {
    saveRef.current = save;
  });
  useEffect(() => {
    if (!dirty) return;
    const timer = setTimeout(() => void saveRef.current(), 1600);
    return () => clearTimeout(timer);
  }, [html, title, status, dirty]);
  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state !== 'active') void saveRef.current();
    });
    return () => sub.remove();
  }, []);
  usePreventRemove(dirty || busy, ({ data }) =>
    Alert.alert(t('work.leaveTitle'), t('work.unsaved'), [
      { text: t('work.cancel'), style: 'cancel' },
      { text: t('work.discard'), style: 'destructive', onPress: () => navigation.dispatch(data.action) },
      {
        text: t('work.save'),
        onPress: () => {
          void save().then((ok) => {
            if (ok) navigation.dispatch(data.action);
          });
        },
      },
    ]),
  );
  function replace(value: string) {
    setHtml(value);
    current.current.html = value;
    setReplacement({ html: value, key: Date.now() });
  }
  async function perform(action: string) {
    if (!(await save())) return;
    try {
      await draftingApi.action(initial.id, action);
      void qc.invalidateQueries({ queryKey: ['drafts'] });
      router.back();
    } catch (e) {
      setError(friendlyError(e));
    }
  }
  async function exportFile(file_format: string) {
    if (!(await save())) return;
    setBusy(true);
    try {
      const result = await apiRequest<{ url: string }>(`/draft-documents/${initial.id}/export`, {
        method: 'POST',
        body: JSON.stringify({ file_format }),
      });
      await Linking.openURL(result.url);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  async function loadAutofill() {
    try {
      const result = await apiRequest<{ values: Record<string, string | null> }>(
        `/draft-documents/${initial.id}/autofill`,
      );
      const values = Object.fromEntries(
        Object.entries(result.values).map(([key, value]) => [key, value ?? '']),
      );
      for (const token of html.matchAll(/\{\{\s*([\w.]+)\s*\}\}/g))
        if (!(token[1] in values)) values[token[1]] = '';
      setAutofill(values);
    } catch (e) {
      setError(friendlyError(e));
    }
  }
  const escape = (value: string) =>
    value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
  return (
    <Screen record={initial} title={t('work.drafting')} back>
<Button label={t('notifications.newReminder')} variant="secondary" onPress={()=>router.push({pathname:'/notifications/create',params:{entity_type:'draft',entity_id:initial.id}})}/>
      {error && <Notice message={error} />}
      <AppText>{busy ? t('work.saving') : dirty ? t('work.unsaved') : t('work.saved')}</AppText>
      <TextField label={t('work.title')} value={title} onChangeText={setTitle} />
      <ChoiceChips
        value={status}
        onChange={setStatus}
        options={['draft', 'review', 'final'].map((value) => ({ value, label: t(`work.${value}`, value) }))}
      />
      <Button
        label={preview ? t('work.back') : t('work.preview')}
        variant="secondary"
        onPress={() => setPreview(!preview)}
      />
      {version ? (
        <>
          <RichEditor key={version.id} initialHtml={version.content} onChange={() => {}} preview />
          <Button
            label={t('work.restore')}
            onPress={() =>
              Alert.alert(t('work.confirm'), t('work.confirmBody'), [
                { text: t('work.cancel'), style: 'cancel' },
                {
                  text: t('work.restore'),
                  onPress: () => {
                    void (async () => {
                      if (!(await save())) return;
                      try {
                        await draftingApi.action(initial.id, `versions/${version.id}/restore`);
                        const restored = await draftingApi.get(initial.id);
                        revision.current = restored.updated_at;
                        replace(restored.content);
                        setVersion(undefined);
                        void versions.refetch();
                      } catch (e) {
                        setError(friendlyError(e));
                      }
                    })();
                  },
                },
              ])
            }
          />
          <Button label={t('work.back')} onPress={() => setVersion(undefined)} />
        </>
      ) : preview ? (
        <RichEditor key="preview" initialHtml={html} onChange={() => {}} preview />
      ) : (
        <RichEditor initialHtml={html} replacement={replacement} onChange={setHtml} />
      )}
      {!initial.archived_at && <Button label={t('ai.kinds.draft')} variant="secondary" disabled={busy}
        onPress={() => { void save().then(ok => {
          if (ok) router.replace({ pathname: '/ai/request', params: { mode: 'draft', draftId: initial.id } });
        }); }} />}
      <Button label={t('work.save')} loading={busy} onPress={() => void save()} />
      <Button label={t('work.autofill')} variant="secondary" onPress={() => void loadAutofill()} />
      {autofill && (
        <>
          {Object.entries(autofill).map(([key, value]) => (
            <TextField
              key={key}
              label={key}
              value={value}
              onChangeText={(text) => setAutofill({ ...autofill, [key]: text })}
            />
          ))}
          <Button
            label={t('work.applyAutofill')}
            onPress={() => {
              const missing: string[] = [];
              replace(
                html.replace(/\{\{\s*([\w.]+)\s*\}\}/g, (token, key: string) => {
                  if (!autofill[key]) {
                    missing.push(key);
                    return token;
                  }
                  return escape(autofill[key]);
                }),
              );
              setAutofill(undefined);
              if (missing.length) setError(t('work.missing') + ': ' + missing.join(', '));
            }}
          />
        </>
      )}
      <Button label={t('work.clauses')} variant="secondary" onPress={() => setShowClauses(!showClauses)} />
      {showClauses && (
        <TextField label={t('work.search')} value={clauseSearch} onChangeText={setClauseSearch} />
      )}{' '}
      {showClauses &&
        clauses.data?.map((clause) => (
          <Button
            key={clause.id}
            label={clause.title ?? ''}
            variant="secondary"
            onPress={() => replace(html + '<p>' + clause.content + '</p>')}
          />
        ))}
      <ChoiceChips
        value=""
        onChange={(token) => replace(html + '<p>{{' + token + '}}</p>')}
        options={['advocate.name', 'client.name', 'case.number', 'court.name', 'document.content'].map(
          (value) => ({ value, label: '{{' + value + '}}' }),
        )}
      />
      <Button
        label={t('work.snapshot')}
        variant="secondary"
        onPress={() => {
          void (async () => {
            if (await save())
              try {
                await draftingApi.action(initial.id, 'versions');
                void versions.refetch();
              } catch (e) {
                setError(friendlyError(e));
              }
          })();
        }}
      />
      <AppText>{t('work.versions')}</AppText>
      {versions.data?.map((v) => (
        <Button
          key={v.id}
          label={`${v.version_number} · ${v.created_at.slice(0, 16)}`}
          variant="secondary"
          onPress={() => setVersion(v)}
        />
      ))}
      <Button label={t('work.exportPdf')} loading={busy} onPress={() => void exportFile('pdf')} />
      <Button label={t('work.exportDocx')} loading={busy} onPress={() => void exportFile('docx')} />
      <Button label={t('work.duplicate')} variant="secondary" onPress={() => void perform('duplicate')} />
      <Button
        label={initial.archived_at ? t('work.restore') : t('work.archive')}
        variant="secondary"
        onPress={() => void perform(initial.archived_at ? 'restore' : 'archive')}
      />
    </Screen>
  );
}
