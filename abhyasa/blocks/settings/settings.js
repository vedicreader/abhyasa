// The Settings page: the − and + buttons and the sliders move the number box, and the box saves (htmx, after 400 ms).
// "Find a setting" shows only the rows whose label or help has the words, and opens the "More" parts that hold them.
(() => {
  const box = el => document.getElementById(el.dataset.box);
  const send = b => b.dispatchEvent(new Event('change', {bubbles: true}));
  document.addEventListener('click', e => {
    const s = e.target.closest('[data-step]');
    if (!s || !box(s)) return;
    const b = box(s);
    Number(s.dataset.step) > 0 ? b.stepUp() : b.stepDown();
    send(b);
  });
  document.addEventListener('input', e => {
    const r = e.target.closest('input[type=range][data-box]');
    if (r && box(r)) { box(r).value = r.value; box(r).dispatchEvent(new Event('input', {bubbles: true})); }
    const b = e.target.closest('.slide input[type=number]');
    if (b) { const r2 = b.parentElement.querySelector('input[type=range]'); if (r2) r2.value = b.value; }
    if (e.target.id === 'sfind') find(e.target.value);
  });
  function find(q) {
    const ws = q.toLowerCase().split(/\s+/).filter(Boolean);
    document.querySelectorAll('.sgroup').forEach(g => {
      let any = !ws.length;
      g.querySelectorAll('[data-find]').forEach(r => {
        const hit = ws.every(w => r.dataset.find.includes(w));
        r.hidden = ws.length > 0 && !hit;
        if (hit && ws.length) { any = true; const d = r.closest('details.more'); if (d) d.open = true; }
      });
      g.hidden = ws.length > 0 && !any;
      const ix = document.getElementById('ix-' + g.id.slice(2));
      if (ix) ix.hidden = g.hidden;
    });
  }
})();
