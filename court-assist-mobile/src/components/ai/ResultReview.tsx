import { useState } from 'react';
import { Platform } from 'react-native';
import { router } from 'expo-router';
import { File, Paths } from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import { randomUUID } from 'expo-crypto';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { aiApi, aiErrorKey, type Evidence, type Job } from '../../services/ai-api';
import { AppText } from '../common/AppText';
import { Button } from '../common/Button';
import { Card } from '../common/Card';
import { TextField } from '../common/TextField';
import { ContextPicker } from './Controls';

function SourceLink({ source }: { source: Evidence['source'] }) {
  const { t } = useTranslation();
  const id = source.id;
  function open() {
    switch (source.kind) {
      case 'document':
        router.push({ pathname: '/documents/preview', params: { id, versionId: source.version ?? '' } });
        break;
      case 'case': router.push({ pathname: '/cases/[id]', params: { id } }); break;
      case 'diary': router.push({ pathname: '/diary/[id]', params: { id } }); break;
      case 'hearing': router.push({ pathname: '/hearings/[id]', params: { id } }); break;
      case 'research': router.push({ pathname: '/research/[id]', params: { id } }); break;
      case 'task': router.push({ pathname: '/tasks/[id]', params: { id } }); break;
    }
  }
  if (source.kind === 'status' || source.kind === 'timeline') return <AppText>{source.id}</AppText>;
  return <Button label={t('ai.openSource')} variant="text" onPress={open} />;
}

export function ResultReview({ job, refresh }: { job: Job; refresh: () => void }) {
  const { t } = useTranslation();
  const cache = useQueryClient();
  const result = job.result!;
  const items = result.items ?? [];
  const [edited, setEdited] = useState(job.review?.text ?? result.suggestion ?? items.map(item =>
    [item.date ?? (job.kind === 'chronology' || job.kind === 'dates' ? t('ai.noDate') : ''),
      t(`ai.sections.${item.section}`), item.quote, item.source.title, item.source.page && t('ai.page', { number: item.source.page })]
      .filter(Boolean).join(' · ')).join('\n\n'));
  const [eventIndex, setEventIndex] = useState<number>();
  const [caseId, setCaseId] = useState(job.case_id ?? undefined);
  const [caseTitle, setCaseTitle] = useState('');
  const [eventTitle, setEventTitle] = useState('');
  const [eventText, setEventText] = useState('');
  const [eventDate, setEventDate] = useState('');
  const [busy, setBusy] = useState(false);
  const [visibleItems, setVisibleItems] = useState(20);
  const [message, setMessage] = useState('');
  const dates = job.kind === 'dates' || job.kind === 'chronology';
  const diaryApproval = job.kind === 'diary' || (dates && eventIndex !== undefined);
  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setMessage('');
    try {
      await action();
      setMessage(t('ai.saved'));
    } catch (error) {
      setMessage(t(aiErrorKey(error), { defaultValue: t('work.error') }));
    } finally {
      setBusy(false);
    }
  };
  const approveDraft = (mode: 'append' | 'replace') => run(async () => {
    if (!job.draft_revision) return;
    await aiApi.approveDraft(job.id, edited, job.draft_revision, mode);
    await cache.invalidateQueries({ queryKey: ['draft', job.draft_id] });
    await cache.invalidateQueries({ queryKey: ['draft-versions', job.draft_id] });
    refresh();
  });
  return <>
    <Card>
      <AppText style={{ fontWeight: '700' }}>{t('ai.generated')}</AppText>
      {result.insufficient && <AppText>{t('ai.noEvidence')}</AppText>}
      {result.warnings?.map(code => <AppText key={code}>{t(`ai.warnings.${code}`)}</AppText>)}
      {!!result.missing_sections?.length && <AppText>{t('ai.unavailableFields', {
        fields: result.missing_sections.map(section => t(`ai.sections.${section}`)).join(', '),
      })}</AppText>}
      {job.selected_text && <><AppText style={{ fontWeight: '700' }}>{t('ai.originalText')}</AppText><AppText>{job.selected_text}</AppText></>}
      {result.suggestion && <><AppText style={{ fontWeight: '700' }}>{t('ai.suggestion')}</AppText><AppText>{result.suggestion}</AppText></>}
    </Card>
    {items.slice(0, visibleItems).map((item, index) => <Card key={index}>
      <AppText style={{ fontWeight: '700' }}>{t(`ai.sections.${item.section}`)}</AppText>
      <AppText selectable>{item.quote}</AppText>
      {dates && <AppText>{item.date ?? t('ai.noDate')} · {t(`ai.dateStatus.${item.date_status}`)}</AppText>}
      {item.check_other_dates && <AppText>{t('ai.checkDates')}</AppText>}
      <AppText>{item.source.title}
        {item.source.page ? ' · ' + t('ai.page', { number: item.source.page }) : ''}
        {item.source.paragraph ? ' · ' + t('ai.paragraph', { value: item.source.paragraph }) : ''}
        {item.source.reference ? ' · ' + item.source.reference : ''}
      </AppText>
      <SourceLink source={item.source} />
      {dates && (job.approval?.[String(index)] ? <AppText>{t('ai.approved')}</AppText>
        : <Button label={t('ai.reviewEvent')} variant="secondary" onPress={() => {
          setEventIndex(index);
          setEventDate(item.date ?? '');
          setEventTitle(t(`ai.sections.${item.section}`));
          setEventText(item.quote);
        }} />)}
    </Card>)}
    {visibleItems < items.length && <Button label={t('clients.loadMore')} variant="secondary"
      onPress={() => setVisibleItems(count => count + 20)} />}
    {message && <AppText accessibilityLiveRegion="polite">{message}</AppText>}
    {job.kind !== 'ask' && (result.suggestion || items.length > 0 || job.review) && <Card>
      <TextField label={t('ai.reviewText')} multiline value={edited} onChangeText={setEdited} />
      <Button label={t('ai.saveReview')} variant="secondary" loading={busy} disabled={!edited.trim() || edited.length > 30000}
        onPress={() => void run(async () => { await aiApi.review(job.id, edited); refresh(); })} />
      {job.kind === 'chronology' && Platform.OS !== 'web' && <Button label={t('ai.export')} variant="secondary" loading={busy}
        disabled={!job.review || job.review.text !== edited.trim()} onPress={() => void run(async () => {
          if (!await Sharing.isAvailableAsync()) throw new Error('sharing unavailable');
          const file = new File(Paths.cache, `chronology-${randomUUID()}.txt`);
          try {
            file.create();
            file.write(await aiApi.export(job.id));
            await Sharing.shareAsync(file.uri, { mimeType: 'text/plain', dialogTitle: t('ai.export') });
          } finally {
            if (file.exists) file.delete();
          }
        })} />}
      {job.kind === 'draft' && (job.approval ? <>
        <AppText>{t('ai.approved')}</AppText>
        <Button label={t('ai.openDraft')} variant="secondary" onPress={() => router.push({
          pathname: '/practice-tools/draft-editor', params: { id: job.draft_id! },
        })} />
      </> : <>
        <AppText>{t('ai.draftApprovalExplanation')}</AppText>
        <Button label={t('ai.approveReplace')} loading={busy} disabled={!edited.trim() || edited.length > 8000}
          onPress={() => void approveDraft('replace')} />
        <Button label={t('ai.approveAppend')} variant="secondary" loading={busy} disabled={!edited.trim() || edited.length > 8000}
          onPress={() => void approveDraft('append')} />
      </>)}
    </Card>}
    {diaryApproval && <Card>
      <AppText>{t('ai.diaryApprovalExplanation')}</AppText>
      {job.kind === 'diary' && job.approval?.note ? <AppText>{t('ai.approved')}</AppText> : <>
        {job.case_id ? <AppText>{t('ai.linkedCase')}</AppText> : caseId
          ? <Button label={caseTitle} variant="secondary" onPress={() => setCaseId(undefined)} />
          : <ContextPicker only="case" selected={[]} onPick={row => { setCaseId(row.id); setCaseTitle(row.title); }} />}
        <TextField label={t('ai.eventTitle')} value={eventTitle} onChangeText={setEventTitle} />
        <TextField label={t('ai.eventDate')} value={eventDate} onChangeText={setEventDate} />
        {dates && <TextField label={t('ai.reviewText')} multiline value={eventText} onChangeText={setEventText} />}
        <Button label={t('ai.approveDiary')} loading={busy}
          disabled={!caseId || !eventTitle.trim() || !/^\d{4}-\d{2}-\d{2}$/.test(eventDate) || !(dates ? eventText : edited).trim()}
          onPress={() => void run(async () => {
            const record = await aiApi.approveDiary(job.id, {
              case_id: caseId!, title: eventTitle, entry_date: eventDate, text: dates ? eventText : edited, item_index: eventIndex,
            });
            void cache.invalidateQueries({ queryKey: ['case-diary'] });
            refresh();
            router.push({ pathname: '/diary/[id]', params: { id: record.diary_entry_id } });
          })} />
      </>}
    </Card>}
  </>;
}

