import { useState } from 'react';
import { RefreshControl, ScrollView, View } from 'react-native';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { EmptyState } from '../../components/common/EmptyState';
import { TextField } from '../../components/common/TextField';
import { Screen } from '../../components/layout/Screen';
import { DocumentCard } from '../../components/documents/DocumentCard';
import { documentApi } from '../../services/document-api';
import { listDocuments } from '../../features/scanner/storage';
import { useAuthStore } from '../../store/auth-store';

export default function DocumentVault() {
  const { t } = useTranslation();
  const user = useAuthStore((state) => state.user);
  const [search, setSearch] = useState('');
  const [view, setView] = useState<'all' | 'recent' | 'failed'>('all');
  const [offset, setOffset] = useState(0);
  const [category, setCategory] = useState('');
  const [mimeType, setMimeType] = useState('');
  const [recentSince] = useState(() => new Date(Date.now() - 30 * 86400000).toISOString());
  const limit = 30;
  const filters = { limit, offset, category, mime_type: mimeType, storage_status: view === 'failed' ? 'upload_failed' : undefined, from_date: view === 'recent' ? recentSince : undefined };
  const cloud = useQuery({ queryKey: ['vault', user?.id, view, offset, category, mimeType], queryFn: () => documentApi.list(filters), enabled: !!user });
  const local = useQuery({ queryKey: ['local-documents', user?.id], queryFn: () => listDocuments(user!.id), enabled: !!user });
  return <Screen title={t('vault.title')} back>
    <View style={{ gap: 8 }}>
      <TextField label={t('vault.search')} value={search} onChangeText={setSearch} />
      <ChoiceChips value={view} onChange={(value) => { setView(value); setOffset(0); }} options={[{ value: 'all', label: t('vaultAll') }, { value: 'recent', label: t('vaultRecent') }, { value: 'failed', label: t('vaultFailed') }]} />
      <TextField label={t('vault.category')} value={category} onChangeText={(value) => { setCategory(value); setOffset(0); }} />
      <TextField label={t('vaultFileType')} value={mimeType} onChangeText={(value) => { setMimeType(value); setOffset(0); }} />
      <Button label={t('vault.upload')} onPress={() => router.push('/documents/upload')} />
      <Button label={t('vault.scan')} variant="secondary" onPress={() => router.push('/(tabs)/scanner')} />
      <Button label={t('vault.advancedSearch')} variant="secondary" onPress={() => router.push('/documents/search')} />
      <Button label={t('vault.archived')} variant="secondary" onPress={() => router.push('/documents/archived')} />
    </View>
    <ScrollView refreshControl={<RefreshControl refreshing={cloud.isRefetching || local.isRefetching} onRefresh={() => { void cloud.refetch(); void local.refetch(); }} />}>
      <AppText>{t('vault.cloudDocuments')}</AppText>
      {cloud.isError && <AppText>{t('vault.cloudUnavailable')}</AppText>}
      {cloud.data?.filter((item) => item.document_name.toLowerCase().includes(search.toLowerCase())).map((item) => <DocumentCard key={item.id} item={item} onPress={() => router.push({ pathname: '/documents/[id]', params: { id: item.id } })} />)}
      <View style={{ flexDirection: 'row', gap: 8 }}>
        {offset > 0 && <Button label={t('vaultPrevious')} variant="secondary" onPress={() => setOffset(Math.max(0, offset - limit))} />}
        {cloud.data?.length === limit && <Button label={t('vaultNext')} variant="secondary" onPress={() => setOffset(offset + limit)} />}
      </View>
      {view === 'all' && <><AppText>{t('vault.localDocuments')}</AppText>
        {local.data?.filter((item) => item.document_name.toLowerCase().includes(search.toLowerCase())).map((item) => <View key={item.id}><Button label={`${item.document_name} · ${t('scanner.localOnly')}`} variant="secondary" onPress={() => router.push({ pathname: '/scanner/document-details', params: { id: item.id } })} /></View>)}
      </>}
      {!cloud.isPending && !local.isPending && !cloud.data?.length && !local.data?.length && <EmptyState title={t('vault.empty')} body={t('vault.emptyDetail')} />}
    </ScrollView>
  </Screen>;
}
