// Server configuration card: name, scenario and passwords.

import { postJson } from './api.js';
import { setBusy, setLog } from './activity.js';
import { fetchStatus, onStatus } from './status.js';

function fillForm(d) {
  const nameInput = document.getElementById('input-name');
  if (document.activeElement !== nameInput) nameInput.value = d.server_name || '';

  const pwdInput = document.getElementById('input-password');
  if (document.activeElement !== pwdInput) pwdInput.value = d.password || '';

  const pwdAdminInput = document.getElementById('input-password-admin');
  if (document.activeElement !== pwdAdminInput) pwdAdminInput.value = d.password_admin || '';

  renderMissionSelect(d.missions || [], d.missions_count, d.scenario_id);
}

function renderMissionSelect(missions, counts, currentId) {
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
    og.label = src === 'vanilla' ? 'Base game' : src;
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
    badge.textContent = `${counts.vanilla} vanilla · ${counts.from_mods} from mods`;
  }
}

async function rescanScenarios() {
  const btn = document.getElementById('btn-rescan-scenarios');
  if (btn) btn.disabled = true;
  setLog('Scanning installed mods for scenarios…', 'info');
  try {
    const r = await postJson('/api/scenarios/rescan', {});
    const d = await r.json();
    if (d.ok) {
      renderMissionSelect(d.missions, d.missions_count);
      const diag = d.diag || {};
      let msg = `Vanilla: ${d.missions_count.vanilla} · From mods: ${d.missions_count.from_mods}`;
      if (diag.workshop_dir) {
        const n = diag.metas_found ?? diag.paks_found ?? 0;
        msg += ` (scanned ${n} addon${n === 1 ? '' : 's'} in ${diag.workshop_dir})`;
      } else {
        const tried = (diag.candidates_tried || []).map(c => c.path).slice(0, 3).join(', ');
        msg += `. No .pak files found. Tried: ${tried}${(diag.candidates_tried || []).length > 3 ? '…' : ''}. Run the server once so it downloads workshop mods, or set WORKSHOP_DIR in config.env.`;
      }
      setLog(msg, diag.workshop_dir ? 'ok' : 'error');
      // Stash full diagnostics in console for deep debugging.
      if (diag) console.log('[rescan diagnostics]', diag);
    } else {
      setLog('Rescan failed: ' + (d.error || 'unknown'), 'error');
    }
  } catch (e) { setLog('Rescan error', 'error'); }
  if (btn) btn.disabled = false;
}

async function saveConfig() {
  const name     = document.getElementById('input-name').value.trim();
  const scenario = document.getElementById('input-mission').value;
  const password = document.getElementById('input-password').value;
  const pwdAdmin = document.getElementById('input-password-admin').value.trim();

  if (!name)     { setLog('Name serwera nie może być pusta', 'error'); return; }
  if (!pwdAdmin) { setLog('Admin password nie może być puste', 'error'); return; }

  setBusy(true);
  setLog('Zapisywanie konfiguracji...', 'info');
  try {
    const r = await postJson('/api/config', { server_name: name, scenario_id: scenario, password, password_admin: pwdAdmin });
    const d = await r.json();
    if (d.ok) {
      setLog('Konfiguracja zapisana', 'ok');
      document.getElementById('restart-notice').classList.toggle('visible', !!d.restart_required);
      await fetchStatus();
    } else {
      setLog('Błąd zapisu: ' + (d.error || 'nieznany'), 'error');
    }
  } catch (e) { setLog('Błąd połączenia', 'error'); }
  setBusy(false);
}

export function initServerConfig() {
  onStatus(fillForm);
  document.getElementById('btn-rescan-scenarios').addEventListener('click', rescanScenarios);
  document.getElementById('btn-save').addEventListener('click', saveConfig);
}
