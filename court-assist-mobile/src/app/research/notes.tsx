import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { TextField } from '../../components/common/TextField';
import { Button } from '../../components/common/Button';
import { EmptyState } from '../../components/common/EmptyState';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { researchApi } from '../../services/research-api';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { AppText } from '../../components/common/AppText';
export default function Notes() {
  const { itemId = '', caseId = '' } = useLocalSearchParams<{ itemId?: string; caseId?: string }>();
  const { t } = useTranslation();
  const [q, setQ] = useState('');
  const [archived, setArchived] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [offset, setOffset] = useState(0);
  const [tag, setTag] = useState('');
  const tags = useQuery({ queryKey: ['research-tags'], queryFn: () => researchApi.tags() });
  const query = useQuery({
    queryKey: ['research-notes', q, itemId, caseId, archived, pinned, offset, tag],
    queryFn: () =>
      researchApi.notes({
        q,
        tag,
        item_id: itemId,
        case_id: caseId,
        archived: String(archived),
        pinned: pinned ? 'true' : '',
        offset: String(offset),
      }),
  });
  return (
    <Screen
      title={t('research.notes')}
      subtitle={t('research.analysisNotice')}
      back
      onRefresh={() => void query.refetch()}
      refreshing={query.isRefetching}
    >
      <Button
        label={t('research.addNote')}
        onPress={() => router.push({ pathname: '/research/note-editor', params: { itemId, caseId } })}
      />
      <TextField
        label={t('work.search')}
        value={q}
        onChangeText={(value) => {
          setQ(value);
          setOffset(0);
        }}
      />
      <AppText>{t('research.tags')}</AppText>
      <ChoiceChips
        value={tag}
        onChange={(value) => {
          setTag(value);
          setOffset(0);
        }}
        options={[
          { value: '', label: t('planning.all') },
          ...(tags.data ?? []).map((row) => ({ value: row.name, label: row.name })),
        ]}
      />
      <Button
        label={(pinned ? '★ ' : '☆ ') + t('research.pinned')}
        variant="secondary"
        onPress={() => {
          setPinned(!pinned);
          setOffset(0);
        }}
      />
      <Button
        label={archived ? t('research.notes') : t('work.archived')}
        variant="secondary"
        onPress={() => {
          setArchived(!archived);
          setOffset(0);
        }}
      />
      {query.isPending ? (
        <LoadingSkeleton />
      ) : query.isError ? (
        <ErrorState message={t('work.error')} retry={() => void query.refetch()} />
      ) : query.data.items.length ? (
        query.data.items.map((note) => (
          <Button
            key={note.id}
            variant="secondary"
            label={(note.pinned ? '★ ' : '') + note.title}
            onPress={() => router.push({ pathname: '/research/note-editor', params: { id: note.id } })}
          />
        ))
      ) : (
        <EmptyState title={t('work.empty')} body={t('research.empty')} />
      )}{' '}
      {offset > 0 && <Button label="←" variant="secondary" onPress={() => setOffset(offset - 30)} />}{' '}
      {query.data && offset + 30 < query.data.total && (
        <Button label="→" variant="secondary" onPress={() => setOffset(offset + 30)} />
      )}
    </Screen>
  );
}
