import test from 'node:test';
import assert from 'node:assert/strict';
import { Buffer } from 'node:buffer';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';
import { randomUUID, randomBytes, createCipheriv, createDecipheriv, createHash } from 'node:crypto';
import ts from 'typescript';

function load(name, modules) {
  const source = fs.readFileSync(new URL('../src/features/sync/' + name + '.ts', import.meta.url), 'utf8');
  const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const exports = {};
  new Function('require', 'exports', js)(key => {
    assert.ok(Object.hasOwn(modules, key), key);
    return modules[key];
  }, exports);
  return exports;
}

const policy = load('policy', {});
const secureStore = () => {
  const data = new Map();
  return {
    getItemAsync: async key => data.get(key) ?? null,
    setItemAsync: async (key, value) => { data.set(key, value); },
    deleteItemAsync: async key => { data.delete(key); },
  };
};
const expoCrypto = {
  randomUUID,
  CryptoDigestAlgorithm: { SHA256: 'sha256' },
  digestStringAsync: async (algorithm, value) => createHash(algorithm).update(value).digest('hex'),
  AESEncryptionKey: {
    generate: async () => { const key = randomBytes(32); return { key, encoded: async () => key.toString('base64') }; },
    import: async value => ({ key: Buffer.from(value, 'base64') }),
  },
  AESSealedData: { fromCombined: value => Buffer.from(value, typeof value === 'string' ? 'base64' : undefined) },
  aesEncryptAsync: async (bytes, key, { additionalData }) => {
    const nonce = randomBytes(12);
    const cipher = createCipheriv('aes-256-gcm', key.key, nonce);
    cipher.setAAD(additionalData);
    const data = Buffer.concat([nonce, cipher.update(bytes), cipher.final(), cipher.getAuthTag()]);
    return { combined: async encoding => encoding === 'base64' ? data.toString('base64') : data };
  },
  aesDecryptAsync: async (bytes, key, { additionalData }) => {
    const cipher = createDecipheriv('aes-256-gcm', key.key, bytes.subarray(0, 12));
    cipher.setAAD(additionalData);
    cipher.setAuthTag(bytes.subarray(-16));
    return Buffer.concat([cipher.update(bytes.subarray(12, -16)), cipher.final()]);
  },
};

function open(filename, secure) {
  const database = new DatabaseSync(filename);
  const db = {
    execAsync: async sql => database.exec(sql),
    runAsync: async (sql, ...args) => database.prepare(sql).run(...args),
    getFirstAsync: async (sql, ...args) => database.prepare(sql).get(...args) ?? null,
    getAllAsync: async (sql, ...args) => database.prepare(sql).all(...args),
    withExclusiveTransactionAsync: async fn => {
      database.exec('BEGIN IMMEDIATE');
      try { await fn(db); database.exec('COMMIT'); }
      catch (error) { database.exec('ROLLBACK'); throw error; }
    },
  };
  const crypto = load('crypto', { 'expo-crypto': expoCrypto, 'expo-secure-store': secure });
  const schema = load('schema', { '../../database': { openLocalDatabase: async () => db } });
  const repository = load('repository', {
    'react-native': { Platform: { OS: 'android' } }, 'expo-crypto': expoCrypto,
    './schema': schema, './crypto': crypto, './policy': policy,
  });
  return { db, database, crypto, schema, repository };
}

test('encrypted case and linked diary queue survive SQLite restart with stable IDs', async () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'courtassist-sync-test-'));
  const filename = path.join(folder, 'offline.db');
  const secure = secureStore();
  const owner = randomUUID();
  const caseId = randomUUID();
  const diaryId = randomUUID();
  let local = open(filename, secure);
  try {
    await local.repository.enable(owner, { id: owner, full_name: 'Private advocate' }, Date.now() + policy.offlineLifetime);
    const created = await local.repository.enqueue(owner, 'case', 'create', caseId, {
      case_title: 'Confidential കേസ്', case_number: 'OS 4/2026',
    });
    await local.repository.enqueue(owner, 'diary', 'create', diaryId, { case_id: caseId, content: 'Private മലയാളം note' });
    assert.equal(created.optimistic.id, caseId);
    const encrypted = local.database.prepare('SELECT body FROM sync_entities WHERE id=?').get(diaryId).body;
    assert.ok(!encrypted.includes('Private'));
    await assert.rejects(() => local.crypto.unpack(owner, 'record:diary:' + caseId, encrypted));
    local.database.close();
    local = open(filename, secure);
    const items = await local.repository.queue(owner);
    assert.equal(items.length, 2);
    assert.equal(items[0].operation.entity_id, caseId);
    assert.equal(items[1].operation.entity_id, diaryId);
    assert.deepEqual(items[1].operation.depends_on, [items[0].id]);
    assert.equal((await local.repository.getRecord(owner, 'diary', diaryId)).content, 'Private മലയാളം note');
    assert.deepEqual(await local.repository.queue(randomUUID()), []);
    assert.equal((await local.repository.restore(owner)).full_name, 'Private advocate');
    await local.repository.clearRecords(owner);
    assert.equal(await local.repository.restore(owner), null);
    assert.deepEqual(await local.repository.queue(owner), []);
    await assert.rejects(() => local.crypto.unpack(owner, 'record:diary:' + diaryId, encrypted));
  } finally {
    local.database.close();
    for (const name of ['offline.db', 'offline.db-wal', 'offline.db-shm']) {
      const target = path.join(folder, name);
      if (fs.existsSync(target)) fs.unlinkSync(target);
    }
    fs.rmdirSync(folder);
  }
});

test('incoming changes cannot replace pending content and acknowledged tombstones persist', async () => {
  const local = open(':memory:', secureStore());
  const owner = randomUUID(), id = randomUUID();
  try {
    await local.repository.enable(owner, { id: owner }, Date.now() + policy.offlineLifetime);
    const initial = { kind: 'draft', id, revision: '4', deleted: false, record: { id, content: 'Original', updated_at: '2026-01-01T12:00:00Z' } };
    await local.repository.applyPage(owner, [initial], '4');
    await local.repository.enqueue(owner, 'draft', 'update', id, { content: 'Offline revision' }, undefined, initial.record.updated_at);
    const remote = { ...initial, revision: '5', record: { id, content: 'Another device' } };
    await local.repository.applyPage(owner, [remote], '5');
    assert.equal((await local.repository.getRecord(owner, 'draft', id)).content, 'Offline revision');
    const [item] = await local.repository.queue(owner);
    assert.equal(item.operation.base_revision, '4');
    await local.repository.outcome(owner, item, 'conflict', { id: item.id, status: 'conflict', revision: '5', server: remote });
    assert.equal((await local.repository.queue(owner))[0].result.server.record.content, 'Another device');
    await local.repository.outcome(owner, item, 'discarded', { id: item.id, status: 'applied', server: remote });
    assert.equal((await local.repository.getRecord(owner, 'draft', id)).content, 'Another device');
    await local.repository.applyPage(owner, [{ ...remote, revision: '6', deleted: true, record: null }], '6');
    await local.repository.applyPage(owner, [initial], '4');
    assert.equal(await local.repository.getRecord(owner, 'draft', id), null);
    assert.equal((await local.repository.control(owner)).cursor, '6');
  } finally { local.database.close(); }
});

test('interrupted upload keeps the same operation and remains queued until file confirmation', async () => {
  const local = open(':memory:', secureStore());
  const owner = randomUUID(), id = randomUUID(), file = randomUUID();
  const pushes = [];
  const removed = [];
  let attempts = 0;
  const state = { connected: true };
  class ApiError extends Error {}
  const pending = { kind: 'document', id, revision: '1', deleted: false, record: { id, storage_status: 'upload_pending' } };
  const stored = { ...pending, revision: '2', record: { id, storage_status: 'cloud_stored' } };
  const engine = load('engine', {
    '../../services/api': { ApiError, networkRequest: async (url, init) => {
      if (url === '/sync/push') {
        const [operation] = JSON.parse(init.body).operations;
        pushes.push(operation.id);
        return { results: [{ id: operation.id, status: 'applied', revision: '1', server: pending }] };
      }
      if (url === '/sync/pull') return { changes: [stored], cursor: '2', has_more: false };
      if (url.startsWith('/sync/records/')) return stored;
      return {};
    } },
    '../../store/auth-store': { useAuthStore: { getState: () => ({ user: { id: owner } }) } },
    './files': { finishUpload: (_owner, blob) => removed.push(blob), transfer: async () => {
      attempts++;
      if (attempts === 1) throw new Error('simulated file transport failure');
    } },
    './policy': policy, './repository': local.repository, './schema': local.schema,
    './state': { useSyncState: { getState: () => state, setState: patch => Object.assign(state, patch) } },
  });
  try {
    await local.repository.enable(owner, { id: owner }, Date.now() + policy.offlineLifetime);
    const queued = await local.repository.enqueue(owner, 'document', 'create', id, { original_filename: 'scan.pdf' }, file);
    await engine.syncNow(owner, true);
    const [retry] = await local.repository.queue(owner);
    assert.equal(retry.status, 'retry');
    assert.equal(retry.operation.id, queued.operation.id);
    assert.deepEqual(removed, []);
    assert.equal((await local.repository.getRecord(owner, 'document', id)).storage_status, 'upload_pending');
    await local.repository.retry(owner, retry.id);
    await engine.syncNow(owner, true);
    assert.deepEqual(pushes, [queued.operation.id, queued.operation.id]);
    assert.deepEqual(removed, [file]);
    assert.deepEqual(await local.repository.queue(owner), []);
    assert.equal((await local.repository.getRecord(owner, 'document', id)).storage_status, 'cloud_stored');
  } finally { local.database.close(); }
});

test('session age and safe replay policy exclude revoked leases and unapproved requests', () => {
  assert.equal(policy.canRestore(100, 200, 150), true);
  assert.equal(policy.canRestore(100, 200, 200), false);
  assert.equal(policy.canRestore(100, 200, 99), false);
  assert.equal(policy.canRestore(100, 100 + policy.offlineLifetime * 2, 150), false);
  assert.equal(policy.nextQueueState('retryable', 5), 'failed');
  assert.equal(policy.writeRoute('/ai/ask', 'POST'), null);
  assert.equal(policy.writeRoute('/payments/' + randomUUID() + '/confirm', 'POST'), null);
  assert.equal(policy.writeRoute('/documents/upload-url', 'POST'), null);
  assert.equal(policy.newerOrEqual('9007199254740993', '9007199254740994'), false);
});

