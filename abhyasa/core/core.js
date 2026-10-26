// Markdown and maths for `.md` elements, and the left-hand keys: ⌥ + a letter clicks the element a block names.
// Vault text is not trusted: a saved web page can hold an <iframe> or a <video autoplay>. Raw HTML in markdown shows as
// text, and a pass after the render removes media, scripts, event attributes and javascript: links that got through.
const abhyasaEsc = t => String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
if (window.marked) marked.use({renderer: {html: tok => abhyasaEsc(typeof tok === 'string' ? tok : tok.raw || tok.text || '')}});
function abhyasaClean(el) {
  el.querySelectorAll('iframe, frame, video, audio, object, embed, script, style, link, meta, base, form').forEach(n => n.remove());
  el.querySelectorAll('*').forEach(n => [...n.attributes].forEach(a => {
    const v = a.value.trim().toLowerCase();
    if (a.name.startsWith('on') || a.name === 'srcdoc' || a.name === 'autoplay' || /^(javascript|vbscript|data:text\/html)/.test(v)) n.removeAttribute(a.name);
  }));
}
function render(root) {
  (root || document).querySelectorAll('.md:not([data-done])').forEach(el => {
    if (window.marked) { el.innerHTML = marked.parse(el.textContent); abhyasaClean(el); }
    el.dataset.done = 1;
    if (window.renderMathInElement) renderMathInElement(el, {delimiters: [{left: '$$', right: '$$', display: true}, {left: '$', right: '$', display: false}]});
  });
}
window.addEventListener('load', () => render());
document.addEventListener('htmx:afterSwap', e => render(e.target));
document.addEventListener('htmx:oobAfterSwap', e => render(e.target));

// A block adds keys with `abhyasaKeys.KeyX = '#selector'`. ⌥S presses the main button of any page.
window.abhyasaKeys = window.abhyasaKeys || {KeyS: '#send, main .go'};
document.addEventListener('keydown', e => {
  if (!e.altKey) return;
  const sel = abhyasaKeys[e.code], el = sel && document.querySelector(sel);
  if (el && !el.disabled) { e.preventDefault(); el.click(); }
});
// ⌘↵ in a form box sends the form with its main button; "/" goes to the search box from anywhere that is not a box.
document.addEventListener('keydown', e => {
  const t = e.target, inBox = t.matches && t.matches('textarea, input, select, [contenteditable]');
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && inBox && t.form && t.form.id !== 'composer') {
    e.preventDefault(); t.form.requestSubmit(t.form.querySelector('button.go') || undefined);
  } else if (e.key === '/' && !inBox && !e.metaKey && !e.ctrlKey && !e.altKey) {
    const q = document.querySelector('nav input[type=search]');
    if (q) { e.preventDefault(); q.focus(); q.select(); }
  }
});

// Text boxes grow with their text (CSS `field-sizing`, or this for a browser without it), up to a limit; then they scroll inside.
// A program that changes a box sends `input` (the voice block does), so the box grows then too. The caret stays in view.
const abhyasaGrow = !CSS.supports('field-sizing', 'content');
document.addEventListener('input', e => {
  const t = e.target;
  if (!(t instanceof HTMLTextAreaElement)) return;
  if (abhyasaGrow) { t.style.height = 'auto'; t.style.height = Math.min(t.scrollHeight + 2, innerHeight * .5) + 'px'; }
  if (t.selectionEnd === t.value.length) {
    t.scrollTop = t.scrollHeight;
    const r = t.getBoundingClientRect();
    if (!t.closest('#composer') && r.bottom > innerHeight - 20) window.scrollBy({top: r.bottom - innerHeight + 40});
  }
});

function abhyasaMotion() { return !matchMedia('(prefers-reduced-motion: reduce)').matches; }

// Every page link and the search box load in place (hx-boost on <body>); a fresh fetch on Back, so a page is never stale.
if (window.htmx) { htmx.config.historyCacheSize = 0; htmx.config.refreshOnHistoryMiss = false; }

// A thin bar at the top for each request, as nprogress does. It creeps toward 90 % and fills when the last request ends.
const abhyasaBar = (() => {
  const el = document.createElement('div');
  el.id = 'pbar'; el.setAttribute('aria-hidden', 'true');
  let n = 0, w = 0, tick = null, hide = null;
  const set = v => { w = v; el.style.transform = `scaleX(${v})`; };
  return {
    start() {
      if (!el.isConnected) document.documentElement.appendChild(el);   // not in <body>: a boosted page replaces the body
      if (n++) return;
      clearTimeout(hide); el.classList.add('on'); set(.08);
      tick = setInterval(() => set(w + (.9 - w) * .06), 250);
    },
    done() {
      if (!n || --n) return;
      clearInterval(tick); set(1);
      hide = setTimeout(() => { el.classList.remove('on'); setTimeout(() => n || set(0), 300); }, 180);
    },
  };
})();
window.addEventListener('beforeunload', () => abhyasaBar.start());        // a full page load (for example the graph's subject menu)
window.addEventListener('pageshow', e => { if (e.persisted) abhyasaBar.done(); });

// Pending states. The button you press says what the app does (its `data-wait`) and counts the seconds; it stays off until
// the reply comes. A `data-skel` names where a placeholder goes while you wait. A request under `data-quiet` shows nothing.
// Each request is timed into `abhyasaTimes` and the console, so you can see where the time goes.
window.abhyasaTimes = window.abhyasaTimes || [];
const abhyasaReqs = new WeakMap();
const abhyasaSecs = st => { const s = Math.round((performance.now() - st.t0) / 1000); st.secs.forEach(x => x.textContent = s >= 1 ? `${s} s` : ''); };
const abhyasaSkel = (tag, text) => {
  const el = document.createElement(tag);
  el.className = 'pending';
  el.innerHTML = '<span class="lbl"><span class="what"></span> <span class="secs"></span></span><div class="skel"><i></i><i></i><i class="short"></i></div>';
  el.querySelector('.what').textContent = text;
  return el;
};

document.addEventListener('htmx:beforeRequest', e => {
  const elt = e.detail.elt, xhr = e.detail.xhr, cfg = e.detail.requestConfig || {};
  const st = {t0: performance.now(), verb: (cfg.verb || 'get').toUpperCase(), path: cfg.path || '', quiet: !!elt.closest('[data-quiet]'), secs: [], off: []};
  abhyasaReqs.set(xhr, st);
  if (st.quiet) return;
  abhyasaBar.start();
  document.querySelectorAll('.req-err').forEach(x => x.remove());
  const ev = cfg.triggeringEvent, sub = ev && ev.submitter;
  const btn = elt.matches('button') ? elt : sub || (elt.tagName === 'FORM' ? elt.querySelector('button:not([type=button])') : null);
  const wait = (btn && btn.dataset.wait) || elt.dataset.wait, skel = (btn && btn.dataset.skel) || elt.dataset.skel;
  st.btn = btn;
  if (btn && wait) {
    st.html = btn.innerHTML;
    btn.innerHTML = '';
    btn.append(wait + ' ');
    const s = document.createElement('span'); s.className = 'secs'; btn.append(s); st.secs.push(s);
    btn.classList.add('busy');
  }
  // the pressed button, and its siblings for a choice, go off so a second press cannot send twice
  st.off = btn ? (btn.classList.contains('opt') ? [...document.querySelectorAll('.opt')] : [btn]) : [];
  st.off.forEach(b => b.disabled = true);
  const into = skel && document.querySelector(skel);
  if (into && wait) {
    st.skel = abhyasaSkel(/^(OL|UL)$/.test(into.tagName) ? 'li' : 'div', wait);
    into.appendChild(st.skel);
    st.secs.push(st.skel.querySelector('.secs'));
  }
  const own = elt.querySelector(':scope > .skeleton .lbl');   // a placeholder that loads itself
  if (own) { const s = document.createElement('span'); s.className = 'secs'; own.append(' ', s); st.secs.push(s); }
  if (st.secs.length) st.tick = setInterval(() => abhyasaSecs(st), 1000);
});

document.addEventListener('htmx:beforeSwap', e => {
  const st = abhyasaReqs.get(e.detail.xhr);
  if (st && st.skel) st.skel.remove();   // before the swap, so the new content takes the place of the placeholder with no jump
});

document.addEventListener('htmx:afterRequest', e => {
  const st = abhyasaReqs.get(e.detail.xhr);
  if (!st) return;
  st.t1 = performance.now();
  clearInterval(st.tick);
  if (st.skel) st.skel.remove();
  st.off.forEach(b => { if (b.isConnected) b.disabled = false; });
  if (st.btn && st.html !== undefined && st.btn.isConnected) { st.btn.innerHTML = st.html; st.btn.classList.remove('busy'); }
  const status = e.detail.xhr.status;
  if (!st.quiet) {
    abhyasaBar.done();
    if (!e.detail.successful) {
      const p = document.createElement('p');
      p.className = 'req-err';
      p.textContent = status ? `The request failed (error ${status}). Try again.` : 'The app does not answer. Make sure that it runs, then try again.';
      const at = (st.btn && st.btn.isConnected && st.btn.closest('.row')) || e.detail.elt;
      if (at && at.isConnected) at.after(p);
    }
  }
  const t = {verb: st.verb, path: st.path, status, wait_ms: Math.round(st.t1 - st.t0), at: new Date().toISOString().slice(11, 19)};
  abhyasaTimes.push(t);
  st.t = t;
  if (!st.quiet) console.info(`[abhyasa] ${t.verb} ${t.path} ${status} ${(t.wait_ms / 1000).toFixed(2)} s`);
});

document.addEventListener('htmx:afterSettle', e => {
  const st = abhyasaReqs.get(e.detail.xhr);
  if (!st || !st.t || st.t.settle_ms !== undefined) return;
  st.t.settle_ms = Math.round(performance.now() - st.t1);
  if (!st.quiet) console.info(`[abhyasa]   swap and settle ${st.t.settle_ms} ms`);
});

window.addEventListener('load', () => {
  const n = performance.getEntriesByType('navigation')[0];
  if (n) console.info(`[abhyasa] page ${location.pathname}: first byte ${Math.round(n.responseStart)} ms, ready ${Math.round(n.domContentLoadedEventEnd)} ms`);
});

// The search box keeps the words of the search on the results page.
const abhyasaQ = () => {
  const q = new URLSearchParams(location.search).get('q'), box = document.querySelector('nav input[type=search]');
  if (box && q && location.pathname === '/search') box.value = q;
};
window.addEventListener('load', abhyasaQ);
document.addEventListener('htmx:afterSettle', abhyasaQ);
