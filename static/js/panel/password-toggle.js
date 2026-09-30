// Show/hide buttons for password inputs. A button with
// data-password-toggle="<input id>" switches that input between masked and
// plain text on each click.

import { t } from '../i18n.js';

function setVisible(button, input, visible) {
  input.type = visible ? 'text' : 'password';
  button.textContent = visible ? t('common.hide_password') : t('common.show_password');
  button.setAttribute('aria-pressed', String(visible));
}

export function initPasswordToggles() {
  document.querySelectorAll('[data-password-toggle]').forEach(button => {
    const input = document.getElementById(button.dataset.passwordToggle);
    if (!input) return;
    button.setAttribute('aria-controls', input.id);
    setVisible(button, input, false);
    button.addEventListener('click', () => setVisible(button, input, input.type === 'password'));
  });
}
