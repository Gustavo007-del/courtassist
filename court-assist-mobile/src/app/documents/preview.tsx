import { useState } from 'react';
import { useLocalSearchParams } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Screen } from '../../components/layout/Screen';
import { secureDownload } from '../../features/vault/download';
import { documentApi } from '../../services/document-api';
import { useAuthStore } from '../../store/auth-store';
import { previewPin } from '../../features/sync/files';
import { useSyncState } from '../../features/sync/state';
import { friendlyError } from '../../utils/errors';
export default function VaultPreview() { const { id, versionId } = useLocalSearchParams<{ id: string; versionId?: string }>(); const { t } = useTranslation(); const user = useAuthStore((state) => state.user); const [error, setError] = useState<string | null>(null); const open = async () => { try { if (user && useSyncState.getState().enabled && useSyncState.getState().connected === false &&
      await previewPin(user.id, id, versionId || undefined)) return;
    const doc = await documentApi.get(id); const file = await secureDownload(user!.id, doc, versionId || undefined); await file.preview({ title: doc.document_name, mimeType: doc.mime_type }); } catch (caught) { setError(friendlyError(caught)); } }; return <Screen title={t('vault.preview')} back>{error && <AppText>{error}</AppText>}<Button label={t('vault.preview')} onPress={() => { void open(); }} /></Screen>; }
