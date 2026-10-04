// Panel settings dialog, opened from the header: the style in use, the
// styles that can be downloaded, uploaded and deleted, the banner logo and
// the app icon. The settings are the same for everyone, and the page is
// reloaded once a style is saved so it takes effect.

import { t } from '../i18n.js';
import { postForm, postJson } from './api.js';

const MAX_STYLESHEET_BYTES = 512 * 1024;
const STYLESHEETS = ['base', 'login', 'panel'];
// Same limit as FILE_MAX_BYTES in arma_panel/services/branding.py.
const MAX_IMAGE_BYTES = 1536 * 1024;
// Requests are capped at 2 MB (MAX_CONTENT_LENGTH in arma_panel/__init__.py).
const MAX_UPLOAD_BYTES = 1900 * 1024;

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

// Banner logo and app icons (see arma_panel/services/branding.py). The
// browser scales the chosen image and sends PNG files.

// Each output is fitted into `box`. A square output fills the whole box, with
// the image centered on a transparent background; the others take the
// image's proportions.
const BRANDING = {
  banner: {
    preview: 'banner-logo.png',
    outputs: [{ name: 'banner-logo.png', box: [1200, 300], square: false }],
  },
  icons: {
    preview: 'icon-192.png',
    outputs: [
      { name: 'icon-192.png', box: [192, 192], square: true },
      { name: 'icon-512.png', box: [512, 512], square: true },
    ],
  },
};

const pendingImages = {};  // { group: { file name: PNG blob } } scaled from the chosen image
const previewUrls = {};

function brandingUrl(name) {
  // The URL never changes, so a query string makes the browser fetch it again.
  return `/branding/${name}?v=${Date.now()}`;
}

function setPreview(group, blob) {
  if (previewUrls[group]) URL.revokeObjectURL(previewUrls[group]);
  previewUrls[group] = blob ? URL.createObjectURL(blob) : null;
  $(`branding-preview-${group}`).src = previewUrls[group] || brandingUrl(BRANDING[group].preview);
}

function clearBrandingForm(group) {
  delete pendingImages[group];
  $(`branding-file-${group}`).value = '';
  $(`btn-branding-upload-${group}`).disabled = true;
  setPreview(group, null);
}

async function loadBrandingState() {
  const r = await fetch('/api/branding');
  if (r.status === 401) { window.location.href = '/login'; return; }
  const d = await r.json();
  Object.keys(BRANDING).forEach(group => { $(`btn-branding-reset-${group}`).hidden = !d.custom[group]; });
}

function scaleImage(img, { box: [boxWidth, boxHeight], square }) {
  const scale = Math.min(boxWidth / img.naturalWidth, boxHeight / img.naturalHeight);
  const width = Math.max(1, Math.round(img.naturalWidth * scale));
  const height = Math.max(1, Math.round(img.naturalHeight * scale));
  const canvas = document.createElement('canvas');
  canvas.width = square ? boxWidth : width;
  canvas.height = square ? boxHeight : height;
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(img, (canvas.width - width) / 2, (canvas.height - height) / 2, width, height);
  return new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
}

async function prepareImage(group, file) {
  delete pendingImages[group];
  $(`btn-branding-upload-${group}`).disabled = true;
  setPreview(group, null);
  if (!file) return;
  const outputs = BRANDING[group].outputs;
  const url = URL.createObjectURL(file);
  let blobs;
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    // Some SVG files have no size of their own.
    if (!img.naturalWidth || !img.naturalHeight) throw new Error('no size');
    blobs = await Promise.all(outputs.map(output => scaleImage(img, output)));
    if (blobs.some(blob => !blob)) throw new Error('not scaled');
  } catch (e) {
    $(`branding-file-${group}`).value = '';
    showError(t('settings.image_unreadable'));
    return;
  } finally {
    URL.revokeObjectURL(url);
  }
  const total = blobs.reduce((sum, blob) => sum + blob.size, 0);
  if (blobs.some(blob => blob.size > MAX_IMAGE_BYTES) || total > MAX_UPLOAD_BYTES) {
    $(`branding-file-${group}`).value = '';
    showError(t('settings.image_too_large', { max: MAX_IMAGE_BYTES / 1024 }));
    return;
  }
  showError('');
  pendingImages[group] = Object.fromEntries(outputs.map((output, i) => [output.name, blobs[i]]));
  setPreview(group, blobs[0]);
  $(`btn-branding-upload-${group}`).disabled = false;
}

// Points every element showing the group's images at the new files.
function refreshBranding(group) {
  BRANDING[group].outputs.forEach(({ name }) => {
    document.querySelectorAll(`[data-branding="${name}"]`).forEach(el => {
      el[el.tagName === 'LINK' ? 'href' : 'src'] = brandingUrl(name);
    });
  });
}

async function uploadImage(group) {
  const images = pendingImages[group];
  if (!images) return;
  const fd = new FormData();
  Object.entries(images).forEach(([name, blob]) => fd.append(name, blob, name));
  const d = await (await postForm(`/api/branding/${group}`, fd)).json();
  if (!d.ok) { showError(errorMessage(d)); return; }
  clearBrandingForm(group);
  $(`btn-branding-reset-${group}`).hidden = false;
  refreshBranding(group);
  showNotice(t(`settings.${group}_saved`));
}

async function resetImage(group) {
  if (!confirm(t(`settings.${group}_confirm_reset`))) return;
  const d = await (await postJson(`/api/branding/${group}/reset`, {})).json();
  if (!d.ok) { showError(errorMessage(d)); return; }
  clearBrandingForm(group);
  $(`btn-branding-reset-${group}`).hidden = true;
  refreshBranding(group);
  showNotice(t(`settings.${group}_reset_done`));
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
    Object.keys(BRANDING).forEach(clearBrandingForm);
    dialog.showModal();
    run(async () => {
      await loadThemes(activeId);
      await loadBrandingState();
    });
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

  Object.keys(BRANDING).forEach(group => {
    $(`branding-file-${group}`).addEventListener('change', event => prepareImage(group, event.target.files[0]));
    $(`btn-branding-upload-${group}`).addEventListener('click', () => run(() => uploadImage(group)));
    $(`btn-branding-reset-${group}`).addEventListener('click', () => run(() => resetImage(group)));
  });

  $('settings-form').addEventListener('submit', event => {
    event.preventDefault();
    run(save);
  });
}
