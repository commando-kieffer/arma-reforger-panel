// Gameplay settings card: game.gameProperties and operating in config.json.
// Saved from the save bar (changes.js).

import { t } from '../i18n.js';
import { setLog } from './activity.js';
import { markSaved, trackSection } from './changes.js';
import { fillFields, readFields } from './fields.js';

function card() {
  return document.getElementById('gameplay-card');
}

function updateBattleyeWarning() {
  document.getElementById('battleye-warning').hidden = document.getElementById('input-battleye').value !== 'false';
}

async function loadGameplay() {
  try {
    const r = await fetch('/api/gameplay');
    if (r.status === 401) { window.location.href = '/login'; return; }
    const d = await r.json();
    if (!d.ok) { setLog(t('common.error', { error: d.error || t('common.unknown') }), 'error'); return; }
    fillFields(card(), d);
    document.getElementById('fast-validation-warning').hidden = d.fast_validation;
    updateBattleyeWarning();
    markSaved('gameplay');
  } catch (e) { setLog(t('common.connection_error'), 'error'); }
}

export function initGameplay() {
  trackSection('gameplay', {
    card: card(),
    read: () => readFields(card()),
    reload: loadGameplay,
    restartNotice: document.getElementById('gameplay-restart-notice'),
  });
  document.getElementById('input-battleye').addEventListener('change', updateBattleyeWarning);
  loadGameplay();
}
