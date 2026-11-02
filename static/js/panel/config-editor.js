// config.json editor: the whole file as text, checked by the server as it's
// edited (services/config_check.py) and saved from the save bar (changes.js).
// It loads the file as stored, even when it isn't valid JSON, so it can be
// used to repair one.

import { t } from '../i18n.js';
import { postJson } from './api.js';
import { markSaved, trackSection } from './changes.js';
import { escHtml } from './format.js';

const CHECK_DELAY_MS = 500;

const $ = id => document.getElementById(id);

let loadedSha = null;
let checkTimer = null;
let checkNumber = 0;

function readEditor() {
  return { text: $('raw-config').value, sha256: loadedSha };
}

function setStatus(message, level = '') {
  const el = $('editor-status');
  el.textContent = message;
  el.className = 'editor-status' + (level ? ' editor-status--' + level : '');
}

function renderProblems(problems) {
  const errors = problems.filter(p => p.level === 'error').length;
  const warnings = problems.length - errors;
  if (!problems.length) {
    setStatus(t('editor.no_problems'), 'ok');
  } else {
    setStatus(t('editor.problem_count', { errors, warnings }), errors ? 'error' : 'warning');
  }
  $('editor-problems').innerHTML = problems.map(p => `
    <li class="editor-problem editor-problem--${p.level}">
      <span class="editor-problem-level">${t('editor.level_' + p.level)}</span>
      ${p.path ? `<code>${escHtml(p.path)}</code>` : ''}
      <span>${escHtml(p.message)}</span>
    </li>`).join('');
}

async function check() {
  const number = ++checkNumber;
  setStatus(t('editor.checking'));
  try {
    const d = await (await postJson('/api/config/check', { text: $('raw-config').value })).json();
    // An older answer arriving late doesn't replace a newer one.
    if (number !== checkNumber) return;
    if (d.ok) renderProblems(d.problems);
    else setStatus(t('common.error', { error: d.error || t('common.unknown') }), 'error');
  } catch (e) {
    if (number === checkNumber) setStatus(t('common.connection_error'), 'error');
  }
}

function scheduleCheck() {
  clearTimeout(checkTimer);
  checkTimer = setTimeout(check, CHECK_DELAY_MS);
}

async function loadEditor() {
  try {
    const r = await fetch('/api/config/raw');
    if (r.status === 401) { window.location.href = '/login'; return; }
    const d = await r.json();
    if (!d.ok) {
      setStatus(t('editor.load_failed', { error: d.error || t('common.unknown') }), 'error');
      return;
    }
    $('raw-config').value = d.text;
    loadedSha = d.sha256;
    markSaved('raw');
    check();
  } catch (e) {
    setStatus(t('common.connection_error'), 'error');
  }
}

// While the forms have unsaved changes, the editor is read-only: saving it
// would replace them.
function lockEditor(locked) {
  $('raw-config').readOnly = locked;
  $('editor-locked').hidden = !locked;
}

export function initConfigEditor() {
  trackSection('raw', {
    card: $('raw-config-card'),
    read: readEditor,
    reload: loadEditor,
    lock: lockEditor,
    restartNotice: $('raw-restart-notice'),
    onError: d => {
      if (d.problems) renderProblems(d.problems);
      $('editor-details').open = true;
    },
  });
  $('raw-config').addEventListener('input', scheduleCheck);
  loadEditor();
}
