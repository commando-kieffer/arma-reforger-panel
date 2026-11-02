// Unsaved changes in the cards that edit config.json, saved together from
// the bar at the bottom of the page. Each card registers how to read its
// values and how to reload them; a card has changes when its values differ
// from the ones it loaded last.
//
// The forms and the config.json editor both write config.json, and the
// editor replaces the whole file: while one side has unsaved changes, the
// other is locked.

import { t } from '../i18n.js';
import { postJson } from './api.js';
import { setBusy, setLog } from './activity.js';
import { fetchStatus } from './status.js';

const EDITOR = 'raw';

const $ = id => document.getElementById(id);

// id -> { card, read, reload, lock, restartNotice, onError, saved }
const sections = new Map();
let saving = false;

// `read()` returns what the save sends for the card, `reload()` loads the
// stored values again (and calls markSaved), `lock(locked)` replaces the
// default lock, and `onError(response)` gets a failed save that concerns it.
export function trackSection(id, { card, read, reload, lock, restartNotice, onError }) {
  sections.set(id, { card, read, reload, lock, restartNotice, onError, saved: null });
  card.addEventListener('input', refresh);
  card.addEventListener('change', refresh);
}

// Records the card's current values as the stored ones. Cards call it once
// they have filled their controls.
export function markSaved(id) {
  const section = sections.get(id);
  section.saved = JSON.stringify(section.read());
  refresh();
}

export function hasChanges(id) {
  const section = sections.get(id);
  return !!section && section.saved !== null && JSON.stringify(section.read()) !== section.saved;
}

function changedSections() {
  return [...sections.keys()].filter(hasChanges);
}

// Reloads a card unless it has changes the user hasn't saved, for example
// after a mod set changed config.json behind the editor.
export function reloadIfUnchanged(id) {
  if (sections.has(id) && !hasChanges(id)) sections.get(id).reload();
}

function setLocked(id, locked) {
  const section = sections.get(id);
  if (section.lock) {
    section.lock(locked);
  } else {
    section.card.inert = locked;
    section.card.classList.toggle('is-locked', locked);
  }
}

function showError(message) {
  $('save-bar-error').textContent = message;
  $('save-bar-error').hidden = !message;
}

export function refresh() {
  const changed = changedSections();
  const editorChanged = changed.includes(EDITOR);
  const formsChanged = changed.some(id => id !== EDITOR);
  sections.forEach((section, id) => setLocked(id, id === EDITOR ? formsChanged : editorChanged));

  $('save-bar').hidden = changed.length === 0;
  document.body.classList.toggle('has-save-bar', changed.length > 0);
  $('save-bar-sections').textContent = changed.map(id => t('changes.section_' + id)).join(', ');
  $('save-bar-note').textContent = editorChanged ? t('changes.forms_locked') : '';
  $('save-bar-note').hidden = !editorChanged;
  if (!changed.length) showError('');
}

async function reloadAll() {
  await Promise.all([...sections.values()].map(section => section.reload()));
}

async function saveAll() {
  const changed = changedSections();
  if (saving || !changed.length) return;
  const body = Object.fromEntries(changed.map(id => [id, sections.get(id).read()]));
  saving = true;
  setBusy(true);
  showError('');
  setLog(t('changes.saving'), 'info');
  try {
    const r = await postJson('/api/config/save', body);
    const d = await r.json();
    if (!d.ok) {
      const error = d.error || t('common.unknown');
      const message = d.section
        ? t('changes.save_failed_section', { section: t('changes.section_' + d.section), error })
        : t('common.save_failed', { error });
      showError(message);
      setLog(message, 'error');
      const section = sections.get(d.section);
      if (section && section.onError) section.onError(d);
      return;
    }
    setLog(t('changes.saved'), 'ok');
    d.saved.forEach(id => {
      const notice = sections.get(id).restartNotice;
      if (notice) notice.classList.toggle('visible', !!d.restart_required);
    });
    // The forms and the editor show the same file: reload both sides.
    await reloadAll();
    await fetchStatus();
  } catch (e) {
    showError(t('common.connection_error'));
    setLog(t('common.connection_error'), 'error');
  } finally {
    saving = false;
    setBusy(false);
  }
}

async function discardAll() {
  const changed = changedSections();
  if (!changed.length || !confirm(t('changes.confirm_discard'))) return;
  await Promise.all(changed.map(id => sections.get(id).reload()));
}

export function initChanges() {
  $('btn-save-all').addEventListener('click', saveAll);
  $('btn-discard-all').addEventListener('click', discardAll);
  // Ctrl+S / Cmd+S saves instead of downloading the page.
  document.addEventListener('keydown', event => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's' && changedSections().length) {
      event.preventDefault();
      saveAll();
    }
  });
  window.addEventListener('beforeunload', event => {
    if (changedSections().length) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
}
