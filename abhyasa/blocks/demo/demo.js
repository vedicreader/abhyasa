// Each prediction in a demo goes to the server as an attempt with kind 'demo'. ⌥E shows the demo of a concept.
abhyasaKeys.KeyE = '#show-demo';
if (!window.abhyasaDemo) {
  window.abhyasaDemo = true;
  document.addEventListener('rk-predict', e => {
    const card = e.target.closest && e.target.closest('.demo-card');
    if (!card) return;
    e.preventDefault();   // the gate shows the answer only when the save works
    const d = e.detail, body = new URLSearchParams({gate: d.gate, picked: String(d.picked), ans: String(d.ans), ok: String(d.ok),
                                                     why: d.why || '', context: d.context || '', session: card.dataset.session || ''});
    const no = 'The tutor did not save this. Try again.';
    fetch(card.dataset.url, {method: 'POST', body}).then(r => d.settle(r.ok, no)).catch(() => d.settle(false, no));
  });
}
