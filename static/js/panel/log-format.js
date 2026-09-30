// Lines up the columns of console.log lines in the live viewer.
//
// The server writes "HH:MM:SS.mmm CATEGORY     : message", where the category
// field (name, padding, then "(W)" or "(E)" for warnings and errors) is 13
// characters wide. Some lines have extra spaces after the time, which shift
// everything after them; alignLogLine() drops those. Only the display changes,
// the downloaded log files are untouched.

const LINE_RE = /^(\d{2}:\d{2}:\d{2}\.\d{3}) +([A-Za-z][\w.]*)(?: *(\([A-Z]\)))? *: ?(.*)$/;
const FIELD_WIDTH = 13;

// Returns the realigned line, or null when it isn't a "time category: message"
// line (continuation lines, blank lines, separators), which are shown as is.
export function alignLogLine(line) {
  const m = LINE_RE.exec(line);
  if (!m) return null;
  const [, time, category, marker, message] = m;
  const field = marker
    ? category + ' '.repeat(Math.max(1, FIELD_WIDTH - category.length - marker.length)) + marker
    : category.padEnd(FIELD_WIDTH);
  return `${time} ${field}: ${message}`.trimEnd();
}
