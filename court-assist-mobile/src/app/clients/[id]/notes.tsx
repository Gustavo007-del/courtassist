import { useState } from 'react';
import { Alert, Pressable, View } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppText } from '../../../components/common/AppText';
import { Button } from '../../../components/common/Button';
import { Card } from '../../../components/common/Card';
import { EmptyState } from '../../../components/common/EmptyState';
import { ErrorState } from '../../../components/common/ErrorState';
import { LoadingSkeleton } from '../../../components/common/LoadingSkeleton';
import { Notice } from '../../../components/common/Notice';
import { TextField } from '../../../components/common/TextField';
import { Screen } from '../../../components/layout/Screen';
import { clientApi, type ClientNote } from '../../../services/client-api';
import { useTheme } from '../../../theme/tokens';
import { friendlyError } from '../../../utils/errors';

export default function ClientNotes() {
  const { id } = useLocalSearchParams<{ id: string }>(); const { t } = useTranslation(); const theme = useTheme(); const cache = useQueryClient(); const [search, setSearch] = useState(''); const [editing, setEditing] = useState<ClientNote | null>(null); const [title, setTitle] = useState(''); const [content, setContent] = useState(''); const [saving, setSaving] = useState(false); const [formError, setFormError] = useState<string | null>(null);
  const query = useQuery({ queryKey: ['client-notes', id, search], queryFn: () => clientApi.notes(id, search.trim()), enabled: !!id });
  const reset = () => { setEditing(null); setTitle(''); setContent(''); setFormError(null); };
  const save = async () => { if (!title.trim() || !content.trim()) { setFormError(t('validation.required')); return; } setSaving(true); setFormError(null); try { if (editing) await clientApi.updateNote(id, editing.id, { title: title.trim(), content: content.trim() }); else await clientApi.addNote(id, { title: title.trim(), content: content.trim() }); reset(); await Promise.all([query.refetch(), cache.invalidateQueries({ queryKey: ['dashboard'] }), cache.invalidateQueries({ queryKey: ['activities'] })]); } catch (caught) { setFormError(friendlyError(caught)); } finally { setSaving(false); } };
  const edit = (note: ClientNote) => { setEditing(note); setTitle(note.title); setContent(note.content); };
  const remove = (note: ClientNote) => Alert.alert(t('clients.notes'), t('clients.deleteNote'), [{ text: t('cancel'), style: 'cancel' }, { text: t('clients.delete'), style: 'destructive', onPress: async () => { await clientApi.deleteNote(id, note.id); if (editing?.id === note.id) reset(); await query.refetch(); } }]);
  return <Screen title={t('clients.notes')} back refreshing={query.isRefetching} onRefresh={() => { void query.refetch(); }}>
    {formError && <Notice message={formError} />}<Card><AppText style={{ fontSize: 18, fontWeight: '800', marginBottom: 14 }}>{t(editing ? 'clients.editNote' : 'clients.addNote')}</AppText><TextField label={t('clients.noteTitle')} value={title} onChangeText={setTitle} autoCapitalize="words" /><TextField label={t('clients.noteContent')} value={content} onChangeText={setContent} multiline /><View style={{ gap: 8 }}><Button label={t('save')} loading={saving} onPress={() => { void save(); }} />{editing && <Button label={t('cancel')} variant="text" onPress={reset} />}</View></Card>
    <View style={{ marginTop: 20 }}><TextField label={t('clients.searchNotes')} value={search} onChangeText={setSearch} /></View>
    {query.isPending ? <LoadingSkeleton /> : query.isError ? <ErrorState message={friendlyError(query.error)} retry={() => { void query.refetch(); }} /> : !query.data?.length ? <EmptyState title={t('clients.noNotes')} body={t('clients.noNotesDetail')} /> : <View style={{ gap: 10 }}>{query.data.map((note) => <Card key={note.id}><AppText style={{ fontWeight: '800' }}>{note.title}</AppText><AppText style={{ color: theme.colors.muted, marginTop: 6 }}>{note.content}</AppText><AppText style={{ color: theme.colors.muted, fontSize: 12, marginTop: 8 }}>{new Date(note.updated_at).toLocaleString()}</AppText><View style={{ flexDirection: 'row', gap: 18, marginTop: 8 }}><Pressable onPress={() => edit(note)}><AppText style={{ color: theme.colors.accent, fontWeight: '700' }}>{t('clients.editNote')}</AppText></Pressable><Pressable onPress={() => remove(note)}><AppText style={{ color: theme.colors.danger, fontWeight: '700' }}>{t('clients.delete')}</AppText></Pressable></View></Card>)}</View>}
  </Screen>;
}
