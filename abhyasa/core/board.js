// The board of the screen guide: hand-drawn marks over the page, one step at a time, with one spoken line for each step.
// The server checked each mark (abhyasa.guide.check_line). Each mark is kept as its anchor plus an offset, and is drawn again
// when the page scrolls or changes size, so it stays on its thing. Text from the model goes in with textContent only.
// Rough.js and perfect-freehand (core/vendor, MIT) load on the first board.
(() => {
  if (window.abhyasaBoard) return;
  const NS = 'http://www.w3.org/2000/svg', INK = 'var(--board-ink, #b5551c)', WAIT = 1200;
  let pf = null, st = null;   // the pen module, and the board that shows now
  const libs = async () => {
    if (!window.rough) await new Promise((ok, no) => document.head.append(Object.assign(document.createElement('script'), {src: '/vendor/rough.js', onload: ok, onerror: no})));
    if (!pf) pf = await import('/vendor/perfect-freehand.mjs');
  };
  const normTex = s => { s = String(s || '').replace(/\s+/g, ''); for (let t; (t = s.replace(/\{(\\[A-Za-z]+|[^{}\\])\}/g, '$1')) !== s;) s = t; return s; };
  const flat = s => String(s || '').replace(/\s+/g, ' ').trim().toLowerCase();
  const seen = el => el && el.isConnected && (el.checkVisibility ? el.checkVisibility() : el.offsetParent !== null);
  const pageRect = r => ({x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height});
  const anchorEl = id => document.querySelector(`[data-guide-id="${CSS.escape(id)}"]`);

  // The box of a run of words inside `el`, from its text nodes (not the hidden MathML of a formula).
  function textBox(el, words) {
    const nodes = [], tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {acceptNode: n => n.parentElement.closest('.katex-mathml, script, style') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT});
    let all = '';
    for (let n; (n = tw.nextNode());) { nodes.push([n, all.length]); all += n.data; }
    const low = all.toLowerCase(), want = flat(words);
    let at = -1, len = 0;
    // match with white space made single: build a regex from the words
    const re = new RegExp(want.split(' ').map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('\\s+'));
    const m = re.exec(low);
    if (!m) return null;
    at = m.index; len = m[0].length;
    const where = k => { let i = nodes.length - 1; while (i > 0 && nodes[i][1] > k) i--; return [nodes[i][0], k - nodes[i][1]]; };
    const r = document.createRange(), [a, ao] = where(at), [b, bo] = where(at + len);
    r.setStart(a, ao); r.setEnd(b, Math.min(bo, b.data.length));
    const rs = [...r.getClientRects()];
    if (!rs.length) return null;
    const f = rs[0];   // the first line only, so a mark on words that wrap stays on one line
    return pageRect(f);
  }

  // The box of an anchor in page pixels, or null when it is not on the page now.
  function boxOf(at) {
    const a = typeof at === 'string' ? {a: at} : at || {}, el = anchorEl(a.a);
    if (!seen(el)) return null;
    const R = pageRect(el.getBoundingClientRect());
    if (a.tex != null) {
      const parts = JSON.parse(el.dataset.parts || '[]'), hit = parts.find(p => normTex(p[0]) === normTex(a.tex)), part = hit && document.getElementById(hit[1]);
      return seen(part) ? pageRect(part.getBoundingClientRect()) : null;
    }
    if (a.text != null) return textBox(el, a.text);
    const rel = b => ({x: R.x + R.w * b[0] / 1000, y: R.y + R.h * b[1] / 1000, w: R.w * (b[2] - b[0]) / 1000, h: R.h * (b[3] - b[1]) / 1000});
    if (a.label != null) { const b = (st && st.labels[a.a] || {})[a.label]; return b ? rel(b) : null; }
    if (a.box) return rel(a.box);
    if (a.pt) return {x: R.x + R.w * a.pt[0] / 1000, y: R.y + R.h * a.pt[1] / 1000, w: 0, h: 0, pt: true};
    return R;
  }

  // --- drawing ---------------------------------------------------------------------------------------------------------
  function host() {
    let h = document.getElementById('board-host');
    if (!h) {
      h = Object.assign(document.createElement('div'), {id: 'board-host'});
      h.setAttribute('aria-hidden', 'true');
      const svg = document.createElementNS(NS, 'svg'); svg.id = 'board-layer'; h.append(svg);
      document.body.append(h);
    }
    return h;   // the layer is 1 px with overflow shown, so it never makes the page larger
  }
  const opts = seed => ({stroke: getComputedStyle(document.documentElement).getPropertyValue('--board-ink').trim() || '#b5551c', strokeWidth: 2.4, roughness: 1.2, bowing: 1, seed});

  // One mark's shapes for its boxes now. A label is an HTML element; the rest are SVG.
  function shapes(m) {
    const o = m.o, rc = rough.svg(host().querySelector('svg')), p = opts(m.seed), out = [];
    const b = o.at !== undefined ? boxOf(o.at) : null;
    if (o.at !== undefined && !b) return null;
    if (o.op === 'circle') out.push(rc.ellipse(b.x + b.w / 2, b.y + b.h / 2, b.w + 22, b.h + 16, p));
    if (o.op === 'box') out.push(rc.rectangle(b.x - 7, b.y - 5, b.w + 14, b.h + 10, p));
    if (o.op === 'underline') out.push(rc.line(b.x - 2, b.y + b.h + 4, b.x + b.w + 2, b.y + b.h + 2, p));
    if (o.op === 'point') {
      const cx = b.x + b.w / 2, cy = b.y + b.h / 2, sx = cx - 58, sy = cy - 46, ex = cx - (b.w / 2 + 6) * .8, ey = cy - (b.h / 2 + 6) * .8;
      out.push(rc.curve([[sx, sy], [(sx + ex) / 2 - 6, (sy + ey) / 2 + 8], [ex, ey]], p), ...head(rc, (sx + ex) / 2 - 6, (sy + ey) / 2 + 8, ex, ey, p));
      out.push(rc.circle(cx, cy, Math.max(10, Math.min(b.w, b.h) + 10), {...p, roughness: .6, strokeWidth: 1.6}));
    }
    if (o.op === 'arrow') {
      const f = boxOf(o.from), t = boxOf(o.to);
      if (!f || !t) return null;
      const fx = f.x + f.w / 2, fy = f.y + f.h / 2, tx = t.x + t.w / 2, ty = fy < t.y ? t.y - 4 : t.y + t.h + 4, mx = (fx + tx) / 2 + 30, my = (fy + ty) / 2;
      out.push(rc.curve([[fx, fy], [mx, my], [tx, ty]], p), ...head(rc, mx, my, tx, ty, p));
    }
    if (o.op === 'sketch' && pf) {
      const W = b.pt ? 240 : b.w, H = b.pt ? 90 : b.h;
      const pts = o.pts.map(([x, y]) => [b.x + W * x / 1000, b.y + H * y / 1000]);
      const outline = pf.getStroke(pts, {size: 5, thinning: .5, smoothing: .6, streamline: .5});
      const path = document.createElementNS(NS, 'path');
      path.setAttribute('d', outline.length ? 'M' + outline.map(q => q.map(v => v.toFixed(1)).join(' ')).join(' L') + ' Z' : '');
      path.setAttribute('fill', p.stroke); path.classList.add('fill');
      out.push(path);
      if (b.pt) out.push(rc.line(b.x, b.y - 6, b.x, b.y + H + 4, {...p, strokeWidth: 1.2, stroke: '#8c877c'}), rc.line(b.x - 4, b.y + H, b.x + W + 6, b.y + H, {...p, strokeWidth: 1.2, stroke: '#8c877c'}));
    }
    return out;
  }
  function head(rc, mx, my, tx, ty, p) {
    const a = Math.atan2(ty - my, tx - mx);
    return [-0.5, 0.5].map(d => rc.line(tx, ty, tx - 13 * Math.cos(a + d), ty - 13 * Math.sin(a + d), p));
  }
  function placeLabel(m) {
    const b = boxOf(m.o.at);
    if (!b) { m.el.hidden = true; return false; }
    m.el.hidden = false;
    const w = m.el.offsetWidth, h = m.el.offsetHeight, side = m.o.side || 'above', gap = 10;
    let x = b.x + b.w / 2 - w / 2, y = b.y - h - gap;
    if (side === 'below') y = b.y + b.h + gap;
    if (side === 'left') { x = b.x - w - gap; y = b.y + b.h / 2 - h / 2; }
    if (side === 'right') { x = b.x + b.w + gap; y = b.y + b.h / 2 - h / 2; }
    m.el.style.left = Math.max(4, x) + 'px'; m.el.style.top = Math.max(4, y) + 'px';
    return true;
  }

  // Draw one mark. With `pen`, each line draws along its length, as a pen does (300 to 900 ms by its length).
  function draw(m, pen) {
    const h = host();
    if (m.o.op === 'label') {
      if (!m.el) { m.el = Object.assign(document.createElement('div'), {className: 'board-label'}); m.el.textContent = m.o.text; h.append(m.el); }
      const ok = placeLabel(m);
      if (pen) requestAnimationFrame(() => m.el.classList.add('on')); else m.el.classList.add('on');
      return ok;
    }
    const ss = shapes(m);
    if (m.g) m.g.remove();
    m.g = document.createElementNS(NS, 'g'); m.g.dataset.op = m.o.op; m.g.dataset.step = m.step;
    if (!ss) { m.g.style.display = 'none'; h.querySelector('svg').append(m.g); return false; }
    m.g.append(...ss); h.querySelector('svg').append(m.g);
    if (pen && motion()) for (const p of m.g.querySelectorAll('path:not(.fill)')) {
      const L = p.getTotalLength(); if (!L) continue;
      p.style.strokeDasharray = L;
      p.animate([{strokeDashoffset: L}, {strokeDashoffset: 0}], {duration: Math.max(300, Math.min(900, L * 2)), easing: 'ease-out', fill: 'backwards'});
    }
    return true;
  }
  const motion = () => !matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Each mark again from its anchor, in the next frame. A mark whose anchor is gone hides; when all are gone, the strip says so.
  let queued = false;
  function follow() {
    if (!st || queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      if (!st) return;
      host();
      const ms = st.marks.filter(m => m.drawn);
      const ok = ms.map(m => draw(m, false));
      if (ms.length && !ok.some(Boolean)) note('The page changed. Ask again.');
    });
  }

  // --- the strip ----------------------------------------------------------------------------------------------------
  const TIER = {tutor: 'tutor', vault: 'your vault', web: 'web'};
  const safeHref = u => /^(https?:\/\/|\/(?!\/))/.test(String(u || ''));
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  function strip() { return document.getElementById('guide-strip') || document.body.appendChild(Object.assign(el('div', 'guide-strip'), {id: 'guide-strip'})); }
  function note(text) { const s = strip(); s.hidden = false; s.replaceChildren(el('p', 'board-note', text)); }
  function caption() {
    const s = strip(), b = st.board, step = b.steps[st.i];
    s.hidden = false;
    const top = el('div', 'board-top');
    top.append(el('span', 'pill tier-' + b.tier, TIER[b.tier] || 'tutor'), el('span', 'board-n', `Step ${st.i + 1} of ${b.steps.length}`));
    const say = el('p', 'board-say', step.say);
    const parts = [top, say];
    if (step.quote) {
      const src = b.sources[step.quote.src - 1] || {}, q = el('p', 'board-quote');
      q.append(el('q', '', step.quote.text), ' ', el('span', 'pill', src.label || 'source'), ' ', link(src));
      parts.push(q);
    }
    if (st.video) parts.push(st.video);
    if (st.i === b.steps.length - 1) {
      const end = el('p', 'board-end', b.end || "In the tutor's own words. No source found.");
      const used = (b.sources || []).filter(x => x.quoted);
      used.forEach(x => end.append(' ', link(x)));
      parts.push(end);
    }
    parts.push(el('p', 'board-keys', 'A again · S back · D next · Esc stop'));
    s.replaceChildren(...parts);
  }
  function link(src) {
    if (!src || !src.title) return el('span', '', '');
    if (!safeHref(src.url)) return el('span', 'board-src', src.title);
    const a = el('a', 'board-src', src.title);
    a.href = src.url;
    if (!src.url.startsWith('/')) { a.target = '_blank'; a.rel = 'noopener noreferrer'; }
    return a;
  }

  // --- steps and voice ----------------------------------------------------------------------------------------------
  function speak(text, onWord, done) {
    const words = text.split(/\s+/), byLetters = () => {   // no voice: time the words by their letters
      let t = 0; words.forEach((w, k) => { st.timers.push(setTimeout(() => onWord(k), t)); t += 55 * (w.length + 1); });
      st.timers.push(setTimeout(done, t + 200));
    };
    if (st.quiet || !('speechSynthesis' in window) || !speechSynthesis.getVoices().length) return byLetters();
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = st.rate;
    let got = false;
    u.onboundary = e => { if (e.name && e.name !== 'word') return; got = true; onWord(text.slice(0, e.charIndex).split(/\s+/).filter(Boolean).length); };
    u.onend = () => { if (!got) words.forEach((_, k) => onWord(k)); done(); };
    u.onerror = () => { if (st) byLetters(); };
    st.utter = u;
    speechSynthesis.speak(u);
    st.timers.push(setTimeout(() => { if (!got) words.forEach((_, k) => onWord(k)); }, 1500));   // WebKit can send no word marks
  }
  function quiet() {
    if (!st) return;
    st.timers.forEach(clearTimeout); st.timers = [];
    if ('speechSynthesis' in window) speechSynthesis.cancel();
  }
  function show(i) {
    if (!st) return;
    quiet();
    i = Math.max(0, Math.min(st.board.steps.length - 1, i));
    st.i = i;
    for (const m of st.marks) { if (m.g) m.g.remove(); if (m.el) m.el.remove(); m.g = m.el = null; m.drawn = false; }
    st.video = null;
    const run = m => {   // a mark that is done: `clear` takes away the marks before it
      if (m.o.op === 'clear') { st.marks.filter(x => x.drawn && (m.o.n == null || x.step === m.o.n - 1)).forEach(x => { if (x.g) x.g.remove(); if (x.el) x.el.remove(); x.g = x.el = null; x.drawn = false; }); return; }
      if (m.o.op === 'demo_set') return demo(m.o.set);
      if (m.o.op === 'video_at') return video(m.o);
      m.drawn = true; draw(m, m.step === st.i && !st.fast);
    };
    st.marks.filter(m => m.step < i).forEach(m => { if (m.o.op !== 'demo_set' && m.o.op !== 'video_at') run(m); });
    const step = st.board.steps[i], mine = st.marks.filter(m => m.step === i), started = new Set();
    caption();
    if (st.fast) { mine.forEach(run); return; }
    // the first mark of a board draws at once, so the learner sees at once that the tutor answers
    const wordOf = (m, n) => i === 0 && n === 0 ? 0 : m.o.w ?? Math.round(n * step.say.split(/\s+/).length / Math.max(1, mine.length));
    const at = k => mine.forEach((m, n) => { if (!started.has(n) && wordOf(m, n) <= k) { started.add(n); run(m); if (st.first == null) { st.first = performance.now(); document.dispatchEvent(new CustomEvent('board:first')); } } });
    at(0);
    speak(step.say, at, () => {
      mine.forEach((m, n) => { if (!started.has(n)) { started.add(n); run(m); } });
      if (st && st.auto && i < st.board.steps.length - 1) st.timers.push(setTimeout(() => show(i + 1), WAIT));
    });
  }
  function demo(set) {
    const h = anchorEl('demo');
    if (!h || !window.Rupaka || !h.rupaka) return;
    const s = h.rupaka, gates = [];
    const walk = bs => (bs || []).forEach(b => { if (b.type === 'gate') gates.push(b.id); walk(b.blocks); });
    walk(s.spec.blocks);
    if (!gates.every(g => s.st.gate && s.st.gate[g] === 'done')) return;   // the gate is still closed: never show the result first
    try { Rupaka.set(h, set); } catch (e) { console.warn('board: demo', e); }
  }
  function video(o) {
    const f = document.querySelector('#guide-video iframe');
    if (f && f.contentWindow) f.contentWindow.postMessage(JSON.stringify({event: 'command', func: 'seekTo', args: [o.t, true]}), 'https://www.youtube-nocookie.com');
    const vid = (document.getElementById('guide-video') || {dataset: {}}).dataset.vid || '', p = el('p', 'board-quote');
    const mm = `${Math.floor(o.t / 60)}:${String(Math.floor(o.t % 60)).padStart(2, '0')}`;
    p.append(el('q', '', o.quote), ' ');
    if (/^[A-Za-z0-9_-]{11}$/.test(vid)) { const a = el('a', 'board-src', `The video at ${mm}`); a.href = `https://www.youtube.com/watch?v=${vid}&t=${Math.floor(o.t)}s`; a.target = '_blank'; a.rel = 'noopener noreferrer'; p.append(a); }
    st.video = p; caption();
  }

  // --- keys: A again, S back, D next, Esc stop, only while a board shows and never in a text box ----------------------
  function onKey(e) {
    if (!st || e.metaKey || e.ctrlKey || e.altKey || e.shiftKey || e.repeat) return;
    const t = e.target;
    if (t && t.matches && t.matches('textarea, input, select, [contenteditable]')) return;
    const act = {KeyA: () => show(st.i), KeyS: () => show(st.i - 1), KeyD: () => show(st.i + 1), Escape: stop}[e.code];
    if (!act) return;
    e.preventDefault(); e.stopImmediatePropagation();
    if (e.code !== 'Escape') st.auto = e.code !== 'KeyS' && st.auto;
    act();
  }
  function stop() {
    quiet();
    const back = st && st.refocus;
    st = null;
    if (back && back.isConnected && !document.activeElement.matches('textarea, input, select, [contenteditable]')) back.focus({preventScroll: true});
    const h = document.getElementById('board-host'); if (h) h.remove();
    const s = document.getElementById('guide-strip'); if (s) { s.hidden = true; s.replaceChildren(); }
    document.dispatchEvent(new CustomEvent('board:stop'));
  }

  // Play a checked board. `labels` maps a figure anchor to its label boxes. `fast` draws each step at once, with no voice.
  async function play(board, {labels = {}, fast = false, quiet: q = false, auto = true} = {}) {
    if (st) stop();
    await libs();
    if (!board || !board.steps || !board.steps.length) { note(board && board.failed ? "The tutor's drawing failed. Say it again or type it." : 'The tutor did not answer. Try again.'); return; }
    st = {board, labels, fast, quiet: q || fast, auto: auto && !fast, i: 0, timers: [], rate: +(localStorage.getItem('board-rate') || 1), first: null,
          marks: board.steps.flatMap((s, k) => s.strokes.map((o, n) => ({o, step: k, seed: 1 + k * 10 + n})))};
    // An empty answer box with the focus (a check takes it when it loads) lets go of it, so A, S and D work. A box with your text
    // keeps it: then the keys type, and a click outside the box gives them to the board. Esc gives the focus back.
    const a = document.activeElement;
    if (a && a.matches && a.matches('textarea, input, select, [contenteditable]') && !a.value && !a.textContent) { st.refocus = a; a.blur(); }
    host();
    show(0);
    if (fast) for (let k = 1; k < board.steps.length; k++) show(k);
  }

  addEventListener('keydown', onKey, true);
  addEventListener('scroll', follow, {capture: true, passive: true});
  addEventListener('resize', follow);
  if (window.ResizeObserver) new ResizeObserver(follow).observe(document.documentElement);
  // A new page (an htmx swap of the body) takes the layer away: the board stops. A change inside the page moves the marks.
  const watch = () => new MutationObserver(ms => {
    if (!st) return;
    if (!document.getElementById('board-host')) return stop();
    if (ms.some(m => !(m.target.closest && m.target.closest('#board-host, #guide-strip')))) follow();
  }).observe(document.body, {childList: true, subtree: true});
  if (document.body) watch(); else addEventListener('DOMContentLoaded', watch);
  window.abhyasaBoard = {play, stop, note, next: () => st && show(st.i + 1), back: () => st && show(st.i - 1), again: () => st && show(st.i), boxOf, normTex,
                         get state() { return st && {i: st.i, steps: st.board.steps.length, tier: st.board.tier, first: st.first}; }};
})();
