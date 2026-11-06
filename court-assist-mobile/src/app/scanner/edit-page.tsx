import { useState } from 'react';
import { Image, View } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import * as ImageManipulator from 'expo-image-manipulator';
import { File } from 'expo-file-system';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { EmptyState } from '../../components/common/EmptyState';
import { Notice } from '../../components/common/Notice';
import { TextField } from '../../components/common/TextField';
import { Screen } from '../../components/layout/Screen';
import { useScannerStore } from '../../features/scanner/store';
import { persistPage } from '../../features/scanner/storage';
import { scannerId } from '../../features/scanner/types';
import { friendlyError } from '../../utils/errors';

export default function EditScanPage() {
  const { id } = useLocalSearchParams<{ id: string }>(); const { t } = useTranslation(); const page = useScannerStore((state) => state.pages.find((item) => item.id === id)); const userId = useScannerStore((state) => state.userId); const update = useScannerStore((state) => state.update); const [rotation, setRotation] = useState(page?.rotation ?? 0); const [left, setLeft] = useState('0'); const [top, setTop] = useState('0'); const [right, setRight] = useState('0'); const [bottom, setBottom] = useState('0'); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  if (!page) return <Screen title={t('scanner.editPage')} back><EmptyState title={t('scanner.noPages')} body={t('scanner.noPagesDetail')} /></Screen>;
  const apply = async () => { if (!userId || busy) return; const [l, topCrop, r, b] = [left, top, right, bottom].map(Number); if ([l, topCrop, r, b].some((value) => !Number.isFinite(value) || value < 0) || l + r >= page.originalWidth || topCrop + b >= page.originalHeight) { setError(t('scanner.invalidCrop')); return; } setBusy(true); setError(null); try { const actions: ImageManipulator.Action[] = []; if (l + topCrop + r + b > 0) actions.push({ crop: { originX: l, originY: topCrop, width: page.originalWidth - l - r, height: page.originalHeight - topCrop - b } }); if (rotation) actions.push({ rotate: rotation }); const result = await ImageManipulator.manipulateAsync(page.originalUri, actions, { format: ImageManipulator.SaveFormat.JPEG, compress: 0.96 }); const saved = await persistPage(userId, result.uri, scannerId()); const temporary = new File(result.uri); if (temporary.exists) temporary.delete(); const previous = page.uri; await update(page.id, { uri: saved, width: result.width, height: result.height, rotation, crop: { originX: l, originY: topCrop, width: page.originalWidth - l - r, height: page.originalHeight - topCrop - b } }); if (previous !== page.originalUri) { const old = new File(previous); if (old.exists) old.delete(); } router.back(); } catch (caught) { setError(friendlyError(caught)); } finally { setBusy(false); } };
  const reset = async () => { setBusy(true); setError(null); try { const previous = page.uri; await update(page.id, { uri: page.originalUri, width: page.originalWidth, height: page.originalHeight, rotation: 0, crop: undefined }); if (previous !== page.originalUri) { const old = new File(previous); if (old.exists) old.delete(); } router.back(); } catch (caught) { setError(friendlyError(caught)); } finally { setBusy(false); } };
  return <Screen title={t('scanner.editPage')} subtitle={t('scanner.manualCropNote')} back>{error && <Notice message={error} />}<Image source={{ uri: page.uri }} style={{ width: '100%', height: 360 }} resizeMode="contain" /><AppText>{page.width} × {page.height}</AppText><View style={{ flexDirection: 'row', gap: 8 }}><View style={{ flex: 1 }}><Button label={t('scanner.rotateLeft')} variant="secondary" onPress={() => setRotation((rotation + 270) % 360)} /></View><View style={{ flex: 1 }}><Button label={t('scanner.rotateRight')} variant="secondary" onPress={() => setRotation((rotation + 90) % 360)} /></View></View><TextField label={t('scanner.cropLeft')} value={left} onChangeText={setLeft} keyboardType="numeric" /><TextField label={t('scanner.cropTop')} value={top} onChangeText={setTop} keyboardType="numeric" /><TextField label={t('scanner.cropRight')} value={right} onChangeText={setRight} keyboardType="numeric" /><TextField label={t('scanner.cropBottom')} value={bottom} onChangeText={setBottom} keyboardType="numeric" /><Button label={t('scanner.applyEdits')} loading={busy} onPress={() => { void apply(); }} /><Button label={t('scanner.reset')} variant="secondary" onPress={() => { void reset(); }} /></Screen>;
}
