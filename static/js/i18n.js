// Translations for the active language, embedded in the page by the server
// (templates/partials/i18n_data.html). Same keys and {placeholder} syntax as
// arma_panel/i18n.py.

const COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

const { lang, locale, messages } = JSON.parse(document.getElementById('i18n-data').textContent);
const pluralRules = new Intl.PluralRules(locale);

export { lang, locale };

export function t(key, params = {}) {
  const template = messages[key] ?? key;
  return template.replace(/\{(\w+)\}/g, (match, name) => (name in params ? String(params[name]) : match));
}

// Count-dependent message: picks the `one` / `other` variant of `key`.
export function tn(key, count, params = {}) {
  const pluralKey = `${key}.${pluralRules.select(count)}`;
  return t(pluralKey in messages ? pluralKey : `${key}.other`, { count, ...params });
}

export function initLanguageSwitch() {
  document.querySelectorAll('[data-lang]').forEach(button => {
    button.addEventListener('click', () => {
      if (button.dataset.lang === lang) return;
      document.cookie = `lang=${button.dataset.lang}; path=/; max-age=${COOKIE_MAX_AGE}; SameSite=Lax`;
      window.location.reload();
    });
  });
}
