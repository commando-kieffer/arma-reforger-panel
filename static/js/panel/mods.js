// Server mods card: active list, bulk JSON import and single-mod form.

import { postForm, postJson } from './api.js';
import { setLog } from './activity.js';
import { escHtml } from './format.js';
import { fetchStatus, onStatus } from './status.js';

const MAX_IMPORT_BYTES = 2 * 1024 * 1024;

function renderMods(mods) {
  const container = document.getElementById('mods-list');
  if (mods.length === 0) {
    container.innerHTML = '<div class="mods-placeholder is-empty">No mods installed</div>';
    return;
  }
  container.innerHTML = '';
  mods.forEach(mod => {
    const row = document.createElement('div');
    row.className = 'mod-row';
    row.innerHTML = `
      <div class="mod-info">
        <div class="mod-name">${escHtml(mod.name)}</div>
        <div class="mod-meta">
          <span class="mod-id">${escHtml(mod.modId)}</span>
          ${mod.version ? `<span class="mod-version">v${escHtml(mod.version)}</span>` : ''}
        </div>
      </div>
      <button type="button" class="mod-remove" data-mod-id="${escHtml(mod.modId)}">Remove ✕</button>`;
    container.appendChild(row);
  });
}

function showRestartNotice(visible) {
  document.getElementById('mods-restart-notice').classList.toggle('visible', visible);
}

async function addMod() {
  const modId   = document.getElementById('mod-id').value.trim();
  const modName = document.getElementById('mod-name').value.trim();
  const modVer  = document.getElementById('mod-version').value.trim();
  if (!modId)   { setLog('Mod ID is required', 'error'); return; }
  if (!modName) { setLog('Mod name is required', 'error'); return; }
  document.getElementById('btn-add-mod').disabled = true;
  setLog('Adding mod…', 'info');
  try {
    const r = await postJson('/api/mods/add', { modId, name: modName, version: modVer });
    const d = await r.json();
    if (d.ok) {
      setLog(`Mod "${modName}" added`, 'ok');
      document.getElementById('mod-id').value = '';
      document.getElementById('mod-name').value = '';
      document.getElementById('mod-version').value = '';
      showRestartNotice(d.restart_required);
      await fetchStatus();
    } else {
      setLog('Error: ' + (d.error || 'unknown'), 'error');
    }
  } catch (e) { setLog('Connection error', 'error'); }
  document.getElementById('btn-add-mod').disabled = false;
}

async function removeMod(modId) {
  if (!confirm('Remove this mod from the configuration?')) return;
  setLog('Removing mod…', 'info');
  try {
    const r = await postJson('/api/mods/remove', { modId });
    const d = await r.json();
    if (d.ok) {
      setLog('Mod removed', 'ok');
      showRestartNotice(d.restart_required);
      await fetchStatus();
    } else {
      setLog('Error: ' + (d.error || 'unknown'), 'error');
    }
  } catch (e) { setLog('Connection error', 'error'); }
}

async function importModsFromTextarea() {
  const txt = document.getElementById('mods-import-text').value;
  if (!txt.trim()) { setLog('Paste a JSON array first', 'error'); return; }
  const mode = document.getElementById('mods-import-mode').value;
  setLog('Importing mods…', 'info');
  try {
    const r = await postJson('/api/mods/import', { payload: txt, mode });
    const d = await r.json();
    afterImport(d);
  } catch (e) { setLog('Connection error', 'error'); }
}

async function importModsFromFile(input) {
  const f = input.files && input.files[0];
  if (!f) return;
  if (f.size > MAX_IMPORT_BYTES) { setLog('File too large (max 2 MB)', 'error'); return; }
  const mode = document.getElementById('mods-import-mode').value;
  setLog(`Uploading ${f.name}…`, 'info');
  const fd = new FormData();
  fd.append('file', f, f.name);
  fd.append('mode', mode);
  try {
    const r = await postForm('/api/mods/import', fd);
    const d = await r.json();
    afterImport(d);
  } catch (e) { setLog('Upload error', 'error'); }
  input.value = '';
}

function afterImport(d) {
  if (d.ok) {
    let msg = d.message || `${d.imported} mods imported`;
    if (d.skipped && d.skipped.length) {
      msg += ` (${d.skipped.length} skipped: ${d.skipped.slice(0, 3).join('; ')}${d.skipped.length > 3 ? '…' : ''})`;
    }
    setLog(msg, 'ok');
    document.getElementById('mods-import-text').value = '';
    showRestartNotice(d.restart_required);
    fetchStatus();
  } else {
    setLog('Import failed: ' + (d.error || 'unknown'), 'error');
  }
}

export function initMods() {
  // Render the mod list
  onStatus(d => renderMods(d.mods || []));

  document.getElementById('btn-add-mod').addEventListener('click', addMod);
  document.getElementById('btn-import-text').addEventListener('click', importModsFromTextarea);
  document.getElementById('mods-import-file').addEventListener('change', event => importModsFromFile(event.target));
  document.getElementById('mods-list').addEventListener('click', event => {
    const btn = event.target.closest('.mod-remove');
    if (btn) removeMod(btn.dataset.modId);
  });
}
