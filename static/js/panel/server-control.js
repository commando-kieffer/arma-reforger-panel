// Server status card and the start / stop / restart buttons.

import { t } from '../i18n.js';
import { postJson } from './api.js';
import { isBusy, setBusy, setLog } from './activity.js';
import { fetchStatus, onStatus } from './status.js';

const PENDING_KEYS = { start: 'controls.starting', stop: 'controls.stopping', restart: 'controls.restarting' };
const DONE_KEYS = { start: 'controls.started', stop: 'controls.stopped', restart: 'controls.restarted' };

function renderStatus(d) {
  const dot = document.getElementById('dot');
  const txt = document.getElementById('status-text');
  dot.className = 'dot ' + (d.running ? 'online' : 'offline');
  txt.className = 'status-text ' + (d.running ? 'online' : 'offline');
  txt.textContent = d.running ? t('status.online') : t('status.offline');

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
  setBusy(true);
  setLog(t(PENDING_KEYS[action]), 'info');
  try {
    const r = await postJson('/api/' + action, {});
    const d = await r.json();
    if (d.ok) {
      setLog(t(DONE_KEYS[action]), 'ok');
      await new Promise(res => setTimeout(res, 1500));
      await fetchStatus();
    } else {
      setLog(t('common.error', { error: d.error || t('common.unknown') }), 'error');
    }
  } catch (e) { setLog(t('common.connection_error'), 'error'); }
  setBusy(false);
}

export function initServerControl() {
  onStatus(renderStatus);
  document.querySelectorAll('[data-server-action]').forEach(btn => {
    btn.addEventListener('click', () => serverAction(btn.dataset.serverAction));
  });
}
