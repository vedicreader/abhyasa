// Rabbit holes (the detour block). ⌥B opens the offer to learn a missing idea: for the selected term in the passage, else for the
// gap that your answer points at, else for the first idea in the needs line that you have not learned. In the offer, 1, 2 and 3
// choose and Esc closes it. 1 or 2 opens the side walk in the side pane (pane.js); 3 opens it in a new tab.
// When the pane closes (⌥Z, Esc, ×, or the end of the side walk), the page asks the server to keep the result on the step
// (/rh/back) and puts the new needs line in place. The page is not drawn again, so its scroll and the draft in the answer box stay.
if (!window.abhyasaDetour) {
  window.abhyasaDetour = true;
  const root = document.documentElement, inPane = () => root.classList.contains('in-pane');
  const box = () => document.getElementById('rh-offer');
  const at = () => document.querySelector('.rh-needs')?.dataset.at;
  const isOpen = () => !!box()?.querySelector('.rh-offer-card');
  let tool = null;
  const hideTool = () => { tool?.remove(); tool = null; };
  const shut = () => { box()?.replaceChildren(); hideTool(); };
  const say = text => { const c = box()?.querySelector('.rh-offer-card'); if (!c) return; let p = c.querySelector('.req-err');
    if (!p) { p = document.createElement('p'); p.className = 'req-err'; c.append(p); } p.textContent = text; };

  // One quiet tip under the first passage of a walk, shown once (the flag in localStorage): you can select a word. It goes after one use.
  const TIP = 'rh-tip';
  const tip = () => {
    const p = document.getElementById('passage');
    if (!p || !at() || inPane() || localStorage.getItem(TIP) || document.querySelector('.rh-tip')) return;
    localStorage.setItem(TIP, '1');
    p.after(Object.assign(document.createElement('p'), {className: 'rh-tip', textContent: 'Select a word that you do not know, then press ⌥B.'}));
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', tip); else tip();
  document.addEventListener('htmx:afterSettle', e => { if (e.detail.target === document.body) tip(); });

  const offer = t => {
    const b = box(), a = at();
    if (!b || !a || !t) return false;
    hideTool(); document.querySelector('.rh-tip')?.remove();
    htmx.ajax('GET', `/rh/term?${new URLSearchParams({t, at: a})}`, {target: b, swap: 'innerHTML'}).then(() => {
      (b.querySelector('.rh-way.pick') || b.querySelector('.rh-way, button'))?.focus({preventScroll: true});
      b.scrollIntoView({block: 'nearest', behavior: abhyasaMotion() ? 'smooth' : 'auto'});
    });
    return true;
  };
  const choose = w => {
    const how = w.dataset.how, tab = how === 'session' ? window.open('', '_blank') : null;   // opened now, in the key press, so no pop-up block
    box().querySelectorAll('.rh-way').forEach(x => x.disabled = true);
    fetch('/rh/open', {method: 'POST', body: new URLSearchParams({slug: w.dataset.slug, at: at(), how})})
      .then(r => r.ok ? r.json() : Promise.reject(r))
      .then(r => {
        shut();
        if (r.how !== 'session') { tab?.close(); window.abhyasaPane.open(r.url, r.title); }
        else if (tab) tab.location = r.url;
        else if (!window.open(r.url, '_blank')) location.assign(r.url);
      })
      .catch(() => { tab?.close(); box().querySelectorAll('.rh-way').forEach(x => x.disabled = false); say('The tutor could not make the side walk. Try again.'); });
  };

  // The selected term in the passage, at most 80 characters, or ''.
  const picked = () => {
    const s = getSelection(), t = s ? String(s).trim() : '', p = document.getElementById('passage');
    return t && t.length <= 80 && s.rangeCount && p && p.contains(s.getRangeAt(0).commonAncestorContainer) ? t : '';
  };
  document.addEventListener('mouseup', e => {
    if (e.target.closest && e.target.closest('#rh-sel')) return;
    setTimeout(() => {
      hideTool();
      const t = picked();
      if (!t || !at()) return;
      const r = getSelection().getRangeAt(0).getBoundingClientRect();
      tool = document.createElement('button');
      tool.type = 'button'; tool.id = 'rh-sel'; tool.className = 'quiet'; tool.dataset.t = t;
      tool.append('Learn beside ', Object.assign(document.createElement('kbd'), {textContent: '⌥B'}));
      tool.style.left = `${scrollX + Math.max(8, r.right - 150)}px`; tool.style.top = `${scrollY + r.bottom + 6}px`;
      document.body.append(tool);
    });
  });

  document.addEventListener('click', e => {
    const x = e.target.closest && e.target.closest('.rh-ask, #rh-sel, .rh-way, .rh-shut');
    if (!x) return;
    if (x.matches('.rh-way')) choose(x);
    else if (x.matches('.rh-shut')) shut();
    else offer(x.dataset.t);
  });
  // Before core.js and pane.js (capture), so Esc closes the offer first, and a number in the offer does not reach the page.
  document.addEventListener('keydown', e => {
    const t = e.target, inBox = t.matches && t.matches('textarea, input, select, [contenteditable]');
    if (e.altKey && !e.metaKey && !e.ctrlKey && e.code === 'KeyB') {
      const term = picked() || document.querySelector('#check .rh-gap')?.dataset.t || document.querySelector('.rh-needs .rh-ask')?.dataset.t;
      if (offer(term)) { e.preventDefault(); e.stopPropagation(); }
      return;
    }
    if (!isOpen() || inBox || e.altKey || e.metaKey || e.ctrlKey) return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); shut(); return; }
    const w = /^[1-3]$/.test(e.key) && box().querySelectorAll('.rh-way')[+e.key - 1];
    if (w && !w.disabled) { e.preventDefault(); choose(w); }
  }, true);

  // The way back. The side walks that the pane showed come from its `rh:at` messages, only from this origin and the pane's frame.
  const seen = new Set();
  const note = u => { const m = /^\/w\/([^/?#]+)\/\d+/.exec(u || ''); if (m) seen.add(decodeURIComponent(m[1])); };
  addEventListener('message', e => {
    const f = document.querySelector('#rh-pane iframe');
    if (inPane() || !f || e.origin !== location.origin || e.source !== f.contentWindow) return;
    if (e.data && e.data.type === 'rh:at') note(e.data.url);
  });
  // The end of a side walk closes the pane. Its detail comes from the pane page, so it is not used: the server has its own record.
  document.addEventListener('abhyasa:rh-done', () => window.abhyasaPane?.close());
  const back = async () => {
    const ids = [...seen].reverse(); seen.clear();   // the deepest side walk first, then the one that opened it
    let html = null;
    for (const sid of ids) {
      try {
        const r = await fetch(`/rh/back/${encodeURIComponent(sid)}`, {method: 'POST'});
        if (r.ok && new URL(r.url).pathname === location.pathname) html = await r.text();
      } catch {}
    }
    const fresh = html && new DOMParser().parseFromString(html, 'text/html').querySelector('.rh-needs'), old = document.querySelector('.rh-needs');
    if (fresh && old) { old.replaceWith(fresh); htmx.process(fresh); }
  };
  let was = root.classList.contains('rh-open');
  if (was) note(new URLSearchParams(location.search).get('rh'));
  new MutationObserver(() => { const now = root.classList.contains('rh-open'); if (was && !now) back(); was = now; })
    .observe(root, {attributes: true, attributeFilter: ['class']});

  // In the pane, the end of a side walk tells the page that opened it.
  const done = () => {
    const d = document.querySelector('[data-rh-done]');
    if (!d || !inPane()) return;
    try { const v = JSON.parse(d.dataset.rhDone); parent.postMessage({type: 'rh:done', slug: v.slug, outcome: v.outcome}, location.origin); } catch {}
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', done); else done();
  document.addEventListener('htmx:afterSettle', e => { if (e.detail.target === document.body) done(); });   // Next idea swaps the page in place
}
