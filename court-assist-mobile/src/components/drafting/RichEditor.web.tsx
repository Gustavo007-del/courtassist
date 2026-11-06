import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { TextField } from '../common/TextField';
import type { EditorProps } from './RichEditor';
export function RichEditor({ initialHtml, onChange, replacement, preview }: EditorProps) {
  const { t } = useTranslation();
  const [state, setState] = useState({ value: initialHtml, key: replacement?.key });
  if (replacement && replacement.key !== state.key)
    setState({ value: replacement.html, key: replacement.key });
  return (
    <TextField
      label={t(preview ? 'work.sourcePreview' : 'work.sourceEditor')}
      value={state.value}
      onChangeText={(html) => {
        setState({ ...state, value: html });
        onChange(html);
      }}
      multiline
    />
  );
}
