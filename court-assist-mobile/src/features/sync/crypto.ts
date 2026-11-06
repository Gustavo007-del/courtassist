import { AESEncryptionKey, AESSealedData, aesDecryptAsync, aesEncryptAsync } from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';

const keys = new Map<string, Promise<AESEncryptionKey>>();
const name = (owner: string) => `courtassist.offline.key.${owner}`;
const encoder = new TextEncoder();

async function key(owner: string, create: boolean) {
  let opening = keys.get(owner);
  if (!opening) {
    opening = (async () => {
      const stored = await SecureStore.getItemAsync(name(owner));
      if (stored) return AESEncryptionKey.import(stored, 'base64');
      if (!create) throw new Error('offline_key_unavailable');
      const generated = await AESEncryptionKey.generate();
      await SecureStore.setItemAsync(name(owner), await generated.encoded('base64'), {
        keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
      });
      return generated;
    })();
    keys.set(owner, opening);
    void opening.catch(() => { if (keys.get(owner) === opening) keys.delete(owner); });
  }
  return opening;
}

export async function seal(owner: string, purpose: string, bytes: Uint8Array) {
  return aesEncryptAsync(bytes, await key(owner, true), { additionalData: encoder.encode(owner + ':' + purpose) });
}

export async function unseal(owner: string, purpose: string, bytes: string | Uint8Array) {
  return aesDecryptAsync(AESSealedData.fromCombined(bytes), await key(owner, false), {
    additionalData: encoder.encode(owner + ':' + purpose),
  });
}

export async function pack(owner: string, purpose: string, value: unknown) {
  return (await seal(owner, purpose, encoder.encode(JSON.stringify(value)))).combined('base64');
}

export async function unpack<T>(owner: string, purpose: string, value: string): Promise<T> {
  return JSON.parse(new TextDecoder().decode(await unseal(owner, purpose, value))) as T;
}

export async function destroyKey(owner: string) {
  await keys.get(owner)?.catch(() => {});
  keys.delete(owner);
  await SecureStore.deleteItemAsync(name(owner));
}

