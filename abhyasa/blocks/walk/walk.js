// The walk keys, for the left hand: ⌥S presses the main button (core.js): Send (or Run the tests) while a check is open, then Next idea.
// ⌥W asks for a hint, and ⌘↵ sends the answer. Skip this idea is a quiet link with no key.
abhyasaKeys.KeyW = '#hint';
abhyasaKeys.KeyV = '.walk-demo #keep';   // ⌥V keeps the state of a demo

if (!window.abhyasaWalk) {
  window.abhyasaWalk = true;
  // Over 1040 px the outline is always open and its summary is only a label, so the keys skip it. The outline is swapped by htmx, so this runs again after each swap.
  const wide = matchMedia('(min-width: 1041px)'), railTab = () => document.querySelectorAll('#rail summary').forEach(x => wide.matches ? x.setAttribute('tabindex', '-1') : x.removeAttribute('tabindex'));
  wide.addEventListener('change', railTab); document.addEventListener('htmx:afterSettle', railTab); railTab();
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

  const root = document.documentElement;

  // Open in Leela opens a new tab. This tab then loads the check card again, so the card shows "Opened in Leela at …".
  document.addEventListener('submit', e => {
    const f = e.target.closest && e.target.closest('form.leela-go');
    if (f && f.dataset.check) setTimeout(() => htmx.ajax('GET', f.dataset.check, {target: '#check', swap: 'innerHTML'}), 800);
  });

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
  document.addEventListener('htmx:afterSettle', e => { if (e.detail.target && e.detail.target.id === 'check') held(); });

  // In the side pane, "Back to the paper" closes one level of the pane, as ⌥Z does, and does not load the paper in the pane.
  document.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('a.walk-back');
    if (!a || !root.classList.contains('in-pane') || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault(); parent.postMessage({type: 'rh:close', level: 1}, location.origin);
  });

  // A demo or an order check: each prediction goes to the walk, which logs it with the step.
  const say = (card, text) => { const s = card.querySelector('.said'); if (s) s.textContent = text; };
  const post = (card, url, body, done) => fetch(url, {method: 'POST', body: new URLSearchParams(body)})
    .then(r => { say(card, r.ok ? done : 'The tutor did not save this. Try again.'); return r.ok && r.json(); }).catch(() => say(card, 'The tutor did not save this. Try again.'));
  // The first prediction closes the step: its dot in the outline fills and the progress line moves, as after an answer (walk.css `.just`).
  const fill = (card, r) => {
    const li = r.dot && document.getElementById('rail-' + card.dataset.step), bar = document.getElementById('rail-bar');
    if (li && !li.classList.contains(r.dot)) { li.classList.remove('now', 'todo'); li.classList.add(r.dot, 'just'); }
    if (bar && r.total) bar.style.width = `${Math.floor(100 * r.done / r.total)}%`;
  };
  // The first prediction closes a demo check: Next idea shows in the card and becomes the main button, and the skip goes.
  const shut = card => {
    const go = card.querySelector('.go-on');
    if (!go || !go.hidden) return;
    go.hidden = false; card.classList.add('shut');
  };
  // After a wrong prediction, the help under the card loads into its slot: a lesson in another way, then a simpler demo (`ladder`).
  const help = url => { if (url && window.htmx && document.getElementById('ladder')) htmx.ajax('GET', url, {target: '#ladder', swap: 'outerHTML'}); };
  document.addEventListener('rk-predict', e => {
    const card = e.target.closest && e.target.closest('.walk-demo');
    if (!card) return;
    const host = e.target.closest('[data-demo]') || card;   // the simpler demo in the help has its own slug
    // The gate waits until the walk saves the prediction. A failed save opens the gate again, with the pick and the why kept.
    e.preventDefault();
    const d = e.detail, no = 'The tutor did not save this. Try again.';
    fetch(card.dataset.url, {method: 'POST', body: new URLSearchParams({slug: host.dataset.demo, gate: d.gate, picked: String(d.picked), ans: String(d.ans),
                                                                        ok: String(d.ok), why: d.why || '', context: d.context || ''})})
      .then(r => { d.settle(r.ok, no); return r.ok && r.json(); })
      .then(r => { if (r) { say(card, 'Your prediction is saved.'); shut(card); fill(card, r); help(r.ladder); } })
      .catch(() => d.settle(false, no));
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

  // Words in the passage point at the demo, as in an explorable explanation. The words that the idea moves (`data-moves`) and the
  // labels of the demo get a dotted line when a part of the demo has the same name. Point at a word, and that part gets a soft
  // ring; point at the part, and its words light up. With no match, the passage stays as it is.
  const norm = t => String(t || '').toLowerCase().replace(/\(.*?\)/g, ' ').replace(/\s+/g, ' ').trim();
  const esc = t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const tree = bs => (bs || []).flatMap(b => [b, ...tree(b.blocks)]);   // the blocks in the order that rupaka draws them
  const link = () => {
    const p = document.getElementById('passage'), host = document.querySelector('#check .walk-demo [data-rupaka]');
    if (!p || !host || host.dataset.rkReady !== '1' || p.dataset.linked) return;
    let spec; try { spec = host.rupaka?.spec || JSON.parse(host.querySelector('script').textContent); } catch { return; }
    const nodes = [...host.querySelectorAll('.rk-b')], bs = tree(spec.blocks);
    if (nodes.length !== bs.length) return;
    let moves = []; try { moves = JSON.parse(p.dataset.moves || '[]'); } catch {}
    const names = k => [bs[k].label, bs[k].bind].map(norm).filter(x => x.length > 2);
    const parts = w => nodes.filter((n, k) => names(k).some(x => x === w || x.includes(w) || w.includes(x)));
    const words = new Map([...new Set([...moves, ...bs.map(b => b.label)].map(norm))].filter(w => w.length > 2).map(w => [w, parts(w)]).filter(([, ns]) => ns.length));
    const text = p.querySelector('.md') || p;
    if (!words.size || !text) return;
    const re = new RegExp(`\\b(${[...words.keys()].sort((a, b) => b.length - a.length).map(esc).join('|')})\\b`, 'gi');
    const walker = document.createTreeWalker(text, NodeFilter.SHOW_TEXT), ts = [];
    while (walker.nextNode()) ts.push(walker.currentNode);
    for (const t of ts) {
      if (t.parentElement.closest('.mv, .math, code')) continue;
      const s = t.textContent, f = document.createDocumentFragment();
      let at = 0;
      for (const m of s.matchAll(re)) {
        const sp = Object.assign(document.createElement('span'), {className: 'mv', textContent: m[0], tabIndex: 0});
        sp.dataset.mv = norm(m[0]);
        f.append(s.slice(at, m.index), sp); at = m.index + m[0].length;
      }
      if (at) { f.append(s.slice(at)); t.replaceWith(f); }
    }
    p.dataset.linked = '1';
    const ring = (w, on) => (words.get(w) || []).forEach(n => n.classList.toggle('mv-hot', on));
    const lit = (n, on) => p.querySelectorAll('.mv').forEach(sp => { if ((words.get(sp.dataset.mv) || []).includes(n)) sp.classList.toggle('hot', on); });
    for (const ev of ['pointerover', 'focusin']) p.addEventListener(ev, e => { const sp = e.target.closest('.mv'); if (sp) ring(sp.dataset.mv, true); });
    for (const ev of ['pointerout', 'focusout']) p.addEventListener(ev, e => { const sp = e.target.closest('.mv'); if (sp) ring(sp.dataset.mv, false); });
    for (const n of new Set([...words.values()].flat())) {
      n.addEventListener('pointerenter', () => lit(n, true)); n.addEventListener('pointerleave', () => lit(n, false));
    }
  };
  // rupaka draws the demo after the card comes; link when it is ready.
  new MutationObserver(link).observe(document.documentElement, {subtree: true, attributes: true, attributeFilter: ['data-rk-ready']});
  document.addEventListener('htmx:afterSettle', link);

}

// The walk path editor. The keys, the drag, the live fields and ⌘Z are in core/edit.js ("Walk path" in core/keys.py). Here: Add an idea goes after
// the idea that had the focus last, W or S with the focus on no row goes into the list, R opens the row and puts the focus in the rewrite box,
// Add an idea puts the focus in its first box, and a change that the walk cannot take shows its reason under the row (as text).
if (!window.abhyasaWalkEdit) {
  window.abhyasaWalkEdit = true;
  const rowOf = el => el?.closest?.('#steps > li.edit-row');
  let last = null;   // the slug of the idea that had the focus last
  document.addEventListener('focusin', e => { const li = rowOf(e.target); if (li) last = li.dataset.id; });
  document.addEventListener('htmx:configRequest', e => {
    const el = e.detail.elt;
    if (!el?.closest?.('#steps')) return;
    if (el.dataset?.after) { e.detail.parameters.after = last || ''; return; }
    const li = rowOf(el);   // a change in a row puts the focus back on that row; a removed row gives it to the row after it
    if (li && el !== li && !el.dataset?.live && el.getAttribute('hx-swap') !== 'none') {
      const next = li.nextElementSibling?.matches('li.edit-row') ? li.nextElementSibling : li.previousElementSibling;
      el._focus = {list: 'steps', id: e.detail.parameters.act === 'remove' ? next?.dataset?.id || '' : li.dataset.id};
    }
  });
  document.addEventListener('keydown', e => {
    const a = document.activeElement, all = document.querySelectorAll('#steps > li.edit-row');
    if (e.defaultPrevented || e.altKey || e.metaKey || e.ctrlKey || e.shiftKey || (a && a !== document.body) || !all.length) return;
    if (e.code !== 'KeyW' && e.code !== 'KeyS') return;
    e.preventDefault(); all[e.code === 'KeyS' ? 0 : all.length - 1].focus();
  });
  document.addEventListener('click', e => {
    const b = e.target.closest?.('#steps [data-rewrite]'), li = rowOf(b);
    if (!li) return;
    const d = li.querySelector(':scope > details');
    if (d) d.open = true;
    li.querySelector('form.rewrite input[name=text]')?.focus();
  });
  document.addEventListener('toggle', e => {
    if (e.target.id === 'add-idea' && e.target.open) e.target.querySelector('input, select')?.focus();
  }, true);
  document.addEventListener('htmx:afterRequest', e => {
    const elt = e.detail.elt, xhr = e.detail.xhr;
    if (!elt.closest || !elt.closest('#steps')) return;
    if (xhr.status !== 400) { if (xhr.status < 300) rowOf(elt)?.querySelectorAll('.req-err').forEach(x => x.remove()); return; }
    document.querySelectorAll('#steps .req-err').forEach(x => x.remove());
    const p = Object.assign(document.createElement('p'), {className: 'req-err', role: 'alert', textContent: xhr.responseText || 'The walk cannot take this change.'});
    (rowOf(elt)?.querySelector('.fields') || elt.closest('.add-idea') || elt).append(p);
  });
  // Improve the walk: a chip puts its words in the box, after what you wrote, and the cursor goes to the end.
  document.addEventListener('click', e => {
    const c = e.target.closest && e.target.closest('#improve [data-fill]');
    if (!c) return;
    const t = c.closest('form').querySelector('textarea');
    t.value = (t.value.trim() ? t.value.trim() + ' ' : '') + c.dataset.fill;
    t.focus(); t.setSelectionRange(t.value.length, t.value.length);
  });
  // A link from a step ("Pick a passage yourself") opens the editor at the passage picker of that idea.
  const toPick = () => { const d = location.hash.startsWith('#pick-') && document.getElementById(location.hash.slice(1)); if (d) { d.open = true; d.scrollIntoView({block: 'center'}); d.querySelector('input')?.focus(); } };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', toPick); else toPick();
}
