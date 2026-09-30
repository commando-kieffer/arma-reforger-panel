import { initLanguageSwitch, t } from './i18n.js';

const form = document.getElementById('login-form');
const passwordInput = document.getElementById('pwd');
const loginButton = document.getElementById('btn-login');
const errorBox = document.getElementById('err');

async function doLogin() {
  loginButton.disabled = true;
  try {
    const r = await fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: passwordInput.value }),
    });
    if (r.ok) { window.location.href = '/'; return; }
    let msg = t('login.invalid_password');
    if (r.status === 429) msg = t('login.too_many_attempts');
    try { const d = await r.json(); if (d && d.error) msg = d.error; } catch (e) {}
    errorBox.textContent = msg;
    passwordInput.classList.add('invalid');
    setTimeout(() => { errorBox.textContent = ''; passwordInput.classList.remove('invalid'); }, 2500);
  } finally {
    loginButton.disabled = false;
  }
}

form.addEventListener('submit', event => {
  event.preventDefault();
  doLogin();
});
initLanguageSwitch();

if ('serviceWorker' in navigator) navigator.serviceWorker.register('/service-worker.js').catch(() => {});
