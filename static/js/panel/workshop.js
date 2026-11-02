// Mods the server has downloaded (end of the Mods card), and removing them
// from disk.

import { t, tn } from '../i18n.js';
import { postJson } from './api.js';
import { setLog } from './activity.js';
import { escHtml, fmtBytes } from './format.js';

const $ = id => document.getElementById(id);

let mods = [];
let pending = false;

function renderMod(mod, running) {
  const where = mod.in_use
    ? `<span class="badge">${t('workshop.in_use')}</span>`
    : '';
  const sets = mod.sets.length
    ? t('workshop.in_sets', { sets: mod.sets.join(', ') })
    : t('workshop.in_no_set');
  // Removing is refused while the server runs, and for a mod it loads.
  const blocked = running ? t('workshop.running_help') : mod.in_use ? t('workshop.in_use_help') : '';
  return `
    <div class="mod-row">
      <div class="mod-info">
        <div class="mod-name">${escHtml(mod.name)} ${where}</div>
        <div class="mod-meta">
          <span class="mod-id">${escHtml(mod.id)}</span>
          ${mod.version ? `<span class="mod-version">v${escHtml(mod.version)}</span>` : ''}
          <span class="mod-id">${fmtBytes(mod.size)} · ${escHtml(sets)}</span>
        </div>
      </div>
      <button type="button" class="mod-remove" data-uninstall="${escHtml(mod.id)}"
        ${blocked ? `disabled title="${escHtml(blocked)}"` : ''}>${t('workshop.uninstall')}</button>
    </div>`;
}

export async function loadWorkshop() {
  try {
    const r = await fetch('/api/workshop');
    if (r.status === 401) { window.location.href = '/login'; return; }
    const d = await r.json();
    mods = d.mods;
    const total = mods.reduce((sum, mod) => sum + mod.size, 0);
    $('workshop-summary').textContent = mods.length
      ? tn('workshop.summary', mods.length, { size: fmtBytes(total), dir: d.dir }) + (d.running ? ' ' + t('workshop.running_help') : '')
      : '';
    $('workshop-list').innerHTML = mods.length
      ? mods.map(mod => renderMod(mod, d.running)).join('')
      : `<div class="mods-placeholder is-empty">${escHtml(t('workshop.empty', { dir: d.dir || '—' }))}</div>`;
  } catch (e) {
    $('workshop-list').innerHTML = `<div class="mods-placeholder is-empty">${escHtml(t('workshop.load_failed'))}</div>`;
  }
}

async function uninstall(modId) {
  const mod = mods.find(m => m.id === modId);
  if (!mod || pending) return;
  if (!confirm(t('workshop.confirm_uninstall', { name: mod.name, size: fmtBytes(mod.size) }))) return;
  pending = true;
  setLog(t('workshop.uninstalling', { name: mod.name }), 'info');
  try {
    const d = await (await postJson(`/api/workshop/${encodeURIComponent(modId)}/uninstall`, {})).json();
    if (d.ok) setLog(t('workshop.uninstalled', { name: mod.name }), 'ok');
    else setLog(t('common.error', { error: d.error || t('common.unknown') }), 'error');
  } catch (e) {
    setLog(t('common.connection_error'), 'error');
  }
  pending = false;
  await loadWorkshop();
}

export function initWorkshop() {
  $('btn-refresh-workshop').addEventListener('click', loadWorkshop);
  $('workshop-list').addEventListener('click', event => {
    const button = event.target.closest('[data-uninstall]');
    if (button && !button.disabled) uninstall(button.dataset.uninstall);
  });
  loadWorkshop();
}
