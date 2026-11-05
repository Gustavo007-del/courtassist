import { Pressable } from 'react-native';
import { useTranslation } from 'react-i18next';
import { Card } from '../common/Card';
import { AppText } from '../common/AppText';
import { useTheme } from '../../theme/tokens';
import type { Hearing } from '../../services/hearing-api';
export function HearingCard({ item, onPress }: { item: Hearing; onPress: () => void }) { const { t } = useTranslation(); const theme = useTheme(); return <Pressable accessibilityRole="button" onPress={onPress}><Card style={{ gap: 3 }}><AppText style={{ fontWeight: '800' }}>{item.case_title} · {item.case_number}</AppText><AppText style={{ color: theme.colors.muted }}>{item.hearing_date} · {item.hearing_time ? item.hearing_time.slice(0, 5) : t('hearings.timeUnknown')}</AppText><AppText>{item.court_name || t('cases.noCourt')} · {t(`hearings.types.${item.hearing_type}`, item.hearing_type)}</AppText><AppText style={{ color: theme.colors.accent }}>{t(`hearings.statuses.${item.status}`)}</AppText></Card></Pressable>; }
