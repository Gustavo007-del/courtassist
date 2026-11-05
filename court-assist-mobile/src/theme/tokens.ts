import { useColorScheme } from 'react-native';
import { useThemeStore } from '../store/theme-store';

const common = {
  spacing: { xs: 4, sm: 8, md: 16, lg: 24, xl: 32, xxl: 48 },
  radius: { sm: 8, md: 14, lg: 22 },
  type: { title: 30, heading: 22, body: 16, caption: 13 },
  shadow: { elevation: 2, shadowOpacity: 0.06, shadowRadius: 12, shadowOffset: { width: 0, height: 4 } },
};

export const light = { ...common, colors: { background: '#F7F8FA', surface: '#FFFFFF', navy: '#12263A', accent: '#B39562', text: '#182B3E', muted: '#667788', border: '#E2E7EC', danger: '#B6373A', success: '#176C55', input: '#F2F5F7' } };
export const dark = { ...common, colors: { background: '#0F1B28', surface: '#192B3B', navy: '#DCE7F1', accent: '#C7AA76', text: '#F4F7F9', muted: '#A6B7C4', border: '#334757', danger: '#FF8F92', success: '#77C5A7', input: '#223648' } };
export type Theme = typeof light;
export const useTheme = (): Theme => {
  const system = useColorScheme();
  const mode = useThemeStore((state) => state.mode);
  return (mode === 'dark' || (mode === 'system' && system === 'dark')) ? dark : light;
};
