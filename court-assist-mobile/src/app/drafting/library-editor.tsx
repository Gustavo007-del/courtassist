import { useState } from 'react';
import { Alert } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { TextField } from '../../components/common/TextField';
import { Button } from '../../components/common/Button';
import { Notice } from '../../components/common/Notice';
import { AppText } from '../../components/common/AppText';
import { RichEditor } from '../../components/drafting/RichEditor';
import { draftingApi, type LibraryKind, type LibraryRecord } from '../../services/drafting-api';
import { apiRequest } from '../../services/api';
import { friendlyError } from '../../utils/errors';
export default function LibraryEditor() {
  const { kind = 'draft-templates', id } = useLocalSearchParams<{ kind: LibraryKind; id?: string }>();
  const { t } = useTranslation();
  const q = useQuery({
    queryKey: ['library-item', kind, id],
    queryFn: () => draftingApi.libraryGet(kind, id!),
    enabled: !!id,
  });
  return id && !q.data ? (
    <Screen title={t('work.templates')} back>
      <AppText>{q.isError ? t('work.error') : t('work.saving')}</AppText>
    </Screen>
  ) : (
    <LibraryForm key={id ?? 'new'} initial={q.data} kind={kind} />
  );
}
function LibraryForm({ initial, kind }: { initial?: LibraryRecord; kind: LibraryKind }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [name, setName] = useState(initial?.name ?? initial?.title ?? '');
  const [category, setCategory] = useState(initial?.category ?? 'General');
  const [content, setContent] = useState(initial?.content ?? '');
  const [preview, setPreview] = useState(!!initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const builtIn = initial?.built_in || initial?.user_id === null;
  async function save() {
    if (!name.trim()) {
      setError(t('work.invalid'));
      return;
    }
    setBusy(true);
    try {
      await draftingApi.librarySave(kind, initial?.id, {
        [kind === 'draft-templates' ? 'name' : 'title']: name,
        category,
        content,
      });
      void qc.invalidateQueries({ queryKey: ['draft-library'] });
      void qc.invalidateQueries({ queryKey: ['draft-clause-options'] });
      router.back();
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  async function mutate(action: 'duplicate' | 'delete') {
    try {
      await apiRequest(`/${kind}/${initial?.id}${action === 'duplicate' ? '/duplicate' : ''}`, {
        method: action === 'duplicate' ? 'POST' : 'DELETE',
      });
      void qc.invalidateQueries({ queryKey: ['draft-library'] });
      router.back();
    } catch (e) {
      setError(friendlyError(e));
    }
  }
  return (
    <Screen title={t(kind === 'draft-templates' ? 'work.templates' : 'work.clauses')} back>
      {error && <Notice message={error} />} {builtIn && <Notice message={t('work.builtIn')} />}
      <TextField label={t('work.name')} value={name} onChangeText={setName} />
      <TextField label={t('work.category')} value={category} onChangeText={setCategory} />
      <Button
        label={preview ? t('work.edit') : t('work.preview')}
        variant="secondary"
        onPress={() => setPreview(!preview)}
      />
      <RichEditor
        key={String(preview)}
        initialHtml={content}
        onChange={setContent}
        preview={preview || builtIn}
      />
      {!builtIn && <Button label={t('work.save')} loading={busy} onPress={() => void save()} />}{' '}
      {initial && kind === 'draft-templates' && (
        <>
          <Button
            label={t('work.useTemplate')}
            onPress={() => router.push({ pathname: '/drafting/create', params: { templateId: initial.id } })}
          />
          <Button label={t('work.duplicate')} variant="secondary" onPress={() => void mutate('duplicate')} />
        </>
      )}{' '}
      {initial && !builtIn && (
        <Button
          label={t('work.archive')}
          variant="secondary"
          onPress={() =>
            Alert.alert(t('work.confirm'), t('work.confirmBody'), [
              { text: t('work.cancel'), style: 'cancel' },
              { text: t('work.confirm'), onPress: () => void mutate('delete') },
            ])
          }
        />
      )}
    </Screen>
  );
}
