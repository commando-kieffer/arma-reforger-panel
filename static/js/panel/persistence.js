// Persistence card: autosave settings and the session save files on disk.

import { t, tn } from '../i18n.js';
import { postJson } from './api.js';
import { setBusy, setLog } from './activity.js';
import { escHtml, fmtAge, fmtBytes } from './format.js';

const BUCKETS = ['game', 'playersave', 'settings'];

function renderPersistStats(s) {
  const el = document.getElementById('persist-stats');
  if (!s.saves) { el.textContent = ''; return; }
  const { path, exists, total, buckets } = s.saves;
  if (!exists || !total || total.count === 0) {
    el.innerHTML = t('persistence.no_saves', { path: `<code>${escHtml(path || '')}</code>` });
    return;
  }
  const rows = BUCKETS
    .filter(k => buckets && buckets[k] && buckets[k].count > 0)
    .map(k => tn('persistence.bucket_stats', buckets[k].count, {
      label: t('persistence.bucket_' + k),
      size: fmtBytes(buckets[k].bytes),
      age: fmtAge(buckets[k].newest),
    }))
    .join(' · ');
  el.innerHTML = `<code>${escHtml(path)}</code><br>${rows || t('persistence.empty')}`;
}

export async function fetchPersistence() {
  try {
    const r = await fetch('/api/persistence');
    if (!r.ok) return;
    const d = await r.json();
    document.getElementById('input-persist-enabled').value  = d.enabled ? 'true' : 'false';
    document.getElementById('input-persist-interval').value = d.autoSaveInterval;
    document.getElementById('input-persist-hive').value     = d.hiveId;
    renderPersistStats(d);
  } catch (e) { /* panel is the source of truth; silent on transient errors */ }
}

async function savePersistence() {
  const enabled  = document.getElementById('input-persist-enabled').value === 'true';
  const interval = parseInt(document.getElementById('input-persist-interval').value, 10);
  const hive     = parseInt(document.getElementById('input-persist-hive').value, 10);
  setBusy(true);
  setLog(t('persistence.saving'), 'info');
  try {
    const r = await postJson('/api/persistence', { enabled, autoSaveInterval: interval, hiveId: hive });
    const d = await r.json();
    if (d.ok) {
      setLog(enabled ? t('persistence.now_enabled') : t('persistence.now_disabled'), 'ok');
      document.getElementById('persist-restart-notice').classList.toggle('visible', !!d.restart_required);
      await fetchPersistence();
    } else {
      setLog(t('common.save_failed', { error: d.error || t('common.unknown') }), 'error');
    }
  } catch (e) { setLog(t('common.connection_error'), 'error'); }
  setBusy(false);
}

async function flushPersistence() {
  if (!confirm(t('persistence.confirm_flush'))) return;
  setBusy(true);
  setLog(t('persistence.flushing'), 'info');
  try {
    const r = await postJson('/api/persistence/flush', {});
    const d = await r.json();
    if (d.ok) {
      setLog(tn('persistence.flushed', d.removed), 'ok');
      renderPersistStats(d);
    } else {
      setLog(t('persistence.flush_failed', { error: d.error || t('common.unknown') }), 'error');
    }
  } catch (e) { setLog(t('common.connection_error'), 'error'); }
  setBusy(false);
}

export function initPersistence() {
  document.getElementById('btn-persist-save').addEventListener('click', savePersistence);
  document.getElementById('btn-persist-flush').addEventListener('click', flushPersistence);
}
