// Each prediction in a demo goes to the server as an attempt with kind 'demo', with the ask of the demo when you asked for it.
// ⌥E presses Show me: the demo of a concept, a walk step or the open question of a session.
// `?show=<words>` on the page (the link "Open in abhyasa" of the Mac guide) presses Show me once, with the words.
abhyasaKeys.KeyE = '#show-demo';
if (!window.abhyasaDemo) {
  window.abhyasaDemo = true;
  const press = () => {
    const want = new URLSearchParams(location.search).get('show'), b = document.getElementById('show-demo');
    if (want === null || !b || b.dataset.pressed || !window.htmx) return;
    b.dataset.pressed = '1';
    b.setAttribute('hx-vals', JSON.stringify({...JSON.parse(b.getAttribute('hx-vals') || '{}'), said: want.slice(0, 300)}));
    htmx.process(b); b.click();
  };
  if (document.readyState === 'complete') press(); else addEventListener('load', press, {once: true});
  document.addEventListener('rk-predict', e => {
    const card = e.target.closest && e.target.closest('.demo-card');
    if (!card) return;
    e.preventDefault();   // the gate shows the answer only when the save works
    const d = e.detail, body = new URLSearchParams({gate: d.gate, picked: String(d.picked), ans: String(d.ans), ok: String(d.ok),
                                                     why: d.why || '', context: d.context || '', session: card.dataset.session || '',
                                                     ask: card.dataset.ask || ''});
    const no = 'The tutor did not save this. Try again.';
    fetch(card.dataset.url, {method: 'POST', body}).then(r => d.settle(r.ok, no)).catch(() => d.settle(false, no));
  });
}
