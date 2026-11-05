import { Pressable, View } from 'react-native';
import { Building2, ChevronRight, UserRound } from 'lucide-react-native';
import { useTranslation } from 'react-i18next';
import { AppText } from '../common/AppText';
import { Card } from '../common/Card';
import type { Client } from '../../services/client-api';
import { useTheme } from '../../theme/tokens';

export function ClientCard({ client, onPress }: { client: Client; onPress: () => void }) {
  const { t } = useTranslation(); const theme = useTheme(); const Icon = client.client_type === 'organization' ? Building2 : UserRound;
  return <Pressable accessibilityRole="button" onPress={onPress}><Card style={{ flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16 }}><View style={{ width: 42, height: 42, borderRadius: 21, backgroundColor: theme.colors.input, alignItems: 'center', justifyContent: 'center' }}><Icon size={21} color={theme.colors.accent} /></View><View style={{ flex: 1 }}><AppText style={{ fontWeight: '800' }}>{client.full_name}</AppText>{client.organization_name && <AppText style={{ color: theme.colors.muted, fontSize: 13 }}>{client.organization_name}</AppText>}<AppText style={{ color: theme.colors.muted, fontSize: 13 }}>{t(`clients.${client.client_type}`)} · {client.phone_number}</AppText><AppText style={{ color: theme.colors.muted, fontSize: 13 }}>{client.city}, {client.district}</AppText>{client.is_archived && <AppText style={{ color: theme.colors.accent, fontSize: 12, fontWeight: '700' }}>{t('clients.archived')}</AppText>}</View><ChevronRight size={18} color={theme.colors.muted} /></Card></Pressable>;
}
