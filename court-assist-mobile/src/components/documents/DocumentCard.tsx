import { Pressable } from 'react-native';
import { useTranslation } from 'react-i18next';
import { AppText } from '../common/AppText';
import { Card } from '../common/Card';
import type { VaultDocument } from '../../services/document-api';
export function DocumentCard({ item, onPress }: { item: VaultDocument; onPress: () => void }) {
  const { t } = useTranslation();
  return <Pressable onPress={onPress}><Card><AppText>{item.document_name}</AppText><AppText>{t(`vaultCategories.${item.document_category}`, item.document_category)} · {t(`vaultStatus.${item.storage_status}`, item.storage_status)}</AppText><AppText>{new Date(item.created_at).toLocaleDateString()} · {(item.file_size / 1024 / 1024).toFixed(2)} MB</AppText>{item.case_number && <AppText>{item.case_number}</AppText>}{item.client_name && <AppText>{item.client_name}</AppText>}{item.snippet && <AppText>{item.snippet}{item.page_number ? ` · ${t('vault.page')} ${item.page_number}` : ''}</AppText>}</Card></Pressable>;
}
