import type { Preferences } from '../features/auth/types';

export function formatStoredDate(value: string, format: Preferences['date_format'] = 'DD/MM/YYYY'): string {
  const [year, month, day] = value.slice(0, 10).split('-');
  if (!year || !month || !day) return value;
  if (format === 'YYYY-MM-DD') return `${year}-${month}-${day}`;
  if (format === 'MM/DD/YYYY') return `${month}/${day}/${year}`;
  return `${day}/${month}/${year}`;
}

export function formatTimestamp(value: string, preferences: Preferences | null, language: string): string {
  return new Date(value).toLocaleString(language === 'ml' ? 'ml-IN' : 'en-IN', {
    timeZone: preferences?.timezone ?? 'Asia/Kolkata', day: 'numeric', month: 'short', year: 'numeric',
    hour: 'numeric', minute: '2-digit', hour12: preferences?.time_format !== '24',
  });
}
