import { Pressable, View } from 'react-native';
import { useTranslation } from 'react-i18next';
import { Card } from '../common/Card';
import { AppText } from '../common/AppText';
import { useTheme } from '../../theme/tokens';
import type { CaseRecord } from '../../services/case-api';

export function CaseCard({ item, onPress }: { item: CaseRecord; onPress: () => void }) {
  const { t } = useTranslation(); const theme = useTheme();
  return <Pressable accessibilityRole="button" onPress={onPress}><Card style={{ gap: 5 }}><AppText style={{ fontWeight: '800', fontSize: 17 }}>{item.case_title}</AppText><AppText style={{ color: theme.colors.muted }}>{item.case_number}{item.cnr_number ? ` · ${item.cnr_number}` : ''}</AppText><AppText style={{ color: theme.colors.muted, fontSize: 13 }}>{item.court_name || t('cases.noCourt')}{item.primary_client_name ? ` · ${item.primary_client_name}` : ''}</AppText><View style={{ flexDirection: 'row', gap: 10 }}><AppText style={{ color: theme.colors.accent, fontSize: 13 }}>{t(`cases.categories.${item.case_category}`, item.case_category)}</AppText><AppText style={{ color: theme.colors.success, fontSize: 13 }}>{t(`cases.statuses.${item.current_status}`)}</AppText><AppText style={{ color: item.priority === 'Urgent' ? theme.colors.danger : theme.colors.muted, fontSize: 13 }}>{t(`cases.priorities.${item.priority}`)}</AppText></View></Card></Pressable>;
}
