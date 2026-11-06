import { useRef, useState } from 'react';
import { Alert } from 'react-native';
import { router, useNavigation, usePreventRemove } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import { Screen } from '../layout/Screen';
import { AppText } from '../common/AppText';
import { Button } from '../common/Button';
import { TextField } from '../common/TextField';
import { ChoiceChips } from '../common/ChoiceChips';
import { Notice } from '../common/Notice';
import {
  researchApi,
  researchTypes,
  type ResearchItem,
  type ResearchFields,
} from '../../services/research-api';
import { caseApi } from '../../services/case-api';
import { clientApi } from '../../services/client-api';
import { documentApi } from '../../services/document-api';
import { friendlyError } from '../../utils/errors';
const base: ResearchFields = {
  title: '',
  item_type: 'Research note',
  court: '',
  case_number: '',
  cnr_number: '',
  citation: '',
  case_title: '',
  judgment_date: null,
  source_name: '',
  source_url: '',
  accessed_date: null,
  summary: '',
  full_text: '',
  language: 'en',
  act_name: '',
  section_number: '',
  party_information: '',
  subject: '',
  notes: '',
  verification_status: 'unverified',
  verification_notes: '',
  page_reference: '',
  paragraph_reference: '',
  case_id: null,
  client_id: null,
  document_id: null,
  favorite: false,
  tags: [],
};
const validation = z.object({
  title: z.string().trim().min(1).max(240),
  source_url: z.union([z.literal(''), z.url({ protocol: /^https?$/ })]),
  judgment_date: z.union([z.iso.date(), z.null()]),
  accessed_date: z.union([z.iso.date(), z.null()]),
});
export function ResearchItemForm({ initial, caseId }: { initial?: ResearchItem; caseId?: string }) {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const navigation = useNavigation();
  const initialValues = {
    ...base,
    ...Object.fromEntries(
      Object.keys(base).map((key) => [
        key,
        initial?.[key as keyof ResearchFields] ?? base[key as keyof ResearchFields],
      ]),
    ),
    ...(!initial ? { case_id: caseId || null, language: i18n.language === 'ml' ? 'ml' : 'en' } : {}),
  } as ResearchFields;
  const [form, setForm] = useState<ResearchFields>(initialValues);
  const [advanced, setAdvanced] = useState(false);
  const [newTag, setNewTag] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const saved = useRef(false);
  const [original] = useState(JSON.stringify(initialValues));
  const dirty = JSON.stringify(form) !== original;
  usePreventRemove(dirty, ({ data }) => {
    if (saved.current) {
      navigation.dispatch(data.action);
      return;
    }
    Alert.alert(t('work.unsaved'), t('research.unsavedNotice'), [
      { text: t('work.cancel'), style: 'cancel' },
      { text: t('work.discard'), style: 'destructive', onPress: () => navigation.dispatch(data.action) },
    ]);
  });
  const cases = useQuery({
    queryKey: ['research-case-options'],
    queryFn: () => caseApi.list({ limit: 100 }),
  });
  const clients = useQuery({
    queryKey: ['research-client-options'],
    queryFn: () => clientApi.list({ limit: 100 }),
  });
  const documents = useQuery({
    queryKey: ['research-document-options'],
    queryFn: () => documentApi.list({ limit: 100 }),
  });
  const catalog = useQuery({ queryKey: ['research-tags'], queryFn: () => researchApi.tags() });
  const critical = [
    'citation',
    'court',
    'case_number',
    'cnr_number',
    'judgment_date',
    'source_url',
    'document_id',
    'case_title',
    'act_name',
    'section_number',
  ];
  const set = <K extends keyof ResearchFields>(key: K, value: ResearchFields[K]) =>
    setForm((current) => ({
      ...current,
      [key]: value,
      ...(critical.includes(key) && value !== current[key] ? { verification_status: 'unverified' } : {}),
    }));
  const text = (
    key:
      | 'title'
      | 'court'
      | 'citation'
      | 'source_name'
      | 'source_url'
      | 'case_number'
      | 'cnr_number'
      | 'case_title'
      | 'act_name'
      | 'section_number'
      | 'subject'
      | 'summary'
      | 'notes'
      | 'full_text'
      | 'verification_notes'
      | 'page_reference'
      | 'paragraph_reference'
      | 'party_information'
      | 'judgment_date'
      | 'accessed_date',
    multiline = false,
  ) => (
    <TextField
      key={key}
      label={t(`research.fields.${key}`)}
      value={form[key] ?? ''}
      onChangeText={(value) =>
        setForm((current) => ({
          ...current,
          [key]: ['judgment_date', 'accessed_date'].includes(key) && !value ? null : value,
          ...(critical.includes(key) && value !== current[key] ? { verification_status: 'unverified' } : {}),
        }))
      }
      multiline={multiline}
    />
  );
  function addTag(value: string) {
    const name = value.trim();
    if (name && !form.tags.some((tag) => tag.toLocaleLowerCase() === name.toLocaleLowerCase()))
      set('tags', [...form.tags, name]);
    setNewTag('');
  }
  async function save() {
    if (!validation.safeParse(form).success) {
      setError(t('work.invalid'));
      return;
    }
    setBusy(true);
    try {
      const item = await researchApi.save(initial?.id, form);
      saved.current = true;
      void qc.invalidateQueries({ queryKey: ['research'] });
      void qc.invalidateQueries({ queryKey: ['research-tags'] });
      router.replace({ pathname: '/research/[id]', params: { id: item.id } });
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Screen title={t(initial ? 'research.edit' : 'research.add')} subtitle={t('research.disclaimer')} back>
      {error && <Notice message={error} />} {text('title')}
      <AppText>{t('research.itemType')}</AppText>
      <ChoiceChips
        value={form.item_type}
        onChange={(value) => set('item_type', value)}
        options={researchTypes.map((value) => ({ value, label: t(`research.types.${value}`, value) }))}
      />
      {text('citation')}
      {text('court')}
      {text('source_name')}
      {text('source_url')}
      {text('summary', true)}
      {text('notes', true)}
      <AppText>{t('work.language')}</AppText>
      <ChoiceChips
        value={form.language}
        onChange={(value) => set('language', value)}
        options={[
          { value: 'en', label: 'English' },
          { value: 'ml', label: 'മലയാളം' },
          { value: 'other', label: t('work.Other') },
        ]}
      />
      <AppText>{t('research.tags')}</AppText>
      {form.tags.map((tag) => (
        <Button
          key={tag}
          label={'× ' + tag}
          variant="secondary"
          onPress={() =>
            set(
              'tags',
              form.tags.filter((value) => value !== tag),
            )
          }
        />
      ))}
      <TextField label={t('research.tagName')} value={newTag} onChangeText={setNewTag} />
      <Button label={t('research.addTag')} variant="secondary" onPress={() => addTag(newTag)} />
      <ChoiceChips
        value=""
        onChange={addTag}
        options={(catalog.data ?? []).map((tag) => ({ value: tag.name, label: tag.name }))}
      />
      <AppText>{t('work.case')}</AppText>
      <ChoiceChips
        value={form.case_id ?? ''}
        onChange={(value) => set('case_id', value || null)}
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
        value={form.client_id ?? ''}
        onChange={(value) => set('client_id', value || null)}
        options={[
          { value: '', label: t('work.none') },
          ...(clients.data?.items ?? []).map((row) => ({ value: row.id, label: row.full_name })),
        ]}
      />
      <AppText>{t('research.document')}</AppText>
      <ChoiceChips
        value={form.document_id ?? ''}
        onChange={(value) => set('document_id', value || null)}
        options={[
          { value: '', label: t('work.none') },
          ...(documents.data ?? [])
            .filter((row) => row.current_version_id)
            .map((row) => ({ value: row.id, label: row.document_name })),
        ]}
      />
      <Button label={t('research.advanced')} variant="secondary" onPress={() => setAdvanced(!advanced)} />
      {advanced && (
        <>
          {(
            [
              'case_title',
              'case_number',
              'cnr_number',
              'judgment_date',
              'accessed_date',
              'act_name',
              'section_number',
              'subject',
              'party_information',
              'page_reference',
              'paragraph_reference',
            ] as const
          ).map((key) => text(key))}
          <Notice message={t('research.fullTextNotice')} />
          {text('full_text', true)}
        </>
      )}
      <AppText>{t('research.verification')}</AppText>
      <ChoiceChips
        value={form.verification_status}
        onChange={(value) => set('verification_status', value)}
        options={['unverified', 'manually_verified'].map((value) => ({
          value,
          label: t(`research.${value}`),
        }))}
      />
      {text('verification_notes', true)}
      <Button label={t('work.save')} loading={busy} onPress={() => void save()} />
    </Screen>
  );
}
