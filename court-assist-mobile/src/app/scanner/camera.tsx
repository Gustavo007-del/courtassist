import { router, useLocalSearchParams } from 'expo-router';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { ScannerCamera } from '../../components/scanner/ScannerCamera';
import { Screen } from '../../components/layout/Screen';
import { useScannerStore } from '../../features/scanner/store';
import { useAuthStore } from '../../store/auth-store';
export default function CameraScreen() { const { retakeId } = useLocalSearchParams<{ retakeId?: string }>(); const { t } = useTranslation(); const user = useAuthStore((state) => state.user); const hydrate = useScannerStore((state) => state.hydrate); useEffect(() => { if (user?.id) void hydrate(user.id); }, [hydrate, user?.id]); return <Screen title={t('scanner.camera')} back><ScannerCamera retakeId={retakeId} onDone={() => router.replace('/scanner/review')} /></Screen>; }
