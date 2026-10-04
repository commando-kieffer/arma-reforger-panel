// Panel settings dialog, opened from the header. The settings are the same for
// everyone, and the page is reloaded once they are saved so they take effect.

import { t } from '../i18n.js';
import { postJson } from './api.js';

const $ = id => document.getElementById(id);

export function initSettings() {
  const dialog = $('settings-dialog');
  const select = $('settings-theme');
  const error = $('settings-error');
  const saveButton = $('btn-settings-save');
  const savedTheme = select.value;

  function showError(message) {
    error.textContent = message;
    error.hidden = false;
  }

  $('btn-settings').addEventListener('click', () => {
    select.value = savedTheme;
    error.hidden = true;
    dialog.showModal();
  });

  dialog.querySelectorAll('[data-dialog-close]').forEach(btn => {
    btn.addEventListener('click', () => dialog.close());
  });
  // The form fills the dialog, so a click on the dialog itself is on the backdrop.
  dialog.addEventListener('click', event => {
    if (event.target === dialog) dialog.close();
  });

  $('settings-form').addEventListener('submit', async event => {
    event.preventDefault();
    if (saveButton.disabled) return;
    if (select.value === savedTheme) { dialog.close(); return; }
    saveButton.disabled = true;
    error.hidden = true;
    try {
      const d = await (await postJson('/api/settings', { theme: select.value })).json();
      if (d.ok) { window.location.reload(); return; }
      showError(t('common.error', { error: d.error || t('common.unknown') }));
    } catch (e) {
      showError(t('common.connection_error'));
    }
    saveButton.disabled = false;
  });
}
