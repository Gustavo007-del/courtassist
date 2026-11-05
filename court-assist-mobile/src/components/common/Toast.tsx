import { useEffect } from 'react';
import { Pressable } from 'react-native';
import { useAppStore } from '../../store/app-store';
import { useTheme } from '../../theme/tokens';
import { AppText } from './AppText';

export function Toast() {
  const theme = useTheme();
  const toast = useAppStore((state) => state.toast);
  const clear = useAppStore((state) => state.clearToast);
  useEffect(() => { if (!toast) return; const id = setTimeout(clear, 3500); return () => clearTimeout(id); }, [toast, clear]);
  if (!toast) return null;
  return <Pressable accessibilityRole="alert" onPress={clear} style={{ position: 'absolute', bottom: 88, left: 20, right: 20, backgroundColor: theme.colors.navy, borderRadius: theme.radius.md, padding: 16, ...theme.shadow }}><AppText style={{ color: theme.colors.surface, fontWeight: '600' }}>{toast}</AppText></Pressable>;
}
