// Feedback on the operation in progress: the "Last operation" line, and the
// busy flag that locks the action buttons while a request is running.

const ACTION_BUTTON_IDS = ['btn-start', 'btn-stop', 'btn-reset', 'btn-save', 'btn-persist-save', 'btn-persist-flush'];

let busy = false;

export function setLog(msg, type = 'info') {
  const el = document.getElementById('log-msg');
  el.className = 'log-entry ' + type;
  const ts = new Date().toLocaleTimeString('pl-PL');
  el.textContent = '[' + ts + '] ' + msg;
}

export function isBusy() {
  return busy;
}

export function setBusy(state) {
  busy = state;
  ACTION_BUTTON_IDS.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = state;
  });
}
