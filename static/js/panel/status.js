// Polls /api/status and passes each response to the registered listeners.

import { setCsrfToken } from './api.js';
import { setLog } from './activity.js';

const REFRESH_SECONDS = 10;

const listeners = [];
let refreshInterval = null;
let countdown = REFRESH_SECONDS;

export function onStatus(listener) {
  listeners.push(listener);
}

export async function fetchStatus() {
  try {
    const r = await fetch('/api/status');
    if (r.status === 401) { window.location.href = '/login'; return; }
    const d = await r.json();
    if (d.csrf) setCsrfToken(d.csrf);
    listeners.forEach(listener => listener(d));
  } catch (e) {
    setLog('Connection error', 'error');
  }
}

export function startCountdown() {
  const timer = document.getElementById('refresh-timer');
  countdown = REFRESH_SECONDS;
  timer.textContent = countdown;
  clearInterval(refreshInterval);
  refreshInterval = setInterval(() => {
    countdown--;
    timer.textContent = countdown;
    if (countdown <= 0) { fetchStatus(); countdown = REFRESH_SECONDS; }
  }, 1000);
}
