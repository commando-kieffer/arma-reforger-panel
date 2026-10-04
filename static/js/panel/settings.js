// Panel settings dialog, opened from the header: the style in use, and the
// styles that can be downloaded, uploaded and deleted. The settings are the
// same for everyone, and the page is reloaded once they are saved so they
// take effect.

import { t } from '../i18n.js';
import { postForm, postJson } from './api.js';

const MAX_STYLESHEET_BYTES = 512 * 1024;
const STYLESHEETS = ['base', 'login', 'panel'];

const $ = id => document.getElementById(id);

let themes = [];
let activeId = null;
let pending = false;

function selectedTheme() {
  return themes.find(theme => theme.id === $('settings-theme').value) || null;
}

function showError(message) {
  $('settings-notice').hidden = true;
  $('settings-error').textContent = message;
  $('settings-error').hidden = !message;
}

function showNotice(message) {
  $('settings-error').hidden = true;
  $('settings-notice').textContent = message;
  $('settings-notice').hidden = false;
}

function errorMessage(d) {
  return t('common.error', { error: d.error || t('common.unknown') });
}

// Ignores clicks while a request is running, so an action can't be sent twice.
async function run(action) {
  if (pending) return;
  pending = true;
  try {
    await action();
  } catch (e) {
    showError(t('common.connection_error'));
  } finally {
    pending = false;
  }
}

async function loadThemes(selectId) {
  const select = $('settings-theme');
  select.disabled = true;
  const r = await fetch('/api/themes');
  if (r.status === 401) { window.location.href = '/login'; return; }
  const d = await r.json();
  if (!d.ok) { showError(t('settings.load_failed', { error: d.error || t('common.unknown') })); return; }
  themes = d.themes;
  activeId = d.active;
  select.replaceChildren(...themes.map(theme => new Option(theme.name, theme.id)));
  select.value = themes.some(theme => theme.id === selectId) ? selectId : activeId;
  select.disabled = false;
  renderActions();
}

function renderActions() {
  const theme = selectedTheme();
  const download = $('btn-theme-download');
  download.hidden = !theme;
  if (theme) download.href = `/api/themes/${encodeURIComponent(theme.id)}/download`;
  // The style in use can't be deleted, and the built-in ones never can.
  $('btn-theme-delete').hidden = !theme || !theme.custom || theme.id === activeId;
}

function openUpload() {
  $('theme-upload').hidden = false;
  $('theme-name').focus();
}

function closeUpload() {
  $('theme-upload').hidden = true;
  $('theme-name').value = '';
  STYLESHEETS.forEach(key => { $(`theme-file-${key}`).value = ''; });
}

async function upload(replace = false) {
  const name = $('theme-name').value.trim();
  if (!name) { showError(t('settings.name_required')); return; }
  const fd = new FormData();
  fd.append('name', name);
  if (replace) fd.append('replace', '1');
  for (const key of STYLESHEETS) {
    const file = $(`theme-file-${key}`).files[0];
    if (!file) { showError(t('settings.file_required', { file: `${key}.css` })); return; }
    if (file.size > MAX_STYLESHEET_BYTES) {
      showError(t('settings.file_too_large', { file: file.name, max: MAX_STYLESHEET_BYTES / 1024 }));
      return;
    }
    fd.append(key, file, file.name);
  }

  const d = await (await postForm('/api/themes', fd)).json();
  if (!d.ok && d.exists && !replace) {
    if (confirm(t('settings.confirm_replace', { name }))) await upload(true);
    return;
  }
  if (!d.ok) { showError(errorMessage(d)); return; }
  // New stylesheets for the style in use only show once the page reloads.
  if (d.id === activeId) { window.location.reload(); return; }
  closeUpload();
  await loadThemes(d.id);
  showNotice(t('settings.uploaded', { name }));
}

async function deleteTheme() {
  const theme = selectedTheme();
  if (!theme || !confirm(t('settings.confirm_delete', { name: theme.name }))) return;
  const d = await (await postJson(`/api/themes/${encodeURIComponent(theme.id)}/delete`, {})).json();
  if (!d.ok) { showError(errorMessage(d)); return; }
  await loadThemes(activeId);
  showNotice(t('settings.deleted', { name: theme.name }));
}

async function save() {
  const theme = selectedTheme();
  if (!theme || theme.id === activeId) { $('settings-dialog').close(); return; }
  const d = await (await postJson('/api/settings', { theme: theme.id })).json();
  if (!d.ok) { showError(errorMessage(d)); return; }
  window.location.reload();
}

export function initSettings() {
  const dialog = $('settings-dialog');

  $('btn-settings').addEventListener('click', () => {
    showError('');
    $('settings-notice').hidden = true;
    closeUpload();
    dialog.showModal();
    run(() => loadThemes(activeId));
  });

  dialog.querySelectorAll('[data-dialog-close]').forEach(btn => {
    btn.addEventListener('click', () => dialog.close());
  });
  // The form fills the dialog, so a click on the dialog itself is on the backdrop.
  dialog.addEventListener('click', event => {
    if (event.target === dialog) dialog.close();
  });

  $('settings-theme').addEventListener('change', renderActions);
  $('btn-theme-upload-open').addEventListener('click', openUpload);
  $('btn-theme-upload-cancel').addEventListener('click', closeUpload);
  $('btn-theme-upload').addEventListener('click', () => run(() => upload()));
  $('btn-theme-delete').addEventListener('click', () => run(deleteTheme));
  // Enter in the name field uploads rather than submitting the settings form.
  $('theme-name').addEventListener('keydown', event => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    run(() => upload());
  });

  $('settings-form').addEventListener('submit', event => {
    event.preventDefault();
    run(save);
  });
}
