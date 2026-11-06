import { Fragment, useState } from 'react';
import { Alert } from 'react-native';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { TextField } from '../../components/common/TextField';
import { Button } from '../../components/common/Button';
import { AppText } from '../../components/common/AppText';
import { Notice } from '../../components/common/Notice';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { researchApi } from '../../services/research-api';
import { friendlyError } from '../../utils/errors';
export default function Tags() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [q, setQ] = useState('');
  const [name, setName] = useState('');
  const [id, setId] = useState<string>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const tags = useQuery({ queryKey: ['research-tags', q], queryFn: () => researchApi.tags(q) });
  async function save() {
    setBusy(true);
    try {
      await researchApi.saveTag(id, name);
      setName('');
      setId(undefined);
      setError('');
      void qc.invalidateQueries({ queryKey: ['research-tags'] });
      void qc.invalidateQueries({ queryKey: ['research'] });
      void qc.invalidateQueries({ queryKey: ['research-notes'] });
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  async function remove(value: string) {
    try {
      await researchApi.deleteTag(value);
      void qc.invalidateQueries({ queryKey: ['research-tags'] });
    } catch (e) {
      setError(friendlyError(e));
    }
  }
  return (
    <Screen title={t('research.tags')} back>
      {error && <Notice message={error} />}
      <TextField label={t('work.search')} value={q} onChangeText={setQ} />
      <TextField label={t('research.tagName')} value={name} onChangeText={setName} />
      <Button
        label={t(id ? 'work.save' : 'research.addTag')}
        disabled={!name.trim()}
        loading={busy}
        onPress={() => void save()}
      />
      {id && (
        <Button
          label={t('work.cancel')}
          variant="secondary"
          onPress={() => {
            setId(undefined);
            setName('');
          }}
        />
      )}
      {tags.isPending ? (
        <LoadingSkeleton />
      ) : tags.isError ? (
        <ErrorState message={t('work.error')} retry={() => void tags.refetch()} />
      ) : (
        tags.data.map((tag) => (
          <Fragment key={tag.id}>
            <AppText key={tag.id + '-name'}>{tag.name}</AppText>
            <Button
              key={tag.id}
              label={t('work.edit')}
              variant="secondary"
              onPress={() => {
                setId(tag.id);
                setName(tag.name);
              }}
            />
            <Button
              key={tag.id + '-delete'}
              label={t('research.deleteUnused')}
              variant="secondary"
              onPress={() =>
                Alert.alert(t('work.confirm'), t('research.unusedOnly'), [
                  { text: t('work.cancel'), style: 'cancel' },
                  { text: t('work.confirm'), onPress: () => void remove(tag.id) },
                ])
              }
            />
          </Fragment>
        ))
      )}
    </Screen>
  );
}
