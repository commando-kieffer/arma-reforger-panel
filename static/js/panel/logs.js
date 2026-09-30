// Live server console, polled from /api/logs.

const MAX_DOM_LINES = 800;
const POLL_MS = 2000;

let pollTimer = null;
let lastLogLine = '';

function colorLine(line) {
  const l = line.toLowerCase();
  if (l.includes('(e):') || l.includes('error'))  return 'err';
  if (l.includes('(w):') || l.includes('warning')) return 'warn';
  if (l.includes('online game') || l.includes('server registered')) return 'ok';
  if (line.startsWith('[---'))  return 'sep';
  return '';
}

function appendLog(text) {
  const el = document.getElementById('log-output');
  const span = document.createElement('span');
  span.className = 'log-line ' + colorLine(text);
  span.textContent = text;
  el.appendChild(span);
  el.appendChild(document.createTextNode('\n'));
  // Auto-scroll only if the user is near the bottom
  if (el.scrollHeight - el.scrollTop < el.clientHeight + 120) {
    el.scrollTop = el.scrollHeight;
  }
  // Cap the number of lines kept in the DOM
  const lines = el.querySelectorAll('.log-line');
  if (lines.length > MAX_DOM_LINES) lines[0].remove();
}

function clearLog() {
  document.getElementById('log-output').innerHTML = '';
}

async function fetchLogs(count) {
  try {
    const r = await fetch(`/api/logs?lines=${count}`);
    if (!r.ok) return;
    const d = await r.json();
    if (!d.lines || d.lines.length === 0) return;

    const el = document.getElementById('log-output');
    const lastNew = d.lines[d.lines.length - 1];

    // First load: clear and insert everything
    if (lastLogLine === '') {
      el.innerHTML = '';
      d.lines.forEach(line => appendLog(line));
      lastLogLine = lastNew;
      return;
    }

    // Later polls: append only the lines that are new
    if (lastNew === lastLogLine) return;

    const idx = d.lines.lastIndexOf(lastLogLine);
    const newLines = idx >= 0 ? d.lines.slice(idx + 1) : d.lines;
    newLines.forEach(line => appendLog(line));
    lastLogLine = lastNew;
  } catch (e) {}
}

export function initLogViewer() {
  document.getElementById('btn-clear-log').addEventListener('click', clearLog);

  clearInterval(pollTimer);
  // Fetch the last 80 lines right away,
  fetchLogs(80);
  // then poll for new lines every 2 seconds
  pollTimer = setInterval(() => fetchLogs(30), POLL_MS);
  document.getElementById('log-live-dot').classList.remove('off');
}
