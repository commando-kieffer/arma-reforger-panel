// Persistence card: autosave settings and the session save files on disk.

import { postJson } from './api.js';
import { setBusy, setLog } from './activity.js';
import { escHtml, fmtAge, fmtBytes } from './format.js';

function renderPersistStats(s) {
  const el = document.getElementById('persist-stats');
  if (!s.saves) { el.textContent = ''; return; }
  const { path, exists, total, buckets } = s.saves;
  if (!exists || !total || total.count === 0) {
    el.innerHTML = `No saves yet under <code>${escHtml(path || '')}</code>.`;
    return;
  }
  const bucketLabel = { game: 'World session', playersave: 'Player saves', settings: 'Settings' };
  const rows = ['game', 'playersave', 'settings']
    .filter(k => buckets && buckets[k] && buckets[k].count > 0)
    .map(k => `${bucketLabel[k]}: ${buckets[k].count} file${buckets[k].count === 1 ? '' : 's'}, ${fmtBytes(buckets[k].bytes)} (newest ${fmtAge(buckets[k].newest)})`)
    .join(' · ');
  el.innerHTML = `<code>${escHtml(path)}</code><br>${rows || 'empty'}`;
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
  setLog('Saving persistence settings...', 'info');
  try {
    const r = await postJson('/api/persistence', { enabled, autoSaveInterval: interval, hiveId: hive });
    const d = await r.json();
    if (d.ok) {
      setLog(enabled ? 'Persistence enabled' : 'Persistence disabled', 'ok');
      document.getElementById('persist-restart-notice').classList.toggle('visible', !!d.restart_required);
      await fetchPersistence();
    } else {
      setLog('Save failed: ' + (d.error || 'unknown'), 'error');
    }
  } catch (e) { setLog('Connection error', 'error'); }
  setBusy(false);
}

async function flushPersistence() {
  if (!confirm('Delete the world-session save (.save/game) and per-player saves (.save/playersave)? Server settings are kept. The next launch starts a fresh world. This cannot be undone.')) return;
  setBusy(true);
  setLog('Flushing saves...', 'info');
  try {
    const r = await postJson('/api/persistence/flush', {});
    const d = await r.json();
    if (d.ok) {
      setLog(`Removed ${d.removed} save file${d.removed === 1 ? '' : 's'}`, 'ok');
      renderPersistStats(d);
    } else {
      setLog('Flush failed: ' + (d.error || 'unknown'), 'error');
    }
  } catch (e) { setLog('Connection error', 'error'); }
  setBusy(false);
}

export function initPersistence() {
  document.getElementById('btn-persist-save').addEventListener('click', savePersistence);
  document.getElementById('btn-persist-flush').addEventListener('click', flushPersistence);
}
