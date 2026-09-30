// Persistence card: save mode and settings, and the session save files on disk.

import { t, tn } from '../i18n.js';
import { postJson } from './api.js';
import { setBusy, setLog } from './activity.js';
import { fillFields, readFields } from './fields.js';
import { escHtml, fmtAge, fmtBytes } from './format.js';

const BUCKETS = ['game', 'playersave', 'settings'];

function card() {
  return document.getElementById('persistence-card');
}

function modeSelect() {
  return document.getElementById('input-persist-mode');
}

// The settings only apply in custom mode; in the other modes they show the
// values the server uses (defaults, or the saved block while disabled).
function updateFieldsState() {
  const custom = modeSelect().value === 'custom';
  card().querySelectorAll('[data-field]').forEach(el => { el.disabled = !custom; });
}

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
    modeSelect().value = d.mode;
    fillFields(card(), d);
    updateFieldsState();
    renderPersistStats(d);
  } catch (e) { /* panel is the source of truth; silent on transient errors */ }
}

async function savePersistence() {
  const mode = modeSelect().value;
  // Settings are only sent, and checked, in custom mode.
  const body = mode === 'custom' ? { mode, ...readFields(card()) } : { mode };
  setBusy(true);
  setLog(t('persistence.saving'), 'info');
  try {
    const r = await postJson('/api/persistence', body);
    const d = await r.json();
    if (d.ok) {
      setLog(t('persistence.saved'), 'ok');
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
  modeSelect().addEventListener('change', updateFieldsState);
  document.getElementById('btn-persist-save').addEventListener('click', savePersistence);
  document.getElementById('btn-persist-flush').addEventListener('click', flushPersistence);
}
