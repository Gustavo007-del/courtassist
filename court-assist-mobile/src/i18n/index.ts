import { createInstance } from 'i18next';
import { initReactI18next } from 'react-i18next';
import * as SecureStore from 'expo-secure-store';
import en from './locales/en.json';
import ml from './locales/ml.json';

export type Language = 'en' | 'ml';
const i18n = createInstance();
i18n.use(initReactI18next).init({ resources: { en: { translation: en }, ml: { translation: ml } }, lng: 'en', fallbackLng: 'en', interpolation: { escapeValue: false } });

export async function loadLanguage() {
  const saved = await SecureStore.getItemAsync('courtassist.language');
  if (saved === 'en' || saved === 'ml') await i18n.changeLanguage(saved);
}

export async function setLanguage(language: Language) {
  await i18n.changeLanguage(language);
  await SecureStore.setItemAsync('courtassist.language', language);
}

export default i18n;
