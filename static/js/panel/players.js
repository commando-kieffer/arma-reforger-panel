// Players card at the end of the page, and the player count in the status
// card. /api/players is fetched along with each status refresh.

import { t, tn } from '../i18n.js';
import { postJson } from './api.js';
import { setLog } from './activity.js';
import { escHtml } from './format.js';
import { onStatus } from './status.js';

let kicking = false;

function fmtDuration(seconds) {
  if (seconds < 60) return t('players.seconds', { n: seconds });
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return t('players.minutes', { n: minutes });
  return t('players.hours', { h: Math.floor(minutes / 60), m: String(minutes % 60).padStart(2, '0') });
}

function renderTable(players, canKick) {
  // Player numbers and identity IDs come with the RCON list, durations with
  // the A2S one.
  const fromRcon = players.some(p => p.uid);
  // Some servers report 0 for every player; the column is useless then.
  const showDuration = players.some(p => p.duration > 0);
  const kick = fromRcon && canKick;
  const rows = players.map(p => {
    const name = p.name ? escHtml(p.name) : `<span class="connecting">${t('players.connecting')}</span>`;
    const number = fromRcon ? `<td class="player-number">${escHtml(String(p.id))}</td>` : '';
    const uid = fromRcon ? `<td class="player-id">${escHtml(p.uid || '')}</td>` : '';
    const duration = showDuration ? `<td class="duration">${p.duration ? fmtDuration(p.duration) : '—'}</td>` : '';
    const action = kick
      ? `<td class="player-action"><button type="button" class="mod-remove" data-kick-id="${escHtml(String(p.id))}"
           data-kick-uid="${escHtml(p.uid)}" data-kick-name="${escHtml(p.name || p.uid)}">${t('players.kick')}</button></td>`
      : '';
    return `<tr>${number}<td>${name}</td>${uid}${duration}${action}</tr>`;
  }).join('');
  const headers = [
    fromRcon ? `<th class="player-number">${t('players.col_number')}</th>` : '',
    `<th>${t('players.col_name')}</th>`,
    fromRcon ? `<th>${t('players.col_id')}</th>` : '',
    showDuration ? `<th class="duration">${t('players.col_duration')}</th>` : '',
    kick ? '<th></th>' : '',
  ].join('');
  const hint = fromRcon && !canKick ? `<div class="card-help">${t('players.kick_unavailable')}</div>` : '';
  return `
    <table class="players-table">
      <thead><tr>${headers}</tr></thead>
      <tbody>${rows}</tbody>
    </table>${hint}`;
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
    list.innerHTML = `<div class="card-help">${t('players.list_' + d.list_state)}</div>`;
  } else {
    list.innerHTML = d.players.length ? renderTable(d.players, d.can_kick) : '';
  }
}

async function fetchPlayers() {
  // The table is rebuilt from each answer: not while a kick is waiting for
  // the player to leave.
  if (kicking) return;
  try {
    const r = await fetch('/api/players');
    if (r.status === 401) { window.location.href = '/login'; return; }
    render(await r.json());
  } catch (e) {
    // Leave the last known state; the status poll reports connection errors.
  }
}

async function kickPlayer(button) {
  const { kickId, kickUid, kickName } = button.dataset;
  if (kicking || !confirm(t('players.confirm_kick', { name: kickName }))) return;
  kicking = true;
  button.disabled = true;
  setLog(t('players.kicking', { name: kickName }), 'info');
  try {
    const d = await (await postJson('/api/players/kick', { id: Number(kickId), uid: kickUid })).json();
    if (d.ok) setLog(t('players.kicked', { name: d.name || kickName }), 'ok');
    else setLog(t('common.error', { error: d.error || t('common.unknown') }), 'error');
  } catch (e) {
    setLog(t('common.connection_error'), 'error');
  }
  kicking = false;
  await fetchPlayers();
}

export function initPlayers() {
  onStatus(() => fetchPlayers());
  document.getElementById('players-list').addEventListener('click', event => {
    const button = event.target.closest('[data-kick-id]');
    if (button) kickPlayer(button);
  });
}
