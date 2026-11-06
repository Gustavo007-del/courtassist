import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { AppText } from '../../components/common/AppText';
import { TextField } from '../../components/common/TextField';
import { Button } from '../../components/common/Button';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { Notice } from '../../components/common/Notice';
import { draftingApi } from '../../services/drafting-api';
import { clientApi } from '../../services/client-api';
import { caseApi } from '../../services/case-api';
import { friendlyError } from '../../utils/errors';
export default function CreateDraft() {
  const {
    templateId,
    caseId: initialCase,
    clientId: initialClient,
  } = useLocalSearchParams<{ templateId?: string; caseId?: string; clientId?: string }>();
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [title, setTitle] = useState('');
  const [category, setCategory] = useState('General legal documents');
  const [language, setLanguage] = useState('en');
  const [caseId, setCaseId] = useState(initialCase ?? '');
  const [clientId, setClientId] = useState(initialClient ?? '');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const cases = useQuery({ queryKey: ['draft-case-options'], queryFn: () => caseApi.list({ limit: 100 }) });
  const clients = useQuery({
    queryKey: ['draft-client-options'],
    queryFn: () => clientApi.list({ limit: 100 }),
  });
  async function create() {
    if (!title.trim() || !category.trim()) {
      setError(t('work.invalid'));
      return;
    }
    setBusy(true);
    try {
      const row = await draftingApi.create({
        title,
        category,
        language,
        case_id: caseId || null,
        client_id: clientId || null,
        template_id: templateId || null,
      });
      void qc.invalidateQueries({ queryKey: ['drafts'] });
      router.replace({ pathname: '/practice-tools/draft-editor', params: { id: row.id } });
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen title={t('work.newDraft')} back>
      {error && <Notice message={error} />}
      <TextField label={t('work.title')} value={title} onChangeText={setTitle} />
      <TextField label={t('work.category')} value={category} onChangeText={setCategory} />
      <AppText>{t('work.language')}</AppText>
      <ChoiceChips
        value={language}
        onChange={setLanguage}
        options={[
          { value: 'en', label: 'English' },
          { value: 'ml', label: 'മലയാളം' },
        ]}
      />
      <AppText>{t('work.case')}</AppText>
      <ChoiceChips
        value={caseId}
        onChange={(value) => {
          setCaseId(value);
          const selected = cases.data?.items.find((row) => row.id === value);
          if (selected?.client_id) setClientId(selected.client_id);
        }}
        options={[
          { value: '', label: t('work.none') },
          ...(cases.data?.items ?? []).map((row) => ({
            value: row.id,
            label: row.case_number + ' · ' + row.case_title,
          })),
        ]}
      />
      <AppText>{t('work.client')}</AppText>
      <ChoiceChips
        value={clientId}
        onChange={setClientId}
        options={[
          { value: '', label: t('work.none') },
          ...(clients.data?.items ?? []).map((row) => ({ value: row.id, label: row.full_name })),
        ]}
      />
      <Button label={t('work.new')} loading={busy} onPress={() => void create()} />
    </Screen>
  );
}
