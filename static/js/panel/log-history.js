// Log history card: one row per server session, each downloadable as a zip
// of its log files. The live viewer's download button points at the newest one.

import { t } from '../i18n.js';
import { escHtml, fmtBytes } from './format.js';
import { onStatus } from './status.js';

let running = null;

function downloadUrl(name) {
  return `/api/logs/sessions/${encodeURIComponent(name)}/download`;
}

function renderSession(session, isCurrent) {
  const files = Object.entries(session.files)
    .map(([name, size]) => `${escHtml(name)} ${fmtBytes(size)}`)
    .join(' · ');
  const badge = isCurrent ? `<span class="badge">${t('logs.current')}</span>` : '';
  const download = files
    ? `<a class="btn btn-outline btn-sm" href="${downloadUrl(session.name)}" download>${t('logs.download')}</a>`
    : '';
  return `
    <div class="log-session">
      <div class="log-session-info">
        <div class="log-session-title">
          ${escHtml(session.started)}
          <span class="log-session-size">${fmtBytes(session.size)}</span>
          ${badge}
        </div>
        <div class="log-session-files">${files || t('logs.no_files')}</div>
      </div>
      ${download}
    </div>`;
}

function render(sessions, logDir) {
  const list = document.getElementById('log-history');
  const liveDownload = document.getElementById('btn-download-log');
  if (!sessions.length) {
    list.innerHTML = `<div class="mods-placeholder is-empty">${t('logs.history_empty', { path: escHtml(logDir) })}</div>`;
    liveDownload.hidden = true;
    return;
  }
  // The newest session is the one being written while the server runs.
  list.innerHTML = sessions.map((s, i) => renderSession(s, i === 0 && running)).join('');
  liveDownload.href = downloadUrl(sessions[0].name);
  liveDownload.hidden = Object.keys(sessions[0].files).length === 0;
}

async function fetchLogHistory() {
  try {
    const r = await fetch('/api/logs/sessions');
    if (r.status === 401) { window.location.href = '/login'; return; }
    const d = await r.json();
    render(d.sessions || [], d.log_dir || '');
  } catch (e) {
    document.getElementById('log-history').innerHTML =
      `<div class="mods-placeholder is-empty">${t('logs.history_failed')}</div>`;
  }
}

export function initLogHistory() {
  document.getElementById('btn-refresh-log-history').addEventListener('click', fetchLogHistory);
  // Starting the server creates a new session and stopping it ends the
  // current one, so reload the list whenever the running state changes.
  onStatus(d => {
    if (d.running === running) return;
    running = d.running;
    fetchLogHistory();
  });
}
