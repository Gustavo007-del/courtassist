import { useEffect, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import * as DocumentPicker from 'expo-document-picker';
import { File } from 'expo-file-system';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { Notice } from '../../components/common/Notice';
import { TextField } from '../../components/common/TextField';
import { Screen } from '../../components/layout/Screen';
import { getDocument } from '../../features/scanner/storage';
import { useAuthStore } from '../../store/auth-store';
import { documentApi, putPrivateFile } from '../../services/document-api';
import { apiRequest } from '../../services/api';
import { control } from '../../features/sync/repository';
import { stageUpload } from '../../features/sync/files';
import { publishStatus, syncNow } from '../../features/sync/engine';
import { useSyncState } from '../../features/sync/state';
import { friendlyError } from '../../utils/errors';

const categories = [
  'Petition',
  'Counter Affidavit',
  'Written Statement',
  'Judgment',
  'Court Order',
  'Vakalath',
  'Evidence',
  'Witness Documents',
  'Legal Notice',
  'Application',
  'Affidavit',
  'Case Records',
  'Identity Documents',
  'Medical Records',
  'Agreements',
  'Receipts',
  'Other',
];
type Selected = { uri: string; name: string; size: number; mimeType: string };
export default function UploadDocument() {
  const { localId, documentId, caseId, clientId, hearingId, researchId } = useLocalSearchParams<{
    localId?: string;
    documentId?: string;
    caseId?: string;
    clientId?: string;
    hearingId?: string;
    researchId?: string;
  }>();
  const { t } = useTranslation();
  const user = useAuthStore((state) => state.user);
  const cache = useQueryClient();
  const [uploadedId, setUploadedId] = useState<string | null>(null);
  const [file, setFile] = useState<Selected | null>(null);
  const [name, setName] = useState('');
  const [category, setCategory] = useState('Other');
  const [description, setDescription] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingId, setPendingId] = useState<string | null>(documentId ?? null);
  useEffect(() => {
    if (!localId || !user) return;
    void getDocument(user.id, localId).then((item) => {
      if (item) {
        setFile({
          uri: item.local_uri,
          name: item.original_filename,
          size: item.file_size,
          mimeType: item.file_type,
        });
        setName(item.document_name);
        setCategory(item.document_category);
      }
    });
  }, [localId, user]);
  const choose = async () => {
    const result = await DocumentPicker.getDocumentAsync({
      type: [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
        'image/jpeg',
        'image/png',
      ],
      copyToCacheDirectory: true,
    });
    if (result.canceled) return;
    const asset = result.assets[0];
    const picked = new File(asset.uri);
    const mimes: Record<string, string> = {
      pdf: 'application/pdf',
      docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      txt: 'text/plain',
      jpg: 'image/jpeg',
      jpeg: 'image/jpeg',
      png: 'image/png',
    };
    setUploadedId(null);
    setFile({
      uri: asset.uri,
      name: asset.name,
      size: asset.size ?? picked.size ?? 0,
      mimeType:
        asset.mimeType && asset.mimeType !== 'application/octet-stream'
          ? asset.mimeType
          : (mimes[asset.name.split('.').pop()?.toLowerCase() ?? ''] ?? 'application/octet-stream'),
    });
    setName(asset.name.replace(/\.[^.]+$/, ''));
    if (!documentId) setPendingId(null);
  };
  const upload = async () => {
    if (!file || busy) return;
    if (uploadedId && researchId) {
      setBusy(true);
      try {
        await apiRequest(`/research-items/${researchId}`, {
          method: 'PATCH',
          body: JSON.stringify({ document_id: uploadedId }),
        });
        await cache.invalidateQueries({ queryKey: ['research'] });
        router.replace({ pathname: '/research/[id]', params: { id: researchId } });
      } catch (caught) {
        setError(friendlyError(caught));
      } finally {
        setBusy(false);
      }
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setStatus(t('vault.preparing'));
      const offline = useSyncState.getState().connected === false;
      if (user && !pendingId && !researchId && (offline || localId) && (await control(user.id))?.enabled) {
        const queued = await stageUpload(user.id, file.uri, {
          document_name: name.trim() || file.name,
          original_filename: file.name, mime_type: file.mimeType, file_size: file.size,
          document_category: category, description, case_id: caseId || null,
          client_id: clientId || null, hearing_id: hearingId || null,
        });
        await publishStatus(user.id);
        void cache.invalidateQueries({ queryKey: ['vault'] });
        if (!offline) void syncNow(user.id);
        router.replace({ pathname: '/documents/[id]', params: { id: queued.operation.entity_id } });
        return;
      }
      const doc = pendingId
        ? await documentApi.get(pendingId)
        : await documentApi.create({
            document_name: name.trim() || file.name,
            original_filename: file.name,
            mime_type: file.mimeType,
            file_size: file.size,
            document_category: category,
            description,
            case_id: caseId || null,
            client_id: clientId || null,
            hearing_id: hearingId || null,
          });
      if (doc.file_size !== file.size || doc.mime_type !== file.mimeType)
        throw new Error(t('vault.fileMismatch'));
      setPendingId(doc.id);
      const signed = await documentApi.uploadUrl(doc.id);
      setStatus(t('vault.uploading'));
      await putPrivateFile(file.uri, signed, file.mimeType);
      setStatus(t('vault.confirming'));
      await documentApi.confirm(doc.id, signed.version_id);
      setUploadedId(doc.id);
      await Promise.all([
        cache.invalidateQueries({ queryKey: ['vault'] }),
        cache.invalidateQueries({ queryKey: ['vault-document', doc.id] }),
        cache.invalidateQueries({ queryKey: ['case-cloud-documents'] }),
        cache.invalidateQueries({ queryKey: ['client-documents'] }),
        cache.invalidateQueries({ queryKey: ['hearing-documents'] }),
      ]);
      if (researchId) {
        await apiRequest(`/research-items/${researchId}`, {
          method: 'PATCH',
          body: JSON.stringify({ document_id: doc.id }),
        });
        await cache.invalidateQueries({ queryKey: ['research'] });
        router.replace({ pathname: '/research/[id]', params: { id: researchId } });
      } else router.replace({ pathname: '/documents/[id]', params: { id: doc.id } });
    } catch (caught) {
      setError(friendlyError(caught));
      setStatus(t('vault.failed'));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Screen title={t('vault.upload')} back>
      {error && <Notice message={error} />}
      <Button
        label={t('vault.chooseFile')}
        variant="secondary"
        onPress={() => {
          void choose();
        }}
      />
      {file && (
        <AppText>
          {file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB
        </AppText>
      )}
      <TextField label={t('vault.name')} value={name} onChangeText={setName} />
      <TextField label={t('vault.description')} value={description} onChangeText={setDescription} multiline />
      <AppText>{t('vault.category')}</AppText>
      <ChoiceChips
        value={category}
        onChange={setCategory}
        options={categories.map((value) => ({ value, label: t(`vaultCategories.${value}`, value) }))}
      />
      {status && <AppText>{status}</AppText>}
      <Button
        label={pendingId ? t('vault.retryUpload') : t('vault.upload')}
        loading={busy}
        onPress={() => {
          void upload();
        }}
      />
    </Screen>
  );
}
