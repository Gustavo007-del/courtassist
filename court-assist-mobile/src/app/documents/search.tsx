import { useState } from 'react';
import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { TextField } from '../../components/common/TextField';
import { Screen } from '../../components/layout/Screen';
import { DocumentCard } from '../../components/documents/DocumentCard';
import { documentApi } from '../../services/document-api';

export default function DocumentSearch() {
  const { t } = useTranslation(); const [q, setQ] = useState(''); const [category, setCategory] = useState(''); const [exact, setExact] = useState(false);
  const results = useQuery({ queryKey: ['vault-search', q, category, exact], queryFn: () => documentApi.search(q, { category, exact }), enabled: q.trim().length > 0 });
  return <Screen title={t('vault.advancedSearch')} back><TextField label={t('vault.search')} value={q} onChangeText={setQ} /><TextField label={t('vault.category')} value={category} onChangeText={setCategory} /><Button label={`${exact ? '✓ ' : ''}${t('vaultExactPhrase')}`} variant="secondary" onPress={() => setExact(!exact)} />{results.isError && <AppText>{t('vault.searchFailed')}</AppText>}{results.data?.items.map((item) => <DocumentCard key={item.id} item={item} onPress={() => router.push({ pathname: '/documents/[id]', params: { id: item.id } })} />)}</Screen>;
}
