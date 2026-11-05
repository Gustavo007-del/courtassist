import { Alert, Image, View } from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { useTranslation } from 'react-i18next';
import { Avatar } from '../common/Avatar';
import { Button } from '../common/Button';
import { AppText } from '../common/AppText';
import { useAuthStore } from '../../store/auth-store';
import { useTheme } from '../../theme/tokens';
import { profileApi } from '../../services/profile-api';

export type PickedImage = { uri: string; contentType: 'image/jpeg' | 'image/png' | 'image/webp' };
export function ImagePickerField({ purpose, imageKey, selected, onPick }: { purpose: 'profile' | 'signature'; imageKey?: string | null; selected: PickedImage | null; onPick: (image: PickedImage) => void }) {
  const { t } = useTranslation(); const theme = useTheme(); const token = useAuthStore((state) => state.accessToken);
  const pick = async (camera: boolean) => {
    if (camera) { const permission = await ImagePicker.requestCameraPermissionsAsync(); if (!permission.granted) return Alert.alert(t('profile2.permissionRequired')); }
    const result = camera
      ? await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], allowsEditing: true, quality: 0.85, aspect: purpose === 'profile' ? [1, 1] : [3, 1] })
      : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], allowsEditing: true, quality: 0.85, aspect: purpose === 'profile' ? [1, 1] : [3, 1] });
    if (result.canceled || !result.assets?.length) return;
    const asset = result.assets[0];
    if (asset.fileSize && asset.fileSize > 5 * 1024 * 1024) return Alert.alert(t('profile2.photoTooLarge'));
    const contentType = asset.mimeType === 'image/png' || asset.mimeType === 'image/webp' || asset.mimeType === 'image/jpeg'
      ? asset.mimeType : asset.uri.toLowerCase().endsWith('.png') ? 'image/png' : asset.uri.toLowerCase().endsWith('.webp') ? 'image/webp' : asset.uri.toLowerCase().match(/\.jpe?g$/) ? 'image/jpeg' : null;
    if (!contentType) return Alert.alert(t('profile2.photoType'));
    onPick({ uri: asset.uri, contentType });
  };
  const source = selected ? { uri: selected.uri } : imageKey && token ? { uri: profileApi.imageUrl(purpose, imageKey), headers: { Authorization: `Bearer ${token}` } } : null;
  return <View style={{ paddingVertical: 12, gap: 10 }}>
    <AppText style={{ fontWeight: '700' }}>{t(purpose === 'profile' ? 'profile2.photo' : 'profile2.signature')}</AppText>
    {purpose === 'profile' ? <Avatar imageKey={imageKey} localUri={selected?.uri} size={82} /> : source ? <Image source={source} style={{ height: 88, width: '100%', resizeMode: 'contain', borderRadius: theme.radius.md, backgroundColor: theme.colors.input }} /> : <AppText style={{ color: theme.colors.muted }}>{t('profile2.none')}</AppText>}
    <View style={{ flexDirection: 'row', gap: 10 }}><View style={{ flex: 1 }}><Button label={t('profile2.chooseGallery')} variant="secondary" onPress={() => { void pick(false); }} /></View><View style={{ flex: 1 }}><Button label={t('profile2.takePhoto')} variant="secondary" onPress={() => { void pick(true); }} /></View></View>
  </View>;
}
