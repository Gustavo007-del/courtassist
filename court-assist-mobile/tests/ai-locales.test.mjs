import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

function messages(locale) {
  const source = new URL('../src/i18n/locales/' + locale + '.json', import.meta.url);
  return flatten(JSON.parse(readFileSync(source, 'utf8')).ai);
}

function flatten(group, prefix = '') {
  return Object.fromEntries(Object.entries(group).flatMap(([key, value]) => {
    const path = prefix + key;
    return typeof value === 'string' ? [[path, value]] : Object.entries(flatten(value, path + '.'));
  }));
}

test('English and Malayalam AI screens preserve locale keys and interpolation values', () => {
  const english = messages('en');
  const malayalam = messages('ml');
  assert.deepEqual(Object.keys(malayalam).sort(), Object.keys(english).sort());
  const variables = value => [...value.matchAll(/{{\s*(\w+)\s*}}/g)].map(match => match[1]).sort();
  for (const [key, text] of Object.entries(malayalam)) {
    assert.match(text, /[\u0d00-\u0d7f]/u, key);
    assert.deepEqual(variables(text), variables(english[key]), key);
  }
});
