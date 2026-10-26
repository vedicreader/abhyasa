// The goal box: ⌘↵ plans (core.js sends the form). A plan takes a while, so the box stays read only until the reply comes.
if (!window.abhyasaJourneys) {
  window.abhyasaJourneys = true;
  document.addEventListener('htmx:beforeRequest', e => { const f = e.detail.elt.closest && e.detail.elt.closest('.goal-form'); if (f) f.querySelector('textarea').readOnly = true; });
  document.addEventListener('htmx:afterRequest', e => { const f = e.detail.elt.closest && e.detail.elt.closest('.goal-form'); if (f) f.querySelector('textarea').readOnly = false; });
}
