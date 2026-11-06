import { useRef, useState } from 'react';
import { Alert } from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Controller, useForm, useFieldArray, useWatch } from 'react-hook-form';
import { z } from 'zod';
import { useTranslation } from 'react-i18next';
import { Screen } from '../../components/layout/Screen';
import { AppText } from '../../components/common/AppText';
import { Button } from '../../components/common/Button';
import { TextField } from '../../components/common/TextField';
import { ChoiceChips } from '../../components/common/ChoiceChips';
import { Notice } from '../../components/common/Notice';
import { documentApi } from '../../services/document-api';
import { clientApi } from '../../services/client-api';
import { caseApi } from '../../services/case-api';
import { financeApi, type FinanceKind } from '../../services/finance-api';
import { friendlyError } from '../../utils/errors';
const money = z
  .string()
  .regex(/^\d{1,12}(\.\d{1,2})?$/)
  .refine((v) => !/^0+(\.0{1,2})?$/.test(v));
const schema = z.object({
  title: z.string().max(180),
  notes: z.string().max(5000),
  vendor: z.string().max(180),
  document_id: z.string(),
  arrangement: z.string().max(40),
  client_id: z.string(),
  case_id: z.string(),
  agreement_id: z.string(),
  amount: z.string(),
  date: z.iso.date(),
  due: z.string(),
  description: z.string().max(5000),
  category: z.string().max(80),
  method: z.string().max(40),
  status: z.string(),
  reference: z.string().max(120),
  terms: z.string().max(5000),
  lines: z.array(z.object({ description: z.string(), quantity: z.string(), unit_price: z.string() })),
});
type Values = z.infer<typeof schema>;
function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
export default function FinanceForm() {
  const {
    kind = 'payments',
    clientId = '',
    caseId = '',
  } = useLocalSearchParams<{ kind: FinanceKind; clientId?: string; caseId?: string }>();
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const key = useRef('');
  const sending = useRef(false);
  const { control, handleSubmit, setValue } = useForm<Values>({
    defaultValues: {
      title: '',
      notes: '',
      vendor: '',
      document_id: '',
      arrangement: 'fixed',
      client_id: clientId,
      case_id: caseId,
      agreement_id: '',
      amount: '',
      date: today(),
      due: '',
      description: '',
      category: 'Other',
      method: 'UPI',
      status: kind === 'fee-agreements' ? 'active' : kind === 'expenses' ? 'confirmed' : 'pending',
      reference: '',
      terms: '',
      lines: [{ description: '', quantity: '1', unit_price: '' }],
    },
  });
  const { fields, append, remove } = useFieldArray({ control, name: 'lines' });
  const form = useWatch({ control }) as Values;
  const documents = useQuery({
    queryKey: ['finance-document-options'],
    queryFn: () => documentApi.list({ limit: 100 }),
    enabled: kind === 'expenses',
  });
  const clients = useQuery({
    queryKey: ['finance-client-options'],
    queryFn: () => clientApi.list({ limit: 100 }),
  });
  const cases = useQuery({ queryKey: ['finance-case-options'], queryFn: () => caseApi.list({ limit: 100 }) });
  const agreements = useQuery({
    queryKey: ['finance-agreement-options'],
    queryFn: () => financeApi.list('fee-agreements'),
  });
  const field = (
    name:
      | 'amount'
      | 'date'
      | 'due'
      | 'description'
      | 'category'
      | 'reference'
      | 'terms'
      | 'title'
      | 'notes'
      | 'vendor',
    label: string,
  ) => (
    <Controller
      key={name}
      control={control}
      name={name}
      render={({ field: f }) => (
        <TextField
          label={t(`work.${label}`)}
          value={f.value}
          onChangeText={f.onChange}
          keyboardType={name === 'amount' ? 'numeric' : 'default'}
        />
      )}
    />
  );
  async function save(values: Values) {
    const parsed = schema.safeParse(values);
    if (
      !parsed.success ||
      !(kind === 'expenses' || z.uuid().safeParse(values.client_id).success) ||
      (!['invoices'].includes(kind) && !money.safeParse(values.amount).success) ||
      (values.due && !z.iso.date().safeParse(values.due).success) ||
      (kind === 'invoices' &&
        values.lines.some(
          (line) =>
            !line.description.trim() ||
            !money.safeParse(line.unit_price).success ||
            !money.safeParse(line.quantity).success,
        ))
    ) {
      setError(t('work.invalid'));
      return;
    }
    const links = { client_id: values.client_id || null, case_id: values.case_id || null };
    let body: unknown;
    if (kind === 'invoices')
      body = {
        ...links,
        agreement_id: values.agreement_id || null,
        issue_date: values.date,
        due_date: values.due || null,
        terms: values.terms,
        lines: values.lines,
      };
    else if (kind === 'fee-agreements')
      body = {
        ...links,
        amount: values.amount,
        agreement_date: values.date,
        due_date: values.due || null,
        description: values.description,
        status: values.status,
        fee_type: values.arrangement,
        title: values.title,
        payment_terms: values.terms,
        notes: values.notes,
      };
    else if (kind === 'expenses')
      body = {
        ...links,
        amount: values.amount,
        expense_date: values.date,
        category: values.category,
        description: values.description,
        payment_method: values.method,
        vendor: values.vendor,
        reference: values.reference,
        document_id: values.document_id || null,
        notes: values.notes,
        status: values.status,
      };
    else
      body = {
        ...links,
        agreement_id: values.agreement_id || null,
        amount: values.amount,
        payment_date: values.date,
        method: values.method,
        status: values.status,
        reference: values.reference,
        description: values.description,
        notes: values.notes,
      };
    const submit = async () => {
      if (sending.current) return;
      sending.current = true;
      if (!key.current) key.current = `payment-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      setBusy(true);
      setError('');
      try {
        const row = await financeApi.create(kind, body, kind === 'payments' ? key.current : undefined);
        void qc.invalidateQueries({ queryKey: ['finance'] });
        void qc.invalidateQueries({ queryKey: ['finance-report'] });
        router.replace({ pathname: '/finance/detail', params: { kind, id: row.id } });
      } catch (e) {
        setError(friendlyError(e));
      } finally {
        sending.current = false;
        setBusy(false);
      }
    };
    if (kind === 'payments' && values.status === 'received')
      Alert.alert(t('work.confirm'), t('work.confirmReceived'), [
        { text: t('work.cancel'), style: 'cancel' },
        { text: t('work.confirm'), onPress: () => void submit() },
      ]);
    else await submit();
  }
  return (
    <Screen title={t('work.add')} back>
      {error && <Notice message={error} />}
      <AppText>{t('work.client')}</AppText>
      <ChoiceChips
        value={form.client_id}
        onChange={(v) => {
          setValue('client_id', v);
          setValue('agreement_id', '');
        }}
        options={[
          { value: '', label: t('work.none') },
          ...(clients.data?.items ?? []).map((c) => ({ value: c.id, label: c.full_name })),
        ]}
      />
      <AppText>{t('work.case')}</AppText>
      <ChoiceChips
        value={form.case_id}
        onChange={(v) => {
          setValue('case_id', v);
          setValue('agreement_id', '');
        }}
        options={[
          { value: '', label: t('work.none') },
          ...(cases.data?.items ?? []).map((c) => ({
            value: c.id,
            label: c.case_number + ' · ' + c.case_title,
          })),
        ]}
      />
      {(kind === 'payments' || kind === 'invoices') && (
        <>
          <AppText>{t('work.agreement')}</AppText>
          <ChoiceChips
            value={form.agreement_id}
            onChange={(v) => setValue('agreement_id', v)}
            options={[
              { value: '', label: t('work.none') },
              ...(agreements.data ?? [])
                .filter((a) => a.client_id === form.client_id && (a.case_id ?? '') === form.case_id)
                .map((a) => ({ value: a.id, label: `${a.description ?? a.id.slice(0, 8)} · ₹${a.amount}` })),
            ]}
          />
        </>
      )}
      {field('date', 'date')}
      {kind !== 'invoices' && field('amount', 'amount')}
      {kind !== 'invoices' && field('description', 'description')}
      {kind !== 'invoices' && field('notes', 'notes')}
      {kind === 'fee-agreements' && (
        <>
          {field('title', 'title')}
          {field('terms', 'terms')}
          <AppText>{t('work.feeType')}</AppText>
          <ChoiceChips
            value={form.arrangement}
            onChange={(v) => setValue('arrangement', v)}
            options={['fixed', 'stage', 'consultation', 'hourly', 'custom'].map((value) => ({
              value,
              label: t(`work.${value}`, value),
            }))}
          />
        </>
      )}
      {(kind === 'invoices' || kind === 'fee-agreements') && field('due', 'due')}
      {kind === 'payments' && (
        <>
          <AppText>{t('work.method')}</AppText>
          <ChoiceChips
            value={form.method}
            onChange={(v) => setValue('method', v)}
            options={['Cash', 'UPI', 'Bank transfer', 'Cheque', 'Card', 'Other'].map((v) => ({
              value: v,
              label: t(`work.${v}`, v),
            }))}
          />
          <AppText>{t('work.status')}</AppText>
          <ChoiceChips
            value={form.status}
            onChange={(v) => setValue('status', v)}
            options={['pending', 'received', 'failed'].map((v) => ({ value: v, label: t(`work.${v}`, v) }))}
          />
          {field('reference', 'reference')}
        </>
      )}
      {kind === 'expenses' && (
        <>
          {field('category', 'category')}
          {field('vendor', 'vendor')}
          {field('reference', 'reference')}
          <AppText>{t('work.method')}</AppText>
          <ChoiceChips
            value={form.method}
            onChange={(v) => setValue('method', v)}
            options={['Cash', 'UPI', 'Bank transfer', 'Cheque', 'Card', 'Other'].map((value) => ({
              value,
              label: t(`work.${value}`, value),
            }))}
          />
          <AppText>{t('work.status')}</AppText>
          <ChoiceChips
            value={form.status}
            onChange={(v) => setValue('status', v)}
            options={['draft', 'confirmed'].map((value) => ({ value, label: t(`work.${value}`, value) }))}
          />
          <AppText>{t('work.attachment')}</AppText>
          <ChoiceChips
            value={form.document_id}
            onChange={(v) => setValue('document_id', v)}
            options={[
              { value: '', label: t('work.none') },
              ...(documents.data ?? []).map((value) => ({ value: value.id, label: value.document_name })),
            ]}
          />
        </>
      )}
      {kind === 'invoices' && (
        <>
          {field('terms', 'terms')}
          {fields.map((f, index) => (
            <Controller
              key={f.id}
              control={control}
              name={`lines.${index}`}
              render={({ field: line }) => (
                <>
                  <TextField
                    label={t('work.description')}
                    value={line.value.description}
                    onChangeText={(v) => line.onChange({ ...line.value, description: v })}
                  />
                  <TextField
                    label={t('work.quantity')}
                    value={line.value.quantity}
                    onChangeText={(v) => line.onChange({ ...line.value, quantity: v })}
                  />
                  <TextField
                    label={t('work.unitPrice')}
                    value={line.value.unit_price}
                    onChangeText={(v) => line.onChange({ ...line.value, unit_price: v })}
                  />
                  {fields.length > 1 && (
                    <Button label={t('work.discard')} variant="secondary" onPress={() => remove(index)} />
                  )}
                </>
              )}
            />
          ))}
          <Button
            label={t('work.addLine')}
            variant="secondary"
            onPress={() => append({ description: '', quantity: '1', unit_price: '' })}
          />
        </>
      )}
      <Button label={t('work.save')} loading={busy} onPress={() => void handleSubmit(save)()} />
    </Screen>
  );
}
