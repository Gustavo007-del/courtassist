import { useRef, useState } from 'react';
import { View } from 'react-native';
import { router } from 'expo-router';
import Svg, { Path } from 'react-native-svg';
import { captureRef } from 'react-native-view-shot';
import { File } from 'expo-file-system';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Notice } from '../../components/common/Notice';
import { Screen } from '../../components/layout/Screen';
import { useScannerStore } from '../../features/scanner/store';
import { persistSignature } from '../../features/scanner/storage';
import { scannerId } from '../../features/scanner/types';
import { useAuthStore } from '../../store/auth-store';
import { friendlyError } from '../../utils/errors';

export default function SignatureCanvas() {
  const { t } = useTranslation(); const ref = useRef<React.ElementRef<typeof View>>(null); const user = useAuthStore((state) => state.user); const [strokes, setStrokes] = useState<string[]>([]); const [current, setCurrent] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null); const setSignature = useScannerStore((state) => state.setSignature);
  const save = async () => { if (!strokes.length || !ref.current || !user) return; setBusy(true); try { const temporary = await captureRef(ref.current, { format: 'png', quality: 1 }); const saved = await persistSignature(user.id, temporary, scannerId()); const old = useScannerStore.getState().signatureUri; setSignature(saved); if (old) { const file = new File(old); if (file.exists) file.delete(); } router.back(); } catch (caught) { setError(friendlyError(caught)); } finally { setBusy(false); } };
  return <Screen title={t('scanner.signature')} subtitle={t('scanner.signatureNote')} back>{error && <Notice message={error} />}<View ref={ref} collapsable={false} style={{ width: '100%', height: 280, backgroundColor: '#FFFFFF', borderWidth: 1, borderColor: '#CCCCCC' }} onTouchStart={(event) => { const { locationX, locationY } = event.nativeEvent; setCurrent(`M ${locationX} ${locationY}`); }} onTouchMove={(event) => { const { locationX, locationY } = event.nativeEvent; setCurrent((path) => `${path} L ${locationX} ${locationY}`); }} onTouchEnd={() => { if (current) setStrokes((paths) => [...paths, current]); setCurrent(''); }}><Svg width="100%" height="100%">{[...strokes, current].filter(Boolean).map((path, index) => <Path key={index} d={path} stroke="#12263A" strokeWidth={2} fill="none" strokeLinecap="round" />)}</Svg></View><AppText>{t('scanner.signatureNote')}</AppText><Button label={t('scanner.undo')} variant="secondary" onPress={() => setStrokes((paths) => paths.slice(0, -1))} /><Button label={t('scanner.reset')} variant="secondary" onPress={() => setStrokes([])} /><Button label={t('scanner.useSignature')} loading={busy} disabled={!strokes.length} onPress={() => { void save(); }} /></Screen>;
}
