import { View } from 'react-native';
import { useTranslation } from 'react-i18next';
import { Card } from '../common/Card';
import { AppText } from '../common/AppText';
import { useTheme } from '../../theme/tokens';

export function ProfileInfoCard({ rows }: { rows: { label: string; value?: string | null }[] }) {
  const { t } = useTranslation(); const theme = useTheme();
  return <Card>{rows.map((row, index) => <View key={row.label} style={{ paddingVertical: 9, borderBottomWidth: index === rows.length - 1 ? 0 : 1, borderBottomColor: theme.colors.border }}><AppText style={{ fontSize: 13, color: theme.colors.muted }}>{row.label}</AppText><AppText style={{ marginTop: 3 }}>{row.value || t('profile.notSet')}</AppText></View>)}</Card>;
}
