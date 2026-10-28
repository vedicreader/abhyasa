// The Settings page. The − and + buttons and the sliders of a setting row are in core.js, as the Profile page has rows too.
// "Find a setting" shows only the rows whose label or help has the words, and opens the "More" parts that hold them.
(() => {
  document.addEventListener('input', e => { if (e.target.id === 'sfind') find(e.target.value); });
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
