// POST helpers for the panel API. Every state-changing call carries the CSRF
// token both as a header and in the body.

let csrfToken = '';

export function setCsrfToken(token) {
  csrfToken = token;
}

async function refreshCsrfToken() {
  try {
    const r = await fetch('/api/csrf');
    if (r.ok) csrfToken = (await r.json()).csrf || '';
  } catch (e) {}
}

export async function postJson(url, body) {
  if (!csrfToken) await refreshCsrfToken();
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken },
    body: JSON.stringify({ ...(body || {}), _csrf: csrfToken }),
  });
  if (r.status === 401) { window.location.href = '/login'; throw new Error('unauthorized'); }
  if (r.status === 403) {
    // CSRF expired — refresh token and surface error
    await refreshCsrfToken();
  }
  return r;
}

export async function postForm(url, formData) {
  if (!csrfToken) await refreshCsrfToken();
  formData.append('_csrf', csrfToken);
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrfToken },
    body: formData,
  });
  if (r.status === 401) { window.location.href = '/login'; throw new Error('unauthorized'); }
  return r;
}
