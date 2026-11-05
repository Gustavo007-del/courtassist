import { Image, View } from 'react-native';
import { UserRound } from 'lucide-react-native';
import { useAuthStore } from '../../store/auth-store';
import { useTheme } from '../../theme/tokens';
import { profileApi } from '../../services/profile-api';

export function Avatar({ imageKey, size = 56, localUri }: { imageKey?: string | null; size?: number; localUri?: string | null }) {
  const theme = useTheme();
  const token = useAuthStore((state) => state.accessToken);
  const source = localUri ? { uri: localUri } : imageKey && token ? { uri: profileApi.imageUrl('profile', imageKey), headers: { Authorization: `Bearer ${token}` } } : null;
  return <View style={{ width: size, height: size, borderRadius: size / 2, overflow: 'hidden', backgroundColor: theme.colors.input, borderColor: theme.colors.border, borderWidth: 1, alignItems: 'center', justifyContent: 'center' }}>
    {source ? <Image source={source} style={{ width: size, height: size }} accessibilityIgnoresInvertColors /> : <UserRound size={size * 0.48} color={theme.colors.muted} />}
  </View>;
}
