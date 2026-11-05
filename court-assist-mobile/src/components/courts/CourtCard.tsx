import { Pressable, View } from 'react-native';
import { ChevronRight, Landmark, Star } from 'lucide-react-native';
import { useTranslation } from 'react-i18next';
import { AppText } from '../common/AppText';
import { Card } from '../common/Card';
import type { Court } from '../../services/court-api';
import { useTheme } from '../../theme/tokens';

export function CourtCard({ court, onPress }: { court: Court; onPress: () => void }) {
  const { t } = useTranslation(); const theme = useTheme();
  return <Pressable accessibilityRole="button" onPress={onPress}><Card style={{ flexDirection: 'row', alignItems: 'center', gap: 13, padding: 16 }}><Landmark size={23} color={theme.colors.accent} /><View style={{ flex: 1 }}><View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}><AppText style={{ fontWeight: '800', flexShrink: 1 }}>{court.name}</AppText>{court.is_favorite && <Star size={14} fill={theme.colors.accent} color={theme.colors.accent} />}</View><AppText style={{ color: theme.colors.muted, fontSize: 13 }}>{t(`courts.types.${court.court_type}`, court.court_type)} · {court.district}</AppText><AppText style={{ color: theme.colors.muted, fontSize: 13 }} numberOfLines={2}>{court.address}</AppText><AppText style={{ color: court.record_scope === 'shared' ? theme.colors.success : theme.colors.accent, fontSize: 12, fontWeight: '700' }}>{t(`courts.${court.record_scope}`)}</AppText></View><ChevronRight size={18} color={theme.colors.muted} /></Card></Pressable>;
}
