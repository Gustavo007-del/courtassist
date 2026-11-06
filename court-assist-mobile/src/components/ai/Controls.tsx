import { useState } from 'react';
import { Switch, View } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { aiApi, sourceKinds, type ContextRow, type Preferences, type SourceKind } from '../../services/ai-api';
import { AppText } from '../common/AppText';
import { Button } from '../common/Button';
import { Card } from '../common/Card';
import { ChoiceChips } from '../common/ChoiceChips';
import { ErrorState } from '../common/ErrorState';
import { LoadingSkeleton } from '../common/LoadingSkeleton';

export function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (value: boolean) => void }) {
  return <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 50 }}>
    <AppText style={{ flex: 1 }}>{label}</AppText>
    <Switch accessibilityLabel={label} value={value} onValueChange={onChange} />
  </View>;
}

export function ExternalConsent({ prefs, allowed, onChange }: {
  prefs: Preferences; allowed: boolean; onChange: (value: boolean) => void;
}) {
  const { t } = useTranslation();
  if (!prefs.external_provider) return null;
  return <Card>
    <AppText>{t('ai.externalNotice', { provider: prefs.provider, model: prefs.model })}</AppText>
    <AppText>{prefs.provider_policy}</AppText>
    {prefs.external
      ? <Toggle label={t('ai.sendThisRequest')} value={allowed} onChange={onChange} />
      : <AppText>{t('ai.externalOff')}</AppText>}
  </Card>;
}

export function Pagination({ offset, hasMore, setOffset }: {
  offset: number; hasMore: boolean; setOffset: (value: number) => void;
}) {
  const { t } = useTranslation();
  return <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
    {offset > 0 && <Button label={t('ai.previous')} variant="text" onPress={() => setOffset(Math.max(0, offset - 20))} />}
    {hasMore && <Button label={t('ai.next')} variant="text" onPress={() => setOffset(offset + 20)} />}
  </View>;
}

export function ContextPicker({ caseId, only, selected, onPick }: {
  caseId?: string; only?: SourceKind; selected: ContextRow[]; onPick: (row: ContextRow) => void;
}) {
  const { t } = useTranslation();
  const [category, setCategory] = useState<SourceKind>(caseId ? 'case' : 'document');
  const [offset, setOffset] = useState(0);
  const kind = only ?? category;
  const query = useQuery({
    queryKey: ['ai', 'context', kind, caseId, offset],
    queryFn: () => aiApi.context(kind, offset, caseId),
  });
  return <Card>
    {!only && <ChoiceChips value={kind} options={sourceKinds.map(value => ({ value, label: t(`ai.sources.${value}`) }))}
      onChange={value => { setCategory(value); setOffset(0); }} />}
    {query.isPending ? <LoadingSkeleton rows={2} /> : query.isError
      ? <ErrorState message={t('work.error')} retry={() => void query.refetch()} />
      : <>
        {!query.data.items.length && <AppText>{t('ai.emptySources')}</AppText>}
        {query.data.items.map(row => <Button key={row.id} variant="secondary"
          label={`${selected.some(item => item.kind === row.kind && item.id === row.id) ? '✓ ' : ''}${row.title}${row.date ? ' · ' + row.date : ''}`}
          onPress={() => onPick(row)} />)}
        <Pagination offset={offset} hasMore={offset + 20 < query.data.total} setOffset={setOffset} />
      </>}
  </Card>;
}

