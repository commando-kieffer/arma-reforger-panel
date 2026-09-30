// Form controls bound to config.json settings by name: <input data-field="max_players">.
// Yes/No selects use the values "true"/"false" and are read as booleans;
// number inputs are read as numbers, and left empty they become null, which
// the server rejects with a proper message.

export function fillFields(container, values) {
  container.querySelectorAll('[data-field]').forEach(el => {
    const value = values[el.dataset.field];
    if (value !== undefined) el.value = String(value);
  });
}

export function readFields(container) {
  const values = {};
  container.querySelectorAll('[data-field]').forEach(el => {
    const name = el.dataset.field;
    if (el.tagName === 'SELECT' && (el.value === 'true' || el.value === 'false')) {
      values[name] = el.value === 'true';
    } else if (el.type === 'number') {
      values[name] = el.value.trim() === '' ? null : Number(el.value);
    } else {
      values[name] = el.value;
    }
  });
  return values;
}
