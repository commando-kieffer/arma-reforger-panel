// Server mods card: mod sets, and the mods of the set chosen in the selector
// (list, bulk JSON import and single-mod form).

import { t, tn } from '../i18n.js';
import { postForm, postJson } from './api.js';
import { setLog } from './activity.js';
import { escHtml } from './format.js';

const MAX_IMPORT_BYTES = 2 * 1024 * 1024;

let sets = [];
let activeId = null;
let configDiffers = false;
let selectedId = null;
let nameFormMode = null;  // 'new', 'duplicate' or 'rename' while the name form is open
let pending = false;

const $ = id => document.getElementById(id);

function selectedSet() {
  return sets.find(s => s.id === selectedId) || null;
}

function setUrl(path = '') {
  return `/api/modsets/${encodeURIComponent(selectedId)}${path}`;
}

// Ignores clicks while a request is running, so an action can't be sent twice.
async function run(action) {
  if (pending) return;
  pending = true;
  try {
    await action();
  } catch (e) {
    setLog(t('common.connection_error'), 'error');
  } finally {
    pending = false;
  }
}

async function send(url, body) {
  const r = await postJson(url, body);
  return r.json();
}

function errorMessage(d) {
  return t('common.error', { error: d.error || t('common.unknown') });
}

function showRestartNotice(visible) {
  $('mods-restart-notice').classList.toggle('visible', !!visible);
}

async function loadSets(selectId = selectedId) {
  const r = await fetch('/api/modsets');
  if (r.status === 401) { window.location.href = '/login'; return; }
  const d = await r.json();
  if (!d.ok) {
    $('mods-list').innerHTML =
      `<div class="mods-placeholder is-empty">${escHtml(t('modsets.load_failed', { error: d.error || t('common.unknown') }))}</div>`;
    return;
  }
  sets = d.sets;
  activeId = d.active;
  configDiffers = d.config_differs;
  const known = id => sets.some(s => s.id === id);
  selectedId = known(selectId) ? selectId : (activeId || (sets[0] && sets[0].id) || null);
  render();
}

function render() {
  const select = $('modset-select');
  select.innerHTML = sets.map(s => {
    const label = s.id === activeId ? t('modsets.option_in_use', { name: s.name }) : s.name;
    return `<option value="${escHtml(s.id)}">${escHtml(label)}</option>`;
  }).join('');
  select.value = selectedId;
  select.disabled = sets.length === 0;

  const set = selectedSet();
  const inUse = !!set && set.id === activeId;
  $('btn-modset-activate').disabled = !set || (inUse && !configDiffers);
  $('btn-modset-export').disabled = !set;
  document.querySelectorAll('[data-modset-action]').forEach(btn => {
    const action = btn.dataset.modsetAction;
    btn.disabled = action !== 'new' && (!set || (action === 'delete' && inUse));
  });

  let state = !activeId ? t('modsets.none_in_use')
    : inUse ? t('modsets.state_in_use') : t('modsets.state_not_in_use');
  if (set) state = `${tn('modsets.count', set.mods.length)} · ${state}`;
  $('modset-state').textContent = state;
  $('modset-differs').hidden = !(inUse && configDiffers);

  renderMods(set ? set.mods : []);
}

function renderMods(mods) {
  const container = $('mods-list');
  if (mods.length === 0) {
    container.innerHTML = `<div class="mods-placeholder is-empty">${t('mods.empty')}</div>`;
    return;
  }
  container.innerHTML = '';
  mods.forEach(mod => {
    const row = document.createElement('div');
    row.className = 'mod-row';
    row.innerHTML = `
      <div class="mod-info">
        <div class="mod-name">${escHtml(mod.name || mod.modId)}</div>
        <div class="mod-meta">
          <span class="mod-id">${escHtml(mod.modId)}</span>
          ${mod.version ? `<span class="mod-version">v${escHtml(mod.version)}</span>` : ''}
        </div>
      </div>
      <button type="button" class="mod-remove" data-mod-id="${escHtml(mod.modId)}">${t('mods.remove')}</button>`;
    container.appendChild(row);
  });
}

// Mod sets

function openNameForm(mode) {
  const set = selectedSet();
  if (mode !== 'new' && !set) return;
  nameFormMode = mode;
  const input = $('modset-name');
  input.value = mode === 'rename' ? set.name
    : mode === 'duplicate' ? t('modsets.copy_name', { name: set.name }) : '';
  $('modset-name-form').hidden = false;
  input.focus();
  input.select();
}

function closeNameForm() {
  nameFormMode = null;
  $('modset-name-form').hidden = true;
}

async function submitName() {
  const name = $('modset-name').value.trim();
  const renaming = nameFormMode === 'rename';
  const body = { name };
  if (nameFormMode === 'duplicate') body.copy_from = selectedId;
  setLog(t('modsets.saving'), 'info');
  const d = await send(renaming ? setUrl('/rename') : '/api/modsets', body);
  if (!d.ok) { setLog(errorMessage(d), 'error'); return; }
  setLog(t(renaming ? 'modsets.renamed' : 'modsets.created', { name }), 'ok');
  closeNameForm();
  await loadSets(d.id || selectedId);
}

async function deleteSet() {
  const set = selectedSet();
  if (!set || !confirm(t('modsets.confirm_delete', { name: set.name }))) return;
  const d = await send(setUrl('/delete'), {});
  if (!d.ok) { setLog(errorMessage(d), 'error'); return; }
  setLog(t('modsets.deleted', { name: set.name }), 'ok');
  await loadSets(activeId);
}

async function activateSet() {
  const set = selectedSet();
  if (!set) return;
  setLog(t('modsets.activating', { name: set.name }), 'info');
  const d = await send(setUrl('/activate'), {});
  if (!d.ok) { setLog(errorMessage(d), 'error'); return; }
  setLog(t('modsets.activated', { name: set.name }), 'ok');
  showRestartNotice(d.restart_required);
  await loadSets();
}

async function exportSet() {
  if (!selectedSet()) return;
  const r = await fetch(setUrl('/export'));
  if (r.status === 401) { window.location.href = '/login'; return; }
  const d = await r.json();
  if (!d.ok) { setLog(errorMessage(d), 'error'); return; }
  downloadJson(d.mods, `${d.name.replace(/[\\/:*?"<>|]/g, '_')}.json`);
  let msg = tn('modsets.exported', d.mods.length, { name: d.name });
  if (d.unversioned.length) {
    const mods = d.unversioned.slice(0, 3).join(', ') + (d.unversioned.length > 3 ? '…' : '');
    msg += tn('modsets.export_unversioned', d.unversioned.length, { mods });
  }
  setLog(msg, 'ok');
}

function downloadJson(data, fileName) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2) + '\n'], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Revoking the URL right after the click can cancel the download in some browsers.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Mods of the selected set

async function addMod() {
  const modId   = $('mod-id').value.trim();
  const modName = $('mod-name').value.trim();
  const modVer  = $('mod-version').value.trim();
  if (!modId)   { setLog(t('mods.id_required'), 'error'); return; }
  if (!modName) { setLog(t('mods.name_required'), 'error'); return; }
  setLog(t('mods.adding'), 'info');
  const d = await send(setUrl('/mods/add'), { modId, name: modName, version: modVer });
  if (!d.ok) { setLog(errorMessage(d), 'error'); return; }
  setLog(t('mods.added', { name: modName }), 'ok');
  $('mod-id').value = '';
  $('mod-name').value = '';
  $('mod-version').value = '';
  showRestartNotice(d.restart_required);
  await loadSets();
}

async function removeMod(modId) {
  if (!confirm(t('mods.confirm_remove'))) return;
  setLog(t('mods.removing'), 'info');
  const d = await send(setUrl('/mods/remove'), { modId });
  if (!d.ok) { setLog(errorMessage(d), 'error'); return; }
  setLog(t('mods.removed'), 'ok');
  showRestartNotice(d.restart_required);
  await loadSets();
}

async function importModsFromTextarea() {
  const txt = $('mods-import-text').value;
  if (!txt.trim()) { setLog(t('mods.paste_first'), 'error'); return; }
  setLog(t('mods.importing'), 'info');
  const d = await send(setUrl('/mods/import'), { payload: txt, mode: $('mods-import-mode').value });
  await afterImport(d);
}

async function importModsFromFile(input) {
  const f = input.files && input.files[0];
  if (!f) return;
  input.value = '';
  if (f.size > MAX_IMPORT_BYTES) { setLog(t('mods.file_too_large'), 'error'); return; }
  setLog(t('mods.uploading', { file: f.name }), 'info');
  const fd = new FormData();
  fd.append('file', f, f.name);
  fd.append('mode', $('mods-import-mode').value);
  let d;
  try {
    d = await (await postForm(setUrl('/mods/import'), fd)).json();
  } catch (e) {
    setLog(t('mods.upload_error'), 'error');
    return;
  }
  await afterImport(d);
}

async function afterImport(d) {
  if (!d.ok) {
    setLog(t('mods.import_failed', { error: d.error || t('common.unknown') }), 'error');
    return;
  }
  let msg = d.message || tn('mods.imported', d.imported);
  if (d.skipped && d.skipped.length) {
    const entries = d.skipped.slice(0, 3).join('; ') + (d.skipped.length > 3 ? '…' : '');
    msg += tn('mods.skipped', d.skipped.length, { entries });
  }
  setLog(msg, 'ok');
  $('mods-import-text').value = '';
  showRestartNotice(d.restart_required);
  await loadSets();
}

export function initMods() {
  $('modset-select').addEventListener('change', event => {
    selectedId = event.target.value;
    closeNameForm();
    render();
  });
  $('btn-modset-activate').addEventListener('click', () => run(activateSet));
  $('btn-modset-export').addEventListener('click', () => run(exportSet));
  document.querySelectorAll('[data-modset-action]').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.modsetAction === 'delete') run(deleteSet);
      else openNameForm(btn.dataset.modsetAction);
    });
  });
  $('modset-name-form').addEventListener('submit', event => {
    event.preventDefault();
    run(submitName);
  });
  $('btn-modset-name-cancel').addEventListener('click', closeNameForm);

  $('btn-add-mod').addEventListener('click', () => run(addMod));
  $('btn-import-text').addEventListener('click', () => run(importModsFromTextarea));
  $('mods-import-file').addEventListener('change', event => run(() => importModsFromFile(event.target)));
  $('mods-list').addEventListener('click', event => {
    const btn = event.target.closest('.mod-remove');
    if (btn) run(() => removeMod(btn.dataset.modId));
  });

  run(() => loadSets());
}
