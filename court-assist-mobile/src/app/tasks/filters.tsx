import { useState } from 'react';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { Button } from '../../components/common/Button';
import { TextField } from '../../components/common/TextField';
import { Screen } from '../../components/layout/Screen';
export default function TaskFilters() { const { t } = useTranslation(); const [status, setStatus] = useState(''); const [caseId, setCaseId] = useState(''); return <Screen title={t('planning.filters')} back><TextField label={t('planning.status')} value={status} onChangeText={setStatus} /><TextField label={t('planning.case')} value={caseId} onChangeText={setCaseId} /><Button label={t('planning.applyFilters')} onPress={() => router.replace({ pathname: '/tasks', params: { status, caseId } })} /></Screen>; }
