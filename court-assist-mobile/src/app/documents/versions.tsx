import { useState } from 'react';
import { View } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import * as DocumentPicker from 'expo-document-picker';
import { File } from 'expo-file-system';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { Notice } from '../../components/common/Notice';
import { TextField } from '../../components/common/TextField';
import { Screen } from '../../components/layout/Screen';
import { secureDownload } from '../../features/vault/download';
import { documentApi, putPrivateFile, type VaultVersion } from '../../services/document-api';
import { useAuthStore } from '../../store/auth-store';
import { friendlyError } from '../../utils/errors';

export default function Versions() {
  const { id } = useLocalSearchParams<{ id: string }>(); const { t } = useTranslation(); const user = useAuthStore((state) => state.user); const cache = useQueryClient();
  const [description, setDescription] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  const doc = useQuery({ queryKey: ['vault-document', id], queryFn: () => documentApi.get(id) }); const versions = useQuery({ queryKey: ['vault-versions', id], queryFn: () => documentApi.versions(id) });
  const revise = async (existing?: VaultVersion) => { if (!doc.data || busy) return; const picked = await DocumentPicker.getDocumentAsync({ type: [doc.data.mime_type], copyToCacheDirectory: true }); if (picked.canceled) return; setBusy(true); setError(null); try { const asset = picked.assets[0]; const file = new File(asset.uri); const size = asset.size ?? file.size; if (existing && (size !== existing.file_size || asset.name !== existing.original_filename)) throw new Error(t('vault.fileMismatch')); const version = existing ?? await documentApi.createVersion(id, { original_filename: asset.name, file_size: size, change_description: description }); const signed = await documentApi.uploadUrl(id, version.id); await putPrivateFile(asset.uri, signed, doc.data.mime_type); await documentApi.confirm(id, version.id); await Promise.all([versions.refetch(), doc.refetch(), cache.invalidateQueries({ queryKey: ['vault'] })]); } catch (caught) { setError(friendlyError(caught)); } finally { setBusy(false); } };
  return <Screen title={t('vault.versions')} back>{error && <Notice message={error} />}{versions.data?.map((version) => <View key={version.id}><AppText>v{version.version_number} · {version.original_filename} · {version.storage_status}</AppText><AppText>{version.change_description}</AppText>{version.storage_status === 'cloud_stored' ? <Button label={t('vault.preview')} variant="secondary" onPress={() => { void (async () => { try { const file = await secureDownload(user!.id, doc.data!, version.id); await file.preview({ title: version.original_filename, mimeType: doc.data!.mime_type }); } catch (caught) { setError(friendlyError(caught)); } })(); }} /> : <Button label={t('vault.retryUpload')} variant="secondary" loading={busy} onPress={() => { void revise(version); }} />}</View>)}<TextField label={t('vault.changeDescription')} value={description} onChangeText={setDescription} /><Button label={t('vault.addVersion')} loading={busy} onPress={() => { void revise(); }} /></Screen>;
}
