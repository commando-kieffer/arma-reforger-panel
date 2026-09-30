// Players card at the end of the page, and the player count in the status
// card. /api/players is fetched along with each status refresh.

import { t, tn } from '../i18n.js';
import { escHtml } from './format.js';
import { onStatus } from './status.js';

function fmtDuration(seconds) {
  if (seconds < 60) return t('players.seconds', { n: seconds });
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return t('players.minutes', { n: minutes });
  return t('players.hours', { h: Math.floor(minutes / 60), m: String(minutes % 60).padStart(2, '0') });
}

function renderTable(players) {
  // Some servers report 0 for every player; the column is useless then.
  const showDuration = players.some(p => p.duration > 0);
  const rows = players.map(p => {
    const name = p.name ? escHtml(p.name) : `<span class="connecting">${t('players.connecting')}</span>`;
    const duration = showDuration ? `<td>${p.duration ? fmtDuration(p.duration) : '—'}</td>` : '';
    return `<tr><td>${name}</td>${duration}</tr>`;
  }).join('');
  const durationHeader = showDuration ? `<th>${t('players.col_duration')}</th>` : '';
  return `
    <table class="players-table">
      <thead><tr><th>${t('players.col_name')}</th>${durationHeader}</tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

function render(d) {
  const summary = document.getElementById('players-summary');
  const list = document.getElementById('players-list');
  document.getElementById('players-display').textContent = d.state === 'ok' ? `${d.count} / ${d.max}` : '—';

  if (d.state !== 'ok') {
    summary.textContent = t('players.state_' + d.state);
    list.innerHTML = '';
    return;
  }
  summary.textContent = tn('players.connected', d.count, { max: d.max });
  if (d.players === null) {
    list.innerHTML = `<div class="card-help">${t('players.no_list')}</div>`;
  } else {
    list.innerHTML = d.players.length ? renderTable(d.players) : '';
  }
}

async function fetchPlayers() {
  try {
    const r = await fetch('/api/players');
    if (r.status === 401) { window.location.href = '/login'; return; }
    render(await r.json());
  } catch (e) {
    // Leave the last known state; the status poll reports connection errors.
  }
}

export function initPlayers() {
  onStatus(() => fetchPlayers());
}
