import { useRef, useState } from 'react';
import { Platform, View } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { File } from 'expo-file-system';
import { useTranslation } from 'react-i18next';
import { AppText } from '../common/AppText';
import { Button } from '../common/Button';
import { ErrorState } from '../common/ErrorState';
import { EmptyState } from '../common/EmptyState';
import { useScannerStore } from '../../features/scanner/store';
import { friendlyError } from '../../utils/errors';

export function ScannerCamera({ retakeId, onDone }: { retakeId?: string; onDone: () => void }) {
  const { t } = useTranslation(); const camera = useRef<CameraView>(null); const [permission, requestPermission] = useCameraPermissions(); const [ready, setReady] = useState(false); const [flash, setFlash] = useState<'off' | 'on' | 'auto'>('off'); const [torch, setTorch] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null); const pages = useScannerStore((state) => state.pages); const add = useScannerStore((state) => state.add); const replace = useScannerStore((state) => state.replace);
  const capture = async () => { if (!ready || busy) return; setBusy(true); setError(null); try { const photo = await camera.current?.takePictureAsync({ quality: 1, skipProcessing: false }); if (!photo) throw new Error(t('scanner.captureFailed')); if (retakeId) { await replace(retakeId, photo.uri, photo.width, photo.height); onDone(); } else await add(photo.uri, photo.width, photo.height); const temporary = new File(photo.uri); if (temporary.exists) temporary.delete(); } catch (caught) { setError(friendlyError(caught)); } finally { setBusy(false); } };
  if (Platform.OS === 'web') return <EmptyState title={t('scanner.nativeUnavailable')} body={t('scanner.nativeNote')} />;
  if (!permission) return <AppText>{t('scanner.loadingCamera')}</AppText>;
  if (!permission.granted) return <ErrorState message={t('scanner.cameraPermission')} retry={() => { void requestPermission(); }} />;
  return <View style={{ gap: 12, flex: 1 }}>{error && <AppText>{error}</AppText>}<CameraView ref={camera} style={{ height: 430, borderRadius: 14, overflow: 'hidden' }} facing="back" flash={flash} enableTorch={torch} onCameraReady={() => setReady(true)} /><AppText>{t('scanner.pages')}: {pages.length}</AppText><View style={{ flexDirection: 'row', gap: 8 }}><View style={{ flex: 1 }}><Button label={t('scanner.flash')} variant="secondary" onPress={() => setFlash(flash === 'off' ? 'auto' : flash === 'auto' ? 'on' : 'off')} /></View><View style={{ flex: 1 }}><Button label={t('scanner.torch')} variant="secondary" onPress={() => setTorch(!torch)} /></View></View><Button label={retakeId ? t('scanner.retake') : t('scanner.capture')} loading={busy} disabled={!ready} onPress={() => { void capture(); }} /><Button label={t('scanner.review')} variant="secondary" onPress={onDone} /></View>;
}
