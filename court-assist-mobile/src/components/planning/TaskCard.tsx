import { Pressable } from 'react-native';
import { useTranslation } from 'react-i18next';
import { AppText } from '../common/AppText';
import { Card } from '../common/Card';
import { useTheme } from '../../theme/tokens';
import type { Task } from '../../services/planning-api';
export function TaskCard({ item, onPress }: { item: Task; onPress: () => void }) { const { t } = useTranslation(); const theme = useTheme(); return <Pressable onPress={onPress}><Card style={{ borderLeftWidth: 4, borderLeftColor: item.is_overdue ? theme.colors.accent : item.priority === 'Urgent' ? theme.colors.navy : theme.colors.border }}><AppText style={{ fontWeight: '800' }}>{item.title}</AppText><AppText>{t(`planning.taskStatuses.${item.status}`)} · {t(`planning.priorities.${item.priority}`)}{item.is_overdue ? ` · ${t('planning.overdue')}` : ''}</AppText>{item.due_date && <AppText>{item.due_date}{item.due_time ? ` · ${item.due_time.slice(0, 5)}` : ''}</AppText>}</Card></Pressable>; }
