import { useRef, useState } from 'react';
import { Alert } from 'react-native';
import { router, useLocalSearchParams, useNavigation, usePreventRemove } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { TextField } from '../../components/common/TextField';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { Notice } from '../../components/common/Notice';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { RichEditor } from '../../components/drafting/RichEditor';
import { researchApi, type ResearchNote } from '../../services/research-api';
import { caseApi } from '../../services/case-api';
import { friendlyError } from '../../utils/errors';
export default function NoteEditor() {
  const { id, itemId, caseId } = useLocalSearchParams<{ id?: string; itemId?: string; caseId?: string }>();
  const { t } = useTranslation();
  const q = useQuery({
    queryKey: ['research-note', id],
    queryFn: () => researchApi.note(id!),
    enabled: !!id,
  });
  return !id || q.data ? (
    <NoteForm key={id ?? 'new'} initial={q.data} itemId={itemId} caseId={caseId} />
  ) : (
    <Screen title={t('research.notes')} back>
      {q.isError ? (
        <ErrorState message={t('work.error')} retry={() => void q.refetch()} />
      ) : (
        <LoadingSkeleton />
      )}
    </Screen>
  );
}
function NoteForm({ initial, itemId, caseId }: { initial?: ResearchNote; itemId?: string; caseId?: string }) {
  const { t, i18n } = useTranslation();
  const navigation = useNavigation();
  const qc = useQueryClient();
  const initialValues = {
    title: initial?.title ?? '',
    content: initial?.content ?? '',
    quoted_text: initial?.quoted_text ?? '',
    references: initial?.references ?? '',
    item_id: initial?.item_id ?? itemId ?? null,
    case_id: initial?.case_id ?? caseId ?? null,
    tags: initial?.tags ?? [],
    pinned: initial?.pinned ?? false,
    language: initial?.language ?? (i18n.language === 'ml' ? 'ml' : 'en'),
  };
  const [form, setForm] = useState(initialValues);
  const [original] = useState(JSON.stringify(initialValues));
  const saved = useRef(false);
  const [preview, setPreview] = useState(false);
  const [newTag, setNewTag] = useState('');
  const [itemSearch, setItemSearch] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const items = useQuery({
    queryKey: ['research-note-item-options', itemSearch],
    queryFn: () => researchApi.list({ q: itemSearch }),
  });
  const cases = useQuery({
    queryKey: ['research-case-options'],
    queryFn: () => caseApi.list({ limit: 100 }),
  });
  usePreventRemove(JSON.stringify(form) !== original, ({ data }) => {
    if (saved.current) {
      navigation.dispatch(data.action);
      return;
    }
    Alert.alert(t('work.unsaved'), t('research.unsavedNotice'), [
      { text: t('work.cancel'), style: 'cancel' },
      { text: t('work.discard'), style: 'destructive', onPress: () => navigation.dispatch(data.action) },
    ]);
  });
  async function save() {
    if (!form.title.trim()) {
      setError(t('work.invalid'));
      return;
    }
    setBusy(true);
    try {
      await researchApi.saveNote(initial?.id, form);
      saved.current = true;
      void qc.invalidateQueries({ queryKey: ['research-notes'] });
      router.back();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  async function archive() {
    if (!initial) return;
    try {
      if (initial.archived_at) await researchApi.restoreNote(initial.id);
      else await researchApi.archiveNote(initial.id);
      saved.current = true;
      void qc.invalidateQueries({ queryKey: ['research-notes'] });
      router.back();
    } catch (e) {
      setError(friendlyError(e));
    }
  }
  return (
    <Screen title={t('research.notes')} subtitle={t('research.analysisNotice')} back>
      {error && <Notice message={error} />}
      <TextField
        label={t('work.title')}
        value={form.title}
        onChangeText={(title) => setForm({ ...form, title })}
      />
      <Button
        label={t(preview ? 'work.edit' : 'work.preview')}
        variant="secondary"
        onPress={() => setPreview(!preview)}
      />
      <AppText>{t('research.analysis')}</AppText>
      <RichEditor
        key={String(preview)}
        initialHtml={form.content}
        preview={preview}
        onChange={(content) => setForm((current) => ({ ...current, content }))}
      />
      <TextField
        label={t('research.quotedText')}
        value={form.quoted_text}
        onChangeText={(quoted_text) => setForm({ ...form, quoted_text })}
        multiline
      />
      <TextField
        label={t('research.references')}
        value={form.references}
        onChangeText={(references) => setForm({ ...form, references })}
        multiline
      />
      <AppText>{t('research.pinned')}</AppText>
      <ChoiceChips
        value={String(form.pinned)}
        onChange={(value) => setForm({ ...form, pinned: value === 'true' })}
        options={[
          { value: 'false', label: '☆' },
          { value: 'true', label: '★' },
        ]}
      />
      <AppText>{t('work.language')}</AppText>
      <ChoiceChips
        value={form.language}
        onChange={(language) => setForm({ ...form, language })}
        options={[
          { value: 'en', label: 'English' },
          { value: 'ml', label: 'മലയാളം' },
        ]}
      />
      <AppText>{t('research.tags')}</AppText>
      {form.tags.map((tag) => (
        <Button
          key={tag}
          label={'× ' + tag}
          variant="secondary"
          onPress={() => setForm({ ...form, tags: form.tags.filter((value) => value !== tag) })}
        />
      ))}
      <TextField label={t('research.tagName')} value={newTag} onChangeText={setNewTag} />
      <Button
        label={t('research.addTag')}
        variant="secondary"
        onPress={() => {
          if (newTag.trim() && !form.tags.includes(newTag.trim()))
            setForm({ ...form, tags: [...form.tags, newTag.trim()] });
          setNewTag('');
        }}
      />
      <TextField label={t('research.linkedResearch')} value={itemSearch} onChangeText={setItemSearch} />
      <ChoiceChips
        value={form.item_id ?? ''}
        onChange={(item_id) => setForm({ ...form, item_id: item_id || null })}
        options={[
          { value: '', label: t('work.none') },
          ...(items.data?.items ?? []).map((item) => ({ value: item.id, label: item.title })),
        ]}
      />
      <AppText>{t('work.case')}</AppText>
      <ChoiceChips
        value={form.case_id ?? ''}
        onChange={(case_id) => setForm({ ...form, case_id: case_id || null })}
        options={[
          { value: '', label: t('work.none') },
          ...(cases.data?.items ?? []).map((row) => ({ value: row.id, label: row.case_number })),
        ]}
      />
      <Button label={t('work.save')} loading={busy} onPress={() => void save()} />
      {initial && (
        <Button
          label={t(initial.archived_at ? 'work.restore' : 'work.archive')}
          variant="secondary"
          onPress={() =>
            Alert.alert(t('work.confirm'), t('work.confirmBody'), [
              { text: t('work.cancel'), style: 'cancel' },
              { text: t('work.confirm'), onPress: () => void archive() },
            ])
          }
        />
      )}
    </Screen>
  );
}
