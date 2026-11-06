// The builder. It is a page in the side pane; the walk or the talk is the page at the left.
// - When a change of the builder is done, the page at the left loads again (`abhyasa:built`); the pane stays open. A builder in another tab or
//   window tells the page of its walk or talk by a BroadcastChannel, and the hidden `#build-watch` mark of that page sees a change too.
// - Keys: ⌥E opens or closes the builder; in the builder ⌥X stops, ⌥W goes to the box, ⌥A opens or closes the brief, ⌘Z undoes,
//   and on a find of research F keeps and X drops. ⌥S sends (the main button) and ⌥D speaks, as on each page.
// - A question from a demo (`rk-ask` of rupaka: {demo, text, state, step}) becomes a message in the box, ready to send.
// - Start and Make a talk in the Start box open the builder with the job running.
(() => {
  if (window.abhyasaBuild) return;
  window.abhyasaBuild = true;
  const inPane = window.parent !== window;
  const col = () => document.getElementById('build-live');
  const seen = () => { const w = document.getElementById('build-watch'); return w ? +w.dataset.changes : null; };
  const chan = window.BroadcastChannel ? new BroadcastChannel('abhyasa-built') : null;
  const built = landed => document.dispatchEvent(new CustomEvent('abhyasa:built', {detail: {landed}}));
  let last = null, shown = null;   // the change count of the builder column, and the one that this page shows
  const toEnd = () => { const t = document.getElementById('build-log'); if (t) t.scrollTop = t.scrollHeight; };
  document.addEventListener('htmx:afterSettle', e => {
    const w = document.getElementById('build-watch');
    if (w && (e.target === w || e.target.contains?.(w))) {
      const n = +w.dataset.changes;
      if (shown !== null && n > shown) built((w.dataset.landed || '').split(',').filter(Boolean).map(Number));
      shown = Math.max(shown ?? n, n);
      return;
    }
    const live = col();
    if (!live || (e.target !== live && !live.contains(e.target))) return;
    toEnd();
    const n = +live.dataset.changes;
    const ns = (live.dataset.landed || '').split(',').filter(Boolean).map(Number);
    if (last !== null && n > last && inPane) { try { window.parent.document.dispatchEvent(new CustomEvent('abhyasa:built', {detail: {landed: ns}})); } catch (_) {} }
    else if (last !== null && n > last && chan && live.dataset.href) chan.postMessage({path: live.dataset.href, landed: ns});   // a builder in its own tab or window
    last = n;
  });
  if (chan) chan.onmessage = e => { if (e.data && e.data.path === location.pathname && !col()) built(e.data.landed || []); };
  const ready = () => { const l = col(); if (l) { last = +l.dataset.changes; toEnd(); } shown = seen(); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', ready); else ready();
  // The page at the left takes the change in place: its main part comes again from the server, and each row that the builder changed
  // gets `.landed` (a soft wash that fades). The side pane, the scroll and the focus stay. A page that cannot do this loads again.
  document.addEventListener('abhyasa:built', async e => {
    const main = document.querySelector('body > main');
    try {
      const r = await fetch(location.href, {headers: {'HX-Request': 'false'}});
      if (new URL(r.url).pathname !== location.pathname) { location.replace(r.url); return; }   // Build became the walk or the talk: its own page, with its own style
      const doc = new DOMParser().parseFromString(await r.text(), 'text/html'), fresh = doc.querySelector('body > main');
      if (!r.ok || !main || !fresh) throw new Error('no main');
      const y = scrollY;
      main.innerHTML = fresh.innerHTML; window.htmx && htmx.process(main); scrollTo(0, y);
      shown = seen() ?? shown;
      const ns = (e.detail && e.detail.landed) || [];
      const rows = [...main.querySelectorAll('.edit-list > li.edit-row')];
      for (const n of ns) { const row = rows.find(li => +li.dataset.i === n - 1); if (row) { row.classList.add('landed'); const b = row.getBoundingClientRect(); if (b.top < 0 || b.bottom > innerHeight) row.scrollIntoView({block: 'center'}); } }
    } catch (_) { location.reload(); }
  });
  // The change box of the walk page and Change this slide on the talk editor go to the builder, in the side pane, and are sent at once.
  const toBuilder = text => {
    const a = document.querySelector('a.build-beside');
    if (!a || !text.trim() || !window.abhyasaPane) return false;
    const u = new URL(a.getAttribute('href'), location.href); u.searchParams.set('say', text.trim()); u.searchParams.set('send', '1');
    return window.abhyasaPane.open(u.pathname + u.search, 'Builder');
  };
  document.addEventListener('submit', e => {
    const f = e.target;
    if (f.matches && f.matches('form.change-form')) {
      const t = f.querySelector('textarea')?.value || '';
      if (toBuilder(t)) { e.preventDefault(); e.stopImmediatePropagation(); f.reset(); }
    } else if (f.matches && f.matches('form.rewrite')) {
      const chip = e.submitter && e.submitter.name === 'chip' ? e.submitter.value : '', t = chip || f.querySelector('input[name=text]')?.value || '';
      const row = f.closest('li.edit-row'), n = row ? +row.dataset.i + 1 : '';
      if (toBuilder(n ? `Slide ${n}: ${t}` : t)) { e.preventDefault(); e.stopImmediatePropagation(); f.reset(); }
    }
  }, true);

  const press = sel => { const b = document.querySelector(sel); if (b && !b.disabled) { b.click(); return true; } return false; };
  document.addEventListener('keydown', e => {
    const box = e.target.closest && e.target.closest('input, textarea, select, [contenteditable]');
    if (e.altKey && !e.metaKey && !e.ctrlKey && e.code === 'KeyE' && !location.pathname.startsWith('/c/')) {
      if (col() && inPane) { e.preventDefault(); window.parent.postMessage({type: 'rh:close'}, location.origin); return; }
      if (window.abhyasaPane && window.abhyasaPane.isOpen() && document.querySelector('#rh-pane iframe[src*="/build/"]')) { e.preventDefault(); window.abhyasaPane.close(); return; }
      if (press('a.build-beside')) e.preventDefault();
      return;
    }
    if (!col()) return;
    if (e.altKey && !e.metaKey && !e.ctrlKey) {
      if (e.code === 'KeyX' && press('#build-live [data-act="stop-job"]')) e.preventDefault();
      else if (e.code === 'KeyW') { e.preventDefault(); document.getElementById('build-say')?.focus(); }
      else if (e.code === 'KeyA') { e.preventDefault(); const d = document.getElementById('bd-brief'); if (d) d.open = !d.open; }
      return;
    }
    if (box) {
      if (e.target.id === 'build-say' && e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); e.target.form.requestSubmit(); }
      return;
    }
    if (e.metaKey && !e.shiftKey && e.key === 'z') { if (press('#build-live [data-undo]')) e.preventDefault(); return; }
    const f = e.target.closest && e.target.closest('.bd-finds > li');
    if (f && !e.metaKey && !e.ctrlKey && !e.altKey && (e.key === 'f' || e.key === 'x')) { const k = f.querySelector(`[data-key="${e.key.toUpperCase()}"]`); if (k) { e.preventDefault(); k.click(); } }
  });
  // The examples of the first run: a press puts the words in the box and sends them.
  document.addEventListener('click', e => {
    const t = e.target.closest && e.target.closest('[data-try]');
    if (!t) return;
    const box = document.getElementById('build-say');
    if (box) { box.value = t.dataset.try; box.form.requestSubmit(); }
  });

  // rk-ask: a question about a demo, with its state, goes into the box.
  const stateOf = d => d.state && typeof d.state === 'object' ? Object.entries(d.state).map(([k, v]) => `${k} = ${v}`).join(', ') : '';
  window.abhyasaAsk = (d, slide) => {
    const st = stateOf(d), text = `About the demo${slide ? ` on slide ${slide}` : ''}${st ? ` (${st})` : ''}: ${d.text || ''}`.trim();
    let box = document.getElementById('build-say');
    if (!box) { try { box = document.querySelector('#rh-pane iframe')?.contentDocument?.getElementById('build-say'); } catch (_) {} }
    if (box) { box.value = text; box.focus(); return text; }
    const a = document.querySelector('a.build-beside');
    if (a) { const u = new URL(a.href, location.href); u.searchParams.set('say', text); a.href = u.pathname + u.search; if (a.dataset.pane) a.dataset.pane = u.pathname + u.search + '&pane=1'; a.click(); }
    return text;
  };
  document.addEventListener('rk-ask', e => {
    e.preventDefault();   // a tutor listens here: the demo does not say that none is on the page
    const d = e.detail || {}, s = e.target && e.target.closest ? e.target.closest('[data-slide]') : null;
    window.abhyasaAsk(d, s ? s.dataset.slide : (d.slide || ''));
  });

  // Start and Make a talk in the Start box open the builder: the text is the first message and the chips are main sources.
  // A box that the builder cannot take (such as a dropped PDF) goes on as before.
  document.addEventListener('click', async e => {
    const b = e.target.closest && e.target.closest('#start-go, #start-talk');
    if (!b || b.disabled || b.dataset.plain) return;
    const form = document.getElementById('start-form');
    if (!form || document.getElementById('start-file')?.value) return;
    e.preventDefault(); e.stopImmediatePropagation();
    const fd = new FormData(form);
    if (b.id === 'start-talk') fd.set('talk', '1');
    try {
      const r = await fetch('/build/start', {method: 'POST', body: fd});
      const j = r.ok ? await r.json() : null;
      if (j && j.url) { location.href = j.url; return; }
    } catch (_) {}
    b.dataset.plain = '1'; b.click(); delete b.dataset.plain;
  }, true);
})();
