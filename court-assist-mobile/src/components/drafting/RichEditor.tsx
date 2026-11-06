import { useEffect, useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { WebView } from 'react-native-webview';
import { useTheme } from '../../theme/tokens';
export type EditorProps = {
  initialHtml: string;
  onChange: (html: string) => void;
  replacement?: { html: string; key: number };
  preview?: boolean;
};
function jsString(value: string) {
  return JSON.stringify(value).replaceAll('<', '\\u003c');
}
export function RichEditor({ initialHtml, onChange, replacement, preview = false }: EditorProps) {
  const { t } = useTranslation();
  const labels = {
    bold: t('work.bold'),
    italic: t('work.italic'),
    underline: t('work.underline'),
    formatBlock: t('work.heading'),
    insertOrderedList: t('work.numbered'),
    insertUnorderedList: t('work.bullets'),
    justifyLeft: t('work.left'),
    justifyCenter: t('work.center'),
    justifyRight: t('work.right'),
    justifyFull: t('work.justify'),
    undo: t('work.undo'),
    redo: t('work.redo'),
    insertHTML: t('work.insertContent'),
  };
  const web = useRef<WebView<object>>(null);
  const theme = useTheme();
  const [source] = useState(() => ({
    html: `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline';"><style>body{margin:0;background:${theme.colors.surface};color:${theme.colors.text};font:17px/1.6 serif}#tools{position:sticky;top:0;background:#eef1f4;padding:8px;display:flex;flex-wrap:wrap;gap:6px}button{min-width:44px;min-height:44px;border:1px solid #aaa;border-radius:5px;background:white;color:#172a42}#editor{min-height:420px;padding:16px;outline:none}table{border-collapse:collapse;width:100%}td,th{border:1px solid #777;padding:7px}.page-break{border-top:2px dashed #777;page-break-after:always}</style></head><body><div id="tools" ${preview ? 'hidden' : ''}></div><div id="editor" contenteditable="${!preview}"></div><script>
const editor=document.getElementById('editor');const tools=document.getElementById('tools');
function emit(){window.ReactNativeWebView.postMessage(JSON.stringify({html:editor.innerHTML}));}
function clean(value){const root=document.createElement('div');root.innerHTML=value;root.querySelectorAll('script,style,iframe,object,embed,link,meta,img,svg').forEach(n=>n.remove());root.querySelectorAll('*').forEach(n=>{Array.from(n.attributes).forEach(a=>{if(!['style','class','colspan','rowspan'].includes(a.name))n.removeAttribute(a.name);});});return root.innerHTML;}
window.replaceContent=function(value){editor.innerHTML=clean(value);emit();};
const original=${jsString(initialHtml)};editor.innerHTML=/<[a-z][\\s\\S]*>/i.test(original)?original:'<p>'+original.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\\n/g,'<br>')+'</p>';editor.innerHTML=clean(editor.innerHTML);
const commands=[['B','bold'],['I','italic'],['U','underline'],['H1','formatBlock','h1'],['H2','formatBlock','h2'],['¶','formatBlock','p'],['1.','insertOrderedList'],['•','insertUnorderedList'],['←','justifyLeft'],['↔','justifyCenter'],['→','justifyRight'],['≋','justifyFull'],['↶','undo'],['↷','redo'],['▦','insertHTML','<table><tr><td><br></td><td><br></td></tr><tr><td><br></td><td><br></td></tr></table><p><br></p>'],['↡','insertHTML','<div class="page-break" style="page-break-after:always"><br></div><p><br></p>']];
const labels=${JSON.stringify(labels)};if(!${preview})commands.forEach(([label,command,value])=>{const b=document.createElement('button');b.textContent=label;b.setAttribute('aria-label',labels[command]||label);b.onmousedown=e=>e.preventDefault();b.onclick=()=>{editor.focus();document.execCommand(command,false,value);emit();};tools.appendChild(b);});
editor.addEventListener('input',emit);editor.addEventListener('paste',e=>{e.preventDefault();document.execCommand('insertText',false,e.clipboardData.getData('text/plain'));emit();});
</script></body></html>`,
  }));
  useEffect(() => {
    if (replacement)
      web.current?.injectJavaScript(`window.replaceContent(${jsString(replacement.html)});true;`);
  }, [replacement]);
  return (
    <WebView<object>
      ref={web}
      source={source}
      style={{ height: 600, backgroundColor: theme.colors.surface }}
      originWhitelist={['about:blank']}
      onShouldStartLoadWithRequest={(request) => request.url === 'about:blank'}
      javaScriptEnabled
      onMessage={(event) => {
        try {
          const data = JSON.parse(event.nativeEvent.data);
          if (typeof data.html === 'string') onChange(data.html);
        } catch {
          /* Ignore non-editor messages. */
        }
      }}
    />
  );
}
