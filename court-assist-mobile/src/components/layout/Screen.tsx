import { FlatList, Pressable, RefreshControl, ScrollView, View, type FlatListProps } from 'react-native';
import { router } from 'expo-router';
import { ArrowLeft } from 'lucide-react-native';
import { useTranslation } from 'react-i18next';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTheme } from '../../theme/tokens';
import { SyncIndicator } from '../common/SyncIndicator';
import { AppText } from '../common/AppText';

export function Screen({ title, subtitle, children, refreshing, onRefresh, back = false, record }: { title?: string; subtitle?: string; children: React.ReactNode; refreshing?: boolean; onRefresh?: () => void; back?: boolean; record?: object }) {
  const theme = useTheme();
  return <SafeAreaView style={{ flex: 1, backgroundColor: theme.colors.background }} edges={['top']}><ScrollView keyboardShouldPersistTaps="handled" refreshControl={onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} tintColor={theme.colors.navy} /> : undefined} contentContainerStyle={{ flexGrow: 1, padding: 24, paddingBottom: 40 }}>
    <ScreenHeading title={title} back={back} subtitle={subtitle} />
    <SyncIndicator recordPending={!!record && 'sync_status' in record && record.sync_status === 'pending'} />
    {children}
  </ScrollView></SafeAreaView>;
}

function ScreenHeading({ title, back, subtitle }: { title?: string; back?: boolean; subtitle?: string }) {
  const theme = useTheme();
  const { t } = useTranslation();
  return title ? <View style={{ marginBottom: 28 }}>{back && <Pressable accessibilityRole="button" accessibilityLabel={t('back')} onPress={() => router.back()} style={{ width: 44, height: 44, alignItems: 'center', justifyContent: 'center', marginLeft: -12, marginBottom: 8 }}><ArrowLeft size={23} color={theme.colors.text} /></Pressable>}<View style={{ width: 38, height: 4, backgroundColor: theme.colors.accent, borderRadius: 2, marginBottom: 18 }} /><AppText style={{ fontSize: 30, fontWeight: '800', lineHeight: 37 }}>{title}</AppText>{subtitle && <AppText style={{ color: theme.colors.muted, marginTop: 8 }}>{subtitle}</AppText>}</View> : null;
}

export function ListScreen<Item extends { id: string }>({ title, back, filters, ...list }: FlatListProps<Item> & {
  title: string; back?: boolean; filters?: React.ReactNode;
}) {
  const theme = useTheme();
  return <SafeAreaView style={{ flex: 1, backgroundColor: theme.colors.background }} edges={['top']}>
    <FlatList {...list} keyboardShouldPersistTaps="handled" contentContainerStyle={{ flexGrow: 1, padding: 24, paddingBottom: 40, gap: 10 }}
      keyExtractor={item => item.id} ListHeaderComponent={<><ScreenHeading title={title} back={back} /><SyncIndicator />{filters}</>} />
  </SafeAreaView>;
}
