import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { Card } from '../../components/common/Card';
import { EmptyState } from '../../components/common/EmptyState';
export default function Scanner() { const { t } = useTranslation(); return <Screen title={t('tabs.scanner')}><Card><EmptyState title={t('placeholder.title')} body={t('placeholder.scanner')} /></Card></Screen>; }
