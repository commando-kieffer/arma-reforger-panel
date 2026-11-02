// Server configuration card: name, scenario and passwords. Saved from the
// save bar (changes.js).

import { t, tn } from '../i18n.js';
import { postJson } from './api.js';
import { setLog } from './activity.js';
import { hasChanges, markSaved, trackSection } from './changes.js';
import { fillFields, readFields } from './fields.js';
import { onStatus } from './status.js';

function card() {
  return document.getElementById('config-card');
}

function readConfig() {
  return {
    ...readFields(card()),
    server_name: document.getElementById('input-name').value,
    scenario_id: document.getElementById('input-mission').value,
    password: document.getElementById('input-password').value,
    password_admin: document.getElementById('input-password-admin').value,
  };
}

// The form is filled when the page loads and after a save, never from the
// status poll: refilling it every 10 s would wipe edits that aren't saved yet.
async function loadConfig() {
  try {
    const r = await fetch('/api/config');
    if (r.status === 401) { window.location.href = '/login'; return; }
    const d = await r.json();
    if (!d.ok) { setLog(t('common.error', { error: d.error || t('common.unknown') }), 'error'); return; }
    document.getElementById('input-name').value = d.server_name || '';
    document.getElementById('input-password').value = d.password || '';
    document.getElementById('input-password-admin').value = d.password_admin || '';
    if (d.scenario_id) document.getElementById('input-mission').value = d.scenario_id;
    fillFields(card(), d);
    markSaved('server');
  } catch (e) { setLog(t('common.connection_error'), 'error'); }
}

function showConfigError(error) {
  const el = document.getElementById('config-alert');
  el.textContent = error ? t('config.unreadable_banner', { error }) : '';
  el.classList.toggle('visible', !!error);
}

function renderMissionSelect(missions, counts, currentId) {
  // Rebuilding the list can change the select's value (when the stored
  // scenario only appears once the list arrives): that isn't a change made
  // by the user.
  const unchanged = !hasChanges('server');
  const sel = document.getElementById('input-mission');
  // Always rebuild — discovered scenarios can change as the workshop populates.
  const prev = sel.value || currentId || '';
  sel.innerHTML = '';
  // Group by source: vanilla first, then per-mod alphabetical.
  const groups = {};
  missions.forEach(m => {
    const key = m.source || 'vanilla';
    (groups[key] = groups[key] || []).push(m);
  });
  const sourceKeys = Object.keys(groups).sort((a, b) => {
    if (a === 'vanilla') return -1;
    if (b === 'vanilla') return 1;
    return a.localeCompare(b);
  });
  sourceKeys.forEach(src => {
    const og = document.createElement('optgroup');
    og.label = src === 'vanilla' ? t('config.base_game') : src;
    groups[src].forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.name;
      og.appendChild(opt);
    });
    sel.appendChild(og);
  });
  if (prev) sel.value = prev;

  // Update the badge near the select if present.
  const badge = document.getElementById('scenario-source-badge');
  if (badge && counts) {
    badge.textContent = t('config.scenario_counts', { vanilla: counts.vanilla, mods: counts.from_mods });
  }
  if (unchanged) markSaved('server');
}

async function rescanScenarios() {
  const btn = document.getElementById('btn-rescan-scenarios');
  if (btn) btn.disabled = true;
  setLog(t('config.scanning'), 'info');
  try {
    const r = await postJson('/api/scenarios/rescan', {});
    const d = await r.json();
    if (d.ok) {
      renderMissionSelect(d.missions, d.missions_count);
      const diag = d.diag || {};
      let msg = t('config.scan_summary', { vanilla: d.missions_count.vanilla, mods: d.missions_count.from_mods });
      if (diag.workshop_dir) {
        const n = diag.metas_found ?? diag.paks_found ?? 0;
        msg += tn('config.scan_details', n, { dirs: diag.workshop_dir });
      } else {
        const candidates = diag.candidates_tried || [];
        const tried = candidates.map(c => c.path).slice(0, 3).join(', ') + (candidates.length > 3 ? '…' : '');
        msg += t('config.scan_nothing_found', { tried });
      }
      setLog(msg, diag.workshop_dir ? 'ok' : 'error');
      // Stash full diagnostics in console for deep debugging.
      if (diag) console.log('[rescan diagnostics]', diag);
    } else {
      setLog(t('config.rescan_failed', { error: d.error || t('common.unknown') }), 'error');
    }
  } catch (e) { setLog(t('config.rescan_error'), 'error'); }
  if (btn) btn.disabled = false;
}

export function initServerConfig() {
  trackSection('server', {
    card: card(),
    read: readConfig,
    reload: loadConfig,
    restartNotice: document.getElementById('restart-notice'),
  });
  onStatus(d => {
    showConfigError(d.config_error);
    renderMissionSelect(d.missions || [], d.missions_count, d.scenario_id);
  });
  document.getElementById('btn-rescan-scenarios').addEventListener('click', rescanScenarios);
  loadConfig();
}
