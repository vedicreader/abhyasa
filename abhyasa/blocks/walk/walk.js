// The walk keys, for the left hand: ⌥S presses the main button (core.js): Send while a check is open, else Next idea. ⌥W asks for a hint, and ⌘↵ sends the answer.
abhyasaKeys.KeyW = '#hint';

if (!window.abhyasaWalk) {
  window.abhyasaWalk = true;
  // After a check card loads or changes, the cursor goes to the answer box, or to Next idea when the check is closed.
  document.addEventListener('htmx:afterSettle', e => {
    if (!e.detail.target || e.detail.target.id !== 'check') return;
    const f = document.querySelector('#check #ans, #check .go');
    if (f) f.focus({preventScroll: true});
  });

  // A demo or an order check: each prediction goes to the walk, which logs it with the step.
  const say = (card, text) => { const s = card.querySelector('.said'); if (s) s.textContent = text; };
  const post = (card, url, body, done) => fetch(url, {method: 'POST', body: new URLSearchParams(body)})
    .then(r => say(card, r.ok ? done : 'The tutor did not save this. Try again.')).catch(() => say(card, 'The tutor did not save this. Try again.'));
  document.addEventListener('rk-predict', e => {
    const card = e.target.closest && e.target.closest('.walk-demo');
    if (!card) return;
    const d = e.detail;
    post(card, card.dataset.url, {slug: card.dataset.demo, gate: d.gate, picked: String(d.picked), ans: String(d.ans), ok: String(d.ok),
                                  why: d.why || '', context: d.context || ''}, 'Your prediction is saved.');
  });

  // Keep this state (K): save the inputs of the demo with your last prediction.
  const keep = card => {
    const host = card.querySelector('[data-rupaka]'), s = host && host.rupaka;
    if (!s) return;
    const st = Object.fromEntries(Object.keys(s.spec.state || {}).map(k => [k, s.st[k]]));
    post(card, card.dataset.keep, {state: JSON.stringify(st)}, 'The state is saved.');
  };
  document.addEventListener('click', e => {
    const b = e.target.closest && e.target.closest('.walk-demo #keep');
    if (b) keep(b.closest('.walk-demo'));
  });
  document.addEventListener('keydown', e => {
    const t = e.target, inBox = t.matches && t.matches('textarea, input, select, [contenteditable]');
    if (e.key !== 'k' || inBox || e.altKey || e.metaKey || e.ctrlKey || e.shiftKey) return;
    const b = document.querySelector('.walk-demo #keep');
    if (b) { e.preventDefault(); b.click(); }
  });
}
