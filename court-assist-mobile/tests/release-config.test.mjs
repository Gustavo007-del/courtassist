import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import appConfig from '../app.config.js';

const read = file => readFileSync(new URL(file, import.meta.url), 'utf8');
const config = JSON.parse(read('../app.json')).expo;

test('release requires HTTPS and cannot opt in to development cleartext traffic', () => {
  const previous = { ...process.env };
  try {
    process.env.COURT_ASSIST_RELEASE = '1';
    process.env.COURT_ASSIST_ALLOW_HTTP_DEV = '1';
    process.env.EXPO_PUBLIC_API_URL = 'http://api.example.test';
    assert.throws(() => appConfig({ config }), /HTTPS/);
    process.env.EXPO_PUBLIC_API_URL = 'https://api.example.test';
    const result = appConfig({ config });
    assert.equal(result.plugins.find(plugin => plugin[0] === 'expo-build-properties')[1].android.usesCleartextTraffic, false);
    assert.equal(result.android.allowBackup, false);
    assert.ok(result.android.blockedPermissions.includes('android.permission.RECORD_AUDIO'));
  } finally { process.env = previous; }
});

test('all private route groups are named in the protected stack', () => {
  const layout = read('../src/app/_layout.tsx');
  assert.match(layout, /<Stack\.Protected guard=\{signedIn\}>\s*\{privateRoutes\.map/);
  const groupNames = layout.match(/const privateRoutes = \[([^\]]+)\]/)[1];
  for (const group of readdirSync(new URL('../src/app/', import.meta.url), { withFileTypes: true })) {
    if (!group.isDirectory() || group.name === '(auth)') continue;
    assert.ok(existsSync(new URL('../src/app/' + group.name + '/_layout.tsx', import.meta.url)), group.name);
    assert.ok(groupNames.includes("'" + group.name + "'"), group.name);
  }
});

test('release package identity and configured artwork are present', () => {
  const eas = JSON.parse(read('../eas.json'));
  assert.equal(config.android.package, 'in.courtassist.advocate');
  assert.equal(eas.build.production.android.buildType, 'app-bundle');
  assert.equal(eas.build.production.autoIncrement, true);
  for (const asset of [config.icon, config.android.adaptiveIcon.foregroundImage,
    config.plugins.find(plugin => plugin[0] === 'expo-splash-screen')[1].image]) {
    assert.ok(existsSync(new URL('../' + asset, import.meta.url)), asset);
  }
});

