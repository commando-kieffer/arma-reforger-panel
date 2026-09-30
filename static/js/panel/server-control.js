// Server status card and the start / stop / restart buttons.

import { postJson } from './api.js';
import { isBusy, setBusy, setLog } from './activity.js';
import { fetchStatus, onStatus } from './status.js';

function renderStatus(d) {
  const dot = document.getElementById('dot');
  const txt = document.getElementById('status-text');
  dot.className = 'dot ' + (d.running ? 'online' : 'offline');
  txt.className = 'status-text ' + (d.running ? 'online' : 'offline');
  txt.textContent = d.running ? 'ONLINE' : 'OFFLINE';

  document.getElementById('server-name-display').textContent = d.server_name || '—';
  document.getElementById('ip-port-display').textContent = (d.ip && d.port) ? d.ip + ':' + d.port : '—';
  document.getElementById('map-name').textContent = d.map || '—';
  document.getElementById('uptime-display').textContent = d.running ? (d.uptime || '—') : '—';

  if (!isBusy()) {
    document.getElementById('btn-start').disabled = d.running;
    document.getElementById('btn-stop').disabled  = !d.running;
    document.getElementById('btn-reset').disabled = false;
  }
}

async function serverAction(action) {
  const labels = { start: 'Uruchamianie serwera...', stop: 'Zatrzymywanie serwera...', restart: 'Restartowanie serwera...' };
  setBusy(true);
  setLog(labels[action], 'info');
  try {
    const r = await postJson('/api/' + action, {});
    const d = await r.json();
    if (d.ok) {
      const success = { start: 'Serwer uruchomiony', stop: 'Serwer zatrzymany', restart: 'Serwer zrestartowany' };
      setLog(success[action], 'ok');
      await new Promise(res => setTimeout(res, 1500));
      await fetchStatus();
    } else {
      setLog('Błąd: ' + (d.error || 'nieznany'), 'error');
    }
  } catch (e) { setLog('Błąd połączenia', 'error'); }
  setBusy(false);
}

export function initServerControl() {
  onStatus(renderStatus);
  document.querySelectorAll('[data-server-action]').forEach(btn => {
    btn.addEventListener('click', () => serverAction(btn.dataset.serverAction));
  });
}
