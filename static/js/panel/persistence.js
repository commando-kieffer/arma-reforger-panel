// Persistence card: save mode and settings, and the session save files on
// disk. The settings are saved from the save bar (changes.js).

import { t, tn } from '../i18n.js';
import { postJson } from './api.js';
import { setBusy, setLog } from './activity.js';
import { markSaved, trackSection } from './changes.js';
import { fillFields, readFields } from './fields.js';
import { escHtml, fmtAge, fmtBytes } from './format.js';

const BUCKETS = ['game', 'playersave', 'settings'];

function card() {
  return document.getElementById('persistence-card');
}

function modeSelect() {
  return document.getElementById('input-persist-mode');
}

// The settings are only sent, and checked, in custom mode.
function readPersistence() {
  const mode = modeSelect().value;
  return mode === 'custom' ? { mode, ...readFields(card()) } : { mode };
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
    markSaved('persistence');
  } catch (e) { /* panel is the source of truth; silent on transient errors */ }
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
  trackSection('persistence', {
    card: card(),
    read: readPersistence,
    reload: fetchPersistence,
    restartNotice: document.getElementById('persist-restart-notice'),
  });
  modeSelect().addEventListener('change', updateFieldsState);
  document.getElementById('btn-persist-flush').addEventListener('click', flushPersistence);
}
