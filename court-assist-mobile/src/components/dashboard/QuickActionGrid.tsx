import { Alert, Pressable, View } from 'react-native';
import { router, type Href } from 'expo-router';
import { BriefcaseBusiness, CalendarPlus, CalendarClock, ClipboardPlus, ContactRound, NotebookPen, Receipt, ScanLine, type LucideIcon, FileText } from 'lucide-react-native';
import { useTranslation } from 'react-i18next';
import { AppText } from '../common/AppText';
import { useTheme } from '../../theme/tokens';

const actions: { key: string; icon: LucideIcon; route?: Href }[] = [
  { key: 'addCase', icon: BriefcaseBusiness, route: '/cases/add' },
  { key: 'addClient', icon: ContactRound, route: '/clients/add' },
  { key: 'addHearing', icon: CalendarPlus, route: '/hearings/add' },
  { key: 'scanDocument', icon: ScanLine, route: '/(tabs)/scanner' },
  { key: 'createTask', icon: ClipboardPlus, route: '/tasks/add' },
  { key: 'addDiary', icon: NotebookPen },
  { key: 'addAppointment', icon: CalendarClock, route: '/appointments/add' },
  { key: 'recordPayment', icon: Receipt, route: { pathname: '/finance/form', params: { kind: 'payments' } } },
  { key: 'createDraft', icon: FileText, route: '/drafting/create' },
  { key: 'finance', icon: Receipt, route: '/finance' },
  { key: 'research', icon: FileText, route: '/research' },
  { key: 'practiceTools', icon: FileText, route: '/practice-tools' },
];

export function QuickActionGrid() {
  const { t } = useTranslation(); const theme = useTheme();
  return <View style={{ flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between', rowGap: 10 }}>
    {actions.map((action) => <Pressable key={action.key} accessibilityRole="button" onPress={() => action.route ? router.push(action.route) : Alert.alert(t('dashboard.futurePhase'), t('dashboard.futureDetail'))} style={({ pressed }) => ({ width: '48%', minHeight: 76, padding: 14, borderRadius: theme.radius.md, backgroundColor: theme.colors.surface, borderWidth: 1, borderColor: theme.colors.border, opacity: pressed ? 0.75 : 1, flexDirection: 'row', alignItems: 'center', gap: 10 })}>
      <action.icon size={21} color={theme.colors.accent} /><AppText style={{ fontSize: 13, lineHeight: 17, fontWeight: '700', flex: 1 }}>{t(`dashboard.actions.${action.key}`)}</AppText>
    </Pressable>)}
  </View>;
}
