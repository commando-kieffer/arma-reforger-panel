// Gameplay settings card: game.gameProperties and operating in config.json.

import { t } from '../i18n.js';
import { postJson } from './api.js';
import { setBusy, setLog } from './activity.js';
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
  } catch (e) { setLog(t('common.connection_error'), 'error'); }
}

async function saveGameplay() {
  setBusy(true);
  setLog(t('gameplay.saving'), 'info');
  try {
    const r = await postJson('/api/gameplay', readFields(card()));
    const d = await r.json();
    if (d.ok) {
      setLog(t('gameplay.saved'), 'ok');
      document.getElementById('gameplay-restart-notice').classList.toggle('visible', !!d.restart_required);
      await loadGameplay();
    } else {
      setLog(t('common.save_failed', { error: d.error || t('common.unknown') }), 'error');
    }
  } catch (e) { setLog(t('common.connection_error'), 'error'); }
  setBusy(false);
}

export function initGameplay() {
  document.getElementById('btn-gameplay-save').addEventListener('click', saveGameplay);
  document.getElementById('input-battleye').addEventListener('change', updateBattleyeWarning);
  loadGameplay();
}
