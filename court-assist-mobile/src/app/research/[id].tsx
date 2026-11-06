import { useState } from 'react';
import { Alert, Linking } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Notice } from '../../components/common/Notice';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { researchApi } from '../../services/research-api';
import { caseApi } from '../../services/case-api';
import { friendlyError } from '../../utils/errors';
export default function Detail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [caseId, setCaseId] = useState('');
  const q = useQuery({ queryKey: ['research', id], queryFn: () => researchApi.get(id) });
  const cases = useQuery({
    queryKey: ['research-case-options'],
    queryFn: () => caseApi.list({ limit: 100 }),
  });
  async function action(name: string) {
    setBusy(true);
    try {
      await researchApi.action(id, name, name === 'favorite' ? { favorite: !q.data?.favorite } : undefined);
      void qc.invalidateQueries({ queryKey: ['research'] });
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  async function link(remove = false) {
    setBusy(true);
    try {
      if (remove) await researchApi.unlink(caseId, id);
      else await researchApi.link(caseId, id);
      void q.refetch();
      void qc.invalidateQueries({ queryKey: ['case-research'] });
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  async function openSource() {
    try {
      const url = new URL(q.data!.source_url);
      if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password)
        throw Error(t('research.unsafeUrl'));
      await Linking.openURL(url.toString());
    } catch (e) {
      setError(friendlyError(e));
    }
  }
  return (
    <Screen title={q.data?.title ?? t('research.library')} back>
      {error && <Notice message={error} />}{' '}
      {q.isPending ? (
        <LoadingSkeleton />
      ) : q.isError ? (
        <ErrorState message={t('work.error')} retry={() => void q.refetch()} />
      ) : (
        <>
          <AppText>{t(`research.types.${q.data.item_type}`, q.data.item_type)}</AppText>
          <Notice message={t(`research.${q.data.verification_status}`, q.data.verification_status)} />
          <AppText>
            {t('research.origin')}: {t(`research.origins.${q.data.source_status}`, q.data.source_status)}
          </AppText>
          {(
            [
              'citation',
              'court',
              'case_title',
              'case_number',
              'cnr_number',
              'judgment_date',
              'source_name',
              'source_url',
              'accessed_date',
              'act_name',
              'section_number',
              'subject',
              'party_information',
              'page_reference',
              'paragraph_reference',
              'summary',
              'notes',
              'verification_notes',
            ] as const
          ).map((key) =>
            q.data[key] ? (
              <AppText key={key} style={{ marginVertical: 6 }}>
                {t(`research.fields.${key}`)}: {q.data[key]}
              </AppText>
            ) : null,
          )}
          <AppText>{q.data.tags.join(' · ')}</AppText>
          {q.data.full_text && (
            <AppText>
              {t('research.fields.full_text')}: {q.data.full_text}
            </AppText>
          )}
          <Button
            label={t('work.edit')}
            onPress={() => router.push({ pathname: '/research/edit', params: { id } })}
          />
          <Button
            label={(q.data.favorite ? '★ ' : '☆ ') + t('research.favorites')}
            variant="secondary"
            loading={busy}
            onPress={() => void action('favorite')}
          />
          {q.data.source_url && (
            <Button label={t('research.openSource')} variant="secondary" onPress={() => void openSource()} />
          )}{' '}
          {q.data.document_id && (
            <Button
              label={t('research.document')}
              onPress={() =>
                router.push({ pathname: '/documents/[id]', params: { id: q.data.document_id! } })
              }
            />
          )}
          <Button
            label={t('research.upload')}
            variant="secondary"
            onPress={() => router.push({ pathname: '/research/upload', params: { id } })}
          />
          <Button
            label={t('research.metadata')}
            variant="secondary"
            onPress={() => router.push({ pathname: '/research/metadata', params: { id } })}
          />
          <Button
            label={t('research.notes')}
            variant="secondary"
            onPress={() => router.push({ pathname: '/research/notes', params: { itemId: id } })}
          />
          <Button
            label={t('research.addNote')}
            variant="secondary"
            onPress={() => router.push({ pathname: '/research/note-editor', params: { itemId: id } })}
          />
          <AppText>{t('research.linkedCases')}</AppText>
          {q.data.linked_case_ids?.map((value) => (
            <Button
              key={value}
              variant="secondary"
              label={cases.data?.items.find((row) => row.id === value)?.case_number ?? value}
              onPress={() => router.push({ pathname: '/cases/[id]', params: { id: value } })}
            />
          ))}
          <ChoiceChips
            value={caseId}
            onChange={setCaseId}
            options={(cases.data?.items ?? []).map((row) => ({ value: row.id, label: row.case_number }))}
          />
          <Button
            label={t('research.linkCase')}
            disabled={!caseId}
            loading={busy}
            onPress={() => void link()}
          />
          {caseId && q.data.linked_case_ids?.includes(caseId) && (
            <Button
              label={t('research.unlinkCase')}
              variant="secondary"
              loading={busy}
              onPress={() =>
                Alert.alert(t('work.confirm'), t('research.unlinkNotice'), [
                  { text: t('work.cancel'), style: 'cancel' },
                  { text: t('work.confirm'), onPress: () => void link(true) },
                ])
              }
            />
          )}
          <Button
            label={q.data.archived_at ? t('work.restore') : t('work.archive')}
            variant="secondary"
            loading={busy}
            onPress={() =>
              Alert.alert(t('work.confirm'), t('work.confirmBody'), [
                { text: t('work.cancel'), style: 'cancel' },
                {
                  text: t('work.confirm'),
                  onPress: () => void action(q.data.archived_at ? 'restore' : 'archive'),
                },
              ])
            }
          />
        </>
      )}
    </Screen>
  );
}
