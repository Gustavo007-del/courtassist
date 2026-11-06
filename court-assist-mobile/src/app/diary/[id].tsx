import { useState } from 'react';
import { Alert, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { ErrorState } from '../../components/common/ErrorState';
import { LoadingSkeleton } from '../../components/common/LoadingSkeleton';
import { Notice } from '../../components/common/Notice';
import { SectionHeader } from '../../components/common/SectionHeader';
import { Screen } from '../../components/layout/Screen';
import { diaryApi } from '../../services/diary-api';
import { useTheme } from '../../theme/tokens';
import { friendlyError } from '../../utils/errors';

const sections = ['content', 'proceedings_summary', 'judge_directions', 'arguments_summary', 'evidence_notes', 'witness_notes', 'observations', 'next_action'] as const;
export default function DiaryDetail() {
  const { id } = useLocalSearchParams<{ id: string }>(); const { t } = useTranslation(); const theme = useTheme(); const cache = useQueryClient(); const [error, setError] = useState<string | null>(null);
  const query = useQuery({ queryKey: ['diary-entry', id], queryFn: () => diaryApi.get(id), enabled: !!id }); const item = query.data;
  const refresh = async () => { await Promise.all([cache.invalidateQueries({ queryKey: ['diary-entry', id] }), cache.invalidateQueries({ queryKey: ['diary'] }), cache.invalidateQueries({ queryKey: ['case-diary'] }), cache.invalidateQueries({ queryKey: ['case-timeline'] })]); };
  const action = async (fn: () => Promise<unknown>) => { try { setError(null); await fn(); await refresh(); } catch (caught) { setError(friendlyError(caught)); } };
  return <Screen record={item} title={item?.title ?? t('diary.title')} subtitle={t('diary.privateLabel')} back>{query.isPending ? <LoadingSkeleton /> : query.isError || !item ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : <>{error && <Notice message={error} />}<Card><AppText>{item.entry_date} · {t(`diary.categories.${item.entry_type}`, item.entry_type)}</AppText><AppText style={{ color: theme.colors.muted }}>{item.case_title} · {item.case_number}</AppText><AppText>{item.is_important ? `★ ${t('diary.important')}` : ''} {item.is_pinned ? `📌 ${t('diary.pinned')}` : ''}</AppText></Card><View style={{ gap: 8, marginTop: 12 }}><Button label={t('ai.kinds.diary')} variant="secondary" onPress={() => router.push({ pathname: '/ai/request', params: { mode: 'diary', entryId: id, caseId: item.case_id } })} /><Button label={t('diary.edit')} onPress={() => router.push({ pathname: '/diary/edit/[id]', params: { id } })} /><Button label={t(item.is_pinned ? 'diary.unpin' : 'diary.pin')} variant="secondary" onPress={() => { void action(() => diaryApi.pin(id, !item.is_pinned)); }} /><Button label={t(item.is_important ? 'diary.unmarkImportant' : 'diary.markImportant')} variant="secondary" onPress={() => { void action(() => diaryApi.important(id, !item.is_important)); }} /><Button label={t('diary.openCase')} variant="secondary" onPress={() => router.push({ pathname: '/cases/[id]', params: { id: item.case_id } })} />{item.hearing_id && <Button label={t('diary.openHearing')} variant="secondary" onPress={() => router.push({ pathname: '/hearings/[id]', params: { id: item.hearing_id! } })} />}</View>{sections.map((key) => item[key] ? <View key={key}><SectionHeader title={t(`diary.fields.${key}`)} /><Card><AppText>{item[key]}</AppText></Card></View> : null)}{item.follow_up_date && <><SectionHeader title={t('diary.followUpDate')} /><Card><AppText>{item.follow_up_date}</AppText></Card></>}<View style={{ marginTop: 24 }}><Button label={t('diary.delete')} variant="text" onPress={() => Alert.alert(t('diary.delete'), t('diary.deleteConfirm'), [{ text: t('cancel'), style: 'cancel' }, { text: t('diary.delete'), style: 'destructive', onPress: () => { void action(async () => { await diaryApi.remove(id); router.replace({ pathname: '/diary', params: { caseId: item.case_id } }); }); } }])} /></View></>}</Screen>;
}
