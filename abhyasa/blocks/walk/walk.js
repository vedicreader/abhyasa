// The walk keys, for the left hand: ⌥S presses the main button (core.js): Send (or Run the tests) while a check is open, then Next idea.
// ⌥W asks for a hint, and ⌘↵ sends the answer. Skip this idea is a quiet link with no key.
abhyasaKeys.KeyW = '#hint';
abhyasaKeys.KeyV = '.walk-demo #keep';   // ⌥V keeps the state of a demo

if (!window.abhyasaWalk) {
  window.abhyasaWalk = true;
  // After a check card loads or changes, the cursor goes to the answer box, or to Next idea when the check is closed.
  document.addEventListener('htmx:afterSettle', e => {
    if (!e.detail.target || e.detail.target.id !== 'check') return;
    const f = document.querySelector('#check #ans, #check .go');
    if (f) f.focus({preventScroll: true, focusVisible: false});
  });

  // A figure that does not load goes out of sight, so the page shows no broken image. Its alt text stays for a screen reader.
  const gone = img => img.closest('#figure')?.classList.add('gone');
  document.addEventListener('error', e => { if (e.target.matches && e.target.matches('#figure img')) gone(e.target); }, true);
  const check = () => document.querySelectorAll('#figure img').forEach(i => { if (i.complete && !i.naturalWidth) gone(i); });
  window.addEventListener('load', check); document.addEventListener('htmx:afterSettle', check);

  // The draft in the answer box is kept in sessionStorage by the id of the question, so a reload or a side walk in the same tab
  // does not lose it. It goes when you send the answer.
  const root = document.documentElement, KEY = 'rh-draft:';
  const qid = () => document.querySelector('#check form[data-qid]')?.dataset.qid;
  document.addEventListener('input', e => {
    if (e.target.id !== 'ans' || !e.target.closest('#check') || !qid()) return;
    if (e.target.value) sessionStorage.setItem(KEY + qid(), e.target.value); else sessionStorage.removeItem(KEY + qid());
  });
  document.addEventListener('htmx:afterRequest', e => {
    const f = e.detail.elt;
    if (e.detail.successful && f && f.matches && f.matches('#check form[data-qid]')) sessionStorage.removeItem(KEY + f.dataset.qid);
  });
  const restore = () => {
    const a = document.querySelector('#check #ans'), d = qid() && sessionStorage.getItem(KEY + qid());
    if (a && d && !a.value) { a.value = d; a.dispatchEvent(new Event('input', {bubbles: true})); }
  };

  // While a side walk is open in the pane, the check says that it waits, and that the draft is kept.
  const held = () => {
    const c = document.querySelector('#check .check'), pane = document.getElementById('rh-pane');
    const on = root.classList.contains('rh-open') && pane?.checkVisibility() && c && c.querySelector('#ans');   // under 1100 px the pane does not show
    c?.querySelector('.held')?.remove();
    if (!on) return;
    const name = document.querySelector('#rh-pane .rh-trail b')?.textContent.trim() || 'the other idea';
    const p = Object.assign(document.createElement('p'), {className: 'held mute', textContent: `Held while you learn ${name}. Your draft is kept.`});
    c.querySelector('.lbl')?.after(p);
  };
  new MutationObserver(held).observe(root, {attributes: true, attributeFilter: ['class']});
  document.addEventListener('htmx:afterSettle', e => { if (e.detail.target && e.detail.target.id === 'check') { restore(); held(); } });

  // In the side pane, "Back to the paper" closes one level of the pane, as ⌥Z does, and does not load the paper in the pane.
  document.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('a.walk-back');
    if (!a || !root.classList.contains('in-pane') || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault(); parent.postMessage({type: 'rh:close', level: 1}, location.origin);
  });

  // A demo or an order check: each prediction goes to the walk, which logs it with the step.
  const say = (card, text) => { const s = card.querySelector('.said'); if (s) s.textContent = text; };
  const post = (card, url, body, done) => fetch(url, {method: 'POST', body: new URLSearchParams(body)})
    .then(r => { say(card, r.ok ? done : 'The tutor did not save this. Try again.'); return r.ok; }).catch(() => say(card, 'The tutor did not save this. Try again.'));
  // The first prediction closes a demo check: Next idea shows in the card and becomes the main button, and the skip goes.
  const shut = card => {
    const go = card.querySelector('.go-on');
    if (!go || !go.hidden) return;
    go.hidden = false; card.classList.add('shut');
  };
  document.addEventListener('rk-predict', e => {
    const card = e.target.closest && e.target.closest('.walk-demo');
    if (!card) return;
    const d = e.detail;
    post(card, card.dataset.url, {slug: card.dataset.demo, gate: d.gate, picked: String(d.picked), ans: String(d.ans), ok: String(d.ok),
                                  why: d.why || '', context: d.context || ''}, 'Your prediction is saved.').then(ok => ok && shut(card));
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

  // The code editor: Tab adds 4 spaces, and Shift-Tab takes away up to 4. ⌘↵ runs the tests (core.js presses the Run button).
  document.addEventListener('keydown', e => {
    const t = e.target;
    if (e.key !== 'Tab' || e.altKey || e.metaKey || e.ctrlKey || !t.matches || !t.matches('.code-editor')) return;
    e.preventDefault();
    const v = t.value, a = t.selectionStart, b = t.selectionEnd;
    if (!e.shiftKey && a === b) { t.setRangeText('    ', a, b, 'end'); return; }
    const from = v.lastIndexOf('\n', a - 1) + 1, lines = v.slice(from, b).split('\n');
    const out = lines.map(l => e.shiftKey ? l.replace(/^ {1,4}/, '') : '    ' + l).join('\n');
    t.setRangeText(out, from, b, 'select');
    t.setSelectionRange(Math.max(from, a + (out.length - (b - from)) * 0 + (lines[0].length - out.split('\n')[0].length) * -1), from + out.length);
  });
}
