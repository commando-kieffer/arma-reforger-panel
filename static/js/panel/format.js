import { t } from '../i18n.js';

const BYTE_UNITS = ['unit_b', 'unit_kb', 'unit_mb', 'unit_gb'];

export function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

export function fmtBytes(n) {
  n = n || 0;
  let i = 0;
  while (n >= 1024 && i < BYTE_UNITS.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${t('format.' + BYTE_UNITS[i])}`;
}

export function fmtAge(ts) {
  if (!ts) return t('format.never');
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60)    return t('format.seconds_ago', { n: s });
  if (s < 3600)  return t('format.minutes_ago', { n: Math.floor(s / 60) });
  if (s < 86400) return t('format.hours_ago', { n: Math.floor(s / 3600) });
  return t('format.days_ago', { n: Math.floor(s / 86400) });
}
