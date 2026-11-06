import { Pressable, View } from 'react-native';
import { useTranslation } from 'react-i18next';
import { Card } from '../common/Card';
import { AppText } from '../common/AppText';
import { useTheme } from '../../theme/tokens';
import type { DiaryEntry } from '../../services/diary-api';

export function DiaryEntryCard({ item, onPress }: { item: DiaryEntry; onPress: () => void }) {
  const { t } = useTranslation(); const theme = useTheme();
  return <Pressable onPress={onPress} accessibilityRole="button"><Card style={{ marginBottom: 10 }}><View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: 10 }}><AppText style={{ fontWeight: '800', flex: 1 }}>{item.title}</AppText><AppText style={{ color: theme.colors.accent }}>{item.is_pinned ? '📌' : ''}{item.is_important ? ' ★' : ''}</AppText></View><AppText style={{ color: theme.colors.muted }}>{item.entry_date} · {t(`diary.categories.${item.entry_type}`, item.entry_type)}</AppText><AppText>{item.case_title} · {item.case_number}</AppText>{item.hearing_id && <AppText style={{ color: theme.colors.muted }}>{t('diary.relatedHearing')}: {item.hearing_date}</AppText>}</Card></Pressable>;
}
