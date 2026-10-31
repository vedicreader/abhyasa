// The Keys panel (keys/ui.py `Float`): a quiet pill at the bottom left of each page. A click, or ⌥⇧F, opens a small panel with the
// most useful keys of the page, and each row does what its key does. Esc closes it. It opens by itself one time, for a new learner, and
// then it remembers open or closed. It never takes the focus on load. It steps out of the way of the guide box, the board strip, the
// composer and the Send button of a check: it moves to the top, or it hides while it would cover one of them.
if (!window.abhyasaKF) {
  const STORE = 'abhyasa-keys-float';
  const AVOID = '#send, #guide-form, #guide-strip, #composer, .mic-float.on, .mic-float.busy';
  const BOX = 'textarea, input[type=text], input[type=search], input:not([type])';
  const $ = id => document.getElementById(id);
  const seen = el => el && !el.disabled && (el.checkVisibility ? el.checkVisibility() : el.offsetParent !== null);
  let lastBox = null;

  const isOpen = () => $('kf-panel') && !$('kf-panel').hidden;
  function show(open, keep) {
    const p = $('kf-panel'), b = $('kf-pill');
    if (!p) return;
    p.hidden = !open; b.setAttribute('aria-expanded', String(open));
    if (keep) localStorage.setItem(STORE, open ? 'open' : 'closed');
    if (open) mark();
    place();
  }

  // A row with no part to act on in this page now (no hint button on a closed check) is off.
  function mark() {
    document.querySelectorAll('#kf .kf-do').forEach(b => {
      const d = b.dataset, sel = d.code && window.abhyasaKeys ? abhyasaKeys[d.code] : undefined;
      let ok = true;
      if (d.act === 'explain') ok = !!($('guide-go') || window.abhyasaGuide);
      else if (d.act === 'dictate') ok = !!$('mic-float');
      else if (d.on) ok = !!document.querySelector(d.on);
      else if (d.alt && sel !== undefined && window.abhyasaFind) ok = !!(abhyasaFind(sel) || (d.code === 'KeyC' && $('continue')));
      b.disabled = !ok;
    });
  }

  const key = (el, code, alt) => el.dispatchEvent(new KeyboardEvent('keydown', {code, key: alt ? '' : code.slice(3).toLowerCase(), altKey: !!alt, bubbles: true, cancelable: true}));
  function act(b) {
    const d = b.dataset;
    show(false, false);   // the panel goes for now, so the focus can go where the key sends it
    if (d.act === 'explain') { const g = $('guide-go'); if (g) g.click(); else if (window.abhyasaGuide) abhyasaGuide.open(); }
    else if (d.act === 'search') {
      const q = document.querySelector('nav input[type=search]');
      if (seen(q)) { q.focus(); q.select(); } else location.assign('/search');
    } else if (d.act === 'dictate') {
      const box = lastBox && lastBox.isConnected && seen(lastBox) ? lastBox : [...document.querySelectorAll(`main :is(${BOX}), #composer textarea`)].find(seen);
      if (box) box.focus();
      key(box || document.body, 'KeyD', true);
    } else if (d.code) {
      const on = d.on ? document.querySelector(d.on) : document.body;
      if (!on) return;
      if (d.on) on.focus({preventScroll: true});
      key(on, d.code, d.alt);
    }
  }

  // Out of the way: the pill hides while it covers a part that it must not cover. The open panel goes to the top left, else it hides too.
  const hit = (r, others) => others.some(o => r.left < o.right && r.right > o.left && r.top < o.bottom && r.bottom > o.top);
  function place() {
    const kf = $('kf'), p = $('kf-panel');
    if (!kf) return;
    const others = [...document.querySelectorAll(AVOID)].filter(seen).map(e => e.getBoundingClientRect()).filter(r => r.width && r.height);
    kf.classList.remove('kf-top'); p.classList.remove('kf-away');
    kf.classList.toggle('kf-away', hit($('kf-pill').getBoundingClientRect(), others));
    if (p.hidden) return;
    if (!hit(p.getBoundingClientRect(), others)) return;
    kf.classList.add('kf-top');
    if (hit(p.getBoundingClientRect(), others)) p.classList.add('kf-away');
  }

  function init() {
    const kf = $('kf');
    if (!kf || kf.dataset.ready) return;
    kf.dataset.ready = '1';
    if (document.documentElement.classList.contains('in-pane')) { kf.remove(); return; }
    if (/\bAbhyasa\//.test(navigator.userAgent)) $('kf-mac').hidden = false;   // Abhyasa.app names itself in the user agent (WebController.swift)
    const s = localStorage.getItem(STORE);
    if (s === null) localStorage.setItem(STORE, 'closed');   // open one time for a new learner, then closed until you open it
    show(s === null || s === 'open', false);
  }
  window.abhyasaKF = {init, show, place};

  document.addEventListener('click', e => {
    const t = e.target.closest && e.target.closest('#kf button, #kf a');
    if (!t) return;
    if (t.id === 'kf-pill') show(!isOpen(), true);
    else if (t.id === 'kf-close') { show(false, true); $('kf-pill').focus(); }
    else if (t.id === 'kf-hide') {
      fetch(t.dataset.url, {method: 'POST', body: new URLSearchParams({on: '0'})}).finally(() => $('kf') && $('kf').remove());
    } else if (t.classList.contains('kf-do')) act(t);
  });
  addEventListener('keydown', e => {
    if (e.code === 'KeyF' && e.altKey && e.shiftKey && !e.metaKey && !e.ctrlKey && $('kf')) {   // before core.js, which opens the keys page on ⌥F
      e.preventDefault(); e.stopImmediatePropagation();
      const open = !isOpen();
      show(open, true);
      if (open) { const b = [...document.querySelectorAll('#kf .kf-do')].find(x => !x.disabled); if (b) b.focus(); }
    } else if (e.key === 'Escape' && isOpen() && !$('kf-panel').classList.contains('kf-away')) {
      const inBox = e.target.matches && e.target.matches('textarea, input, select, [contenteditable]') && !$('kf').contains(e.target);
      if (inBox) return;   // the first Esc in a box only leaves the box (core.js)
      e.preventDefault(); e.stopImmediatePropagation();
      const inside = $('kf').contains(document.activeElement);
      show(false, true);
      if (inside) $('kf-pill').focus();
    }
  }, true);
  document.addEventListener('focusin', e => { if (e.target.matches && e.target.matches(BOX) && !e.target.closest('#kf, nav')) lastBox = e.target; });
  let queued = false;
  const later = () => { if (!queued) { queued = true; requestAnimationFrame(() => { queued = false; place(); }); } };
  addEventListener('scroll', later, {passive: true});
  addEventListener('resize', later);
  document.addEventListener('htmx:afterSettle', () => { init(); mark(); later(); });
  setInterval(() => { if ($('kf')) place(); }, 400);   // the guide box and the board strip come and go with no scroll
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => abhyasaKF.init()); else abhyasaKF.init();
