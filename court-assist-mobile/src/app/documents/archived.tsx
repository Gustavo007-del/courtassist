import { router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../components/common/AppText';
import { Screen } from '../../components/layout/Screen';
import { DocumentCard } from '../../components/documents/DocumentCard';
import { documentApi } from '../../services/document-api';
export default function ArchivedDocuments() { const { t } = useTranslation(); const query = useQuery({ queryKey: ['vault-archived'], queryFn: () => documentApi.list({ archived: true }) }); return <Screen title={t('vault.archived')} back>{query.isError && <AppText>{t('vault.cloudUnavailable')}</AppText>}{query.data?.map((item) => <DocumentCard key={item.id} item={item} onPress={() => router.push({ pathname: '/documents/[id]', params: { id: item.id } })} />)}</Screen>; }
