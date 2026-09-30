// Entry point of the panel page.

import { initLanguageSwitch } from '../i18n.js';
import { initGameplay } from './gameplay.js';
import { initLogHistory } from './log-history.js';
import { initLogViewer } from './logs.js';
import { initMetrics } from './metrics.js';
import { initMods } from './mods.js';
import { initPasswordToggles } from './password-toggle.js';
import { fetchPersistence, initPersistence } from './persistence.js';
import { initPlayers } from './players.js';
import { initServerConfig } from './server-config.js';
import { initServerControl } from './server-control.js';
import { fetchStatus, startCountdown } from './status.js';

async function doLogout() {
  await fetch('/logout', { method: 'POST' });
  window.location.href = '/login';
}

initMetrics();
initLogViewer();

// Status listeners run in registration order, top of the page first.
initServerControl();
initServerConfig();
initGameplay();
initMods();
initPersistence();
initLogHistory();
initPlayers();

document.getElementById('btn-logout').addEventListener('click', doLogout);
initLanguageSwitch();
initPasswordToggles();

fetchStatus().then(() => { fetchPersistence(); startCountdown(); });

// PWA — service worker registration
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js')
      .catch(err => console.log('SW error:', err));
  });
}
