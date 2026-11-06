import { useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { TextField } from '../../components/common/TextField';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { researchApi, researchTypes } from '../../services/research-api';
import { caseApi } from '../../services/case-api';
export default function Filters() {
  const params = useLocalSearchParams<Record<string, string>>();
  const { t } = useTranslation();
  const [form, setForm] = useState<Record<string, string>>({
    q: params.q ?? '',
    item_type: params.item_type ?? '',
    court: params.court ?? '',
    from_date: params.from_date ?? '',
    to_date: params.to_date ?? '',
    language: params.language ?? '',
    tag: params.tag ?? '',
    case_id: params.case_id ?? '',
    sort: params.sort ?? 'recent',
  });
  const tags = useQuery({ queryKey: ['research-tags'], queryFn: () => researchApi.tags() });
  const cases = useQuery({
    queryKey: ['research-case-options'],
    queryFn: () => caseApi.list({ limit: 100 }),
  });
  const set = (key: string, value: string) => setForm({ ...form, [key]: value });
  return (
    <Screen title={t('research.filters')} back>
      <AppText>{t('research.itemType')}</AppText>
      <ChoiceChips
        value={form.item_type}
        onChange={(value) => set('item_type', value)}
        options={[
          { value: '', label: t('planning.all') },
          ...researchTypes.map((value) => ({ value, label: t(`research.types.${value}`, value) })),
        ]}
      />
      {['court', 'from_date', 'to_date'].map((key) => (
        <TextField
          key={key}
          label={t(`research.${key}`)}
          value={form[key]}
          onChangeText={(value) => set(key, value)}
        />
      ))}
      <AppText>{t('work.language')}</AppText>
      <ChoiceChips
        value={form.language}
        onChange={(value) => set('language', value)}
        options={[
          { value: '', label: t('planning.all') },
          { value: 'en', label: 'English' },
          { value: 'ml', label: 'മലയാളം' },
        ]}
      />
      <AppText>{t('research.tags')}</AppText>
      <ChoiceChips
        value={form.tag}
        onChange={(value) => set('tag', value)}
        options={[
          { value: '', label: t('planning.all') },
          ...(tags.data ?? []).map((tag) => ({ value: tag.name, label: tag.name })),
        ]}
      />
      <AppText>{t('work.case')}</AppText>
      <ChoiceChips
        value={form.case_id}
        onChange={(value) => set('case_id', value)}
        options={[
          { value: '', label: t('planning.all') },
          ...(cases.data?.items ?? []).map((row) => ({ value: row.id, label: row.case_number })),
        ]}
      />
      <AppText>{t('research.sort')}</AppText>
      <ChoiceChips
        value={form.sort}
        onChange={(value) => set('sort', value)}
        options={['recent', 'title', 'date'].map((value) => ({ value, label: t(`research.${value}`) }))}
      />
      <Button
        label={t('work.apply')}
        onPress={() => router.replace({ pathname: '/research', params: form })}
      />
    </Screen>
  );
}
