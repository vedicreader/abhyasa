// The screen guide on the page: it reads what the page shows (the anchors), asks the tutor, and gives the board to board.js.
// The model never sends code. Only the anchors that this file finds can carry a mark. Formula parts come from core/texparts.js.

// --- what the page shows --------------------------------------------------------------------------------------------
if (typeof window !== 'undefined' && !window.abhyasaGuide) (() => {
  const me = document.currentScript ? document.currentScript.dataset : {};
  const cut = (s, n = 300) => String(s || '').replace(/\s+/g, ' ').trim().slice(0, n);
  const seen = el => el && (el.checkVisibility ? el.checkVisibility() : el.offsetParent !== null);
  const texOf = k => { const a = k.querySelector('annotation[encoding="application/x-tex"]'); return a ? a.textContent : ''; };
  const textOf = el => {   // the text of `el`, with each formula as its TeX between $ signs, and no hidden MathML
    if (!el) return '';
    const c = el.cloneNode(true);
    c.querySelectorAll('.katex').forEach(k => k.replaceWith(`$${texOf(k)}$`));
    c.querySelectorAll('script, style, textarea, input, select, button, .guide-go').forEach(x => x.remove());
    return cut(c.textContent, 300);
  };
  const figs = {};   // figure src -> labels, for this page load

  // Each formula on the page gets ids on its parts, once, when the guide first reads it. It looks the same as before.
  function markMath(root) {
    const out = [];
    root.querySelectorAll('.katex').forEach((k, n) => {
      if (out.length >= 12 || !seen(k)) return;
      const host = k.closest('span.math, div.math') || k.parentElement;
      if (!host.dataset.guideId) {
        const tex = texOf(k);
        if (!tex || !window.katex) return;
        const f = document.querySelectorAll('[data-guide-id^="m"]').length + 1, [marked, parts] = abhyasaTex.texParts(tex, f);
        try {
          katex.render(marked, host, {displayMode: host.classList.contains('display') || !!k.closest('.katex-display'), throwOnError: true, strict: false,
                                      trust: abhyasaTex.trust});
        } catch (e) { katex.render(tex, host, {displayMode: host.classList.contains('display'), throwOnError: false, trust: false}); parts.length = 0; }
        host.dataset.guideId = 'm' + f; host.dataset.tex = tex; host.dataset.parts = JSON.stringify(parts);
      }
      out.push(host);
    });
    return out;
  }

  // A rupaka demo: its inputs (from spec.state, with the label and range of the block that binds each one), its readouts, and
  // whether all its gates are done. The blocks are built in the order of the spec, so the n-th block is the n-th [data-rk-type].
  function demoOf(host) {
    const s = host.rupaka, spec = s && s.spec;
    if (!spec) return null;
    const flat = [], walk = bs => (bs || []).forEach(b => { flat.push(b); walk(b.blocks); });
    walk(spec.blocks);
    const nodes = [...host.querySelectorAll('[data-rk-type]')], inputs = {}, anchors = [], readouts = [];
    flat.forEach((b, n) => {
      const node = nodes[n];
      if (b.bind && Object.hasOwn(spec.state || {}, b.bind)) {
        inputs[b.bind] = {value: s.st[b.bind], label: b.label || b.bind, ...(b.min != null && {min: b.min}), ...(b.max != null && {max: b.max}), ...(b.step != null && {step: b.step})};
        if (node && seen(node)) { node.dataset.guideId = 'in:' + b.bind; anchors.push({id: 'in:' + b.bind, kind: 'input', text: `${b.label || b.bind} = ${JSON.stringify(s.st[b.bind])}`}); }
      } else if (node && seen(node) && /readout|caption|bars|pixels|plot/.test(b.type)) {
        const id = 'out:' + (readouts.length + 1);
        node.dataset.guideId = id; readouts.push(cut(node.textContent, 120));
        anchors.push({id, kind: 'readout', text: cut(node.textContent, 200) || b.label || b.type});
      }
    });
    const gates = flat.filter(b => b.type === 'gate').map(b => b.id);
    host.dataset.guideId = 'demo';
    anchors.unshift({id: 'demo', kind: 'demo', text: cut((spec.title || '') + '. ' + (spec.ask || ''), 300)});
    return {anchors, demo: {slug: spec.id || '', inputs, readouts, open: gates.every(g => s.st.gate && s.st.gate[g] === 'done')}};
  }

  // The labels of a figure: found once on the server by a vision call, and kept there by the hash of the image.
  async function labelsOf(img) {
    if (!img.complete || !img.naturalWidth) return {};
    if (figs[img.src]) return figs[img.src];
    try {
      const body = await (await fetch(img.src)).blob();
      const r = await (await fetch(me.figure + '?alt=' + encodeURIComponent(img.alt || ''), {method: 'POST', body})).json();
      return figs[img.src] = r.labels || {};
    } catch (e) { return {}; }
  }

  async function capture() {
    const main = document.querySelector('main') || document.body, anchors = [];
    const add = (el, id, kind, text) => { if (el && seen(el)) { el.dataset.guideId = id; anchors.push({id, kind, text}); } };
    const h1 = main.querySelector('h1');
    add(h1, 'title', 'title', textOf(h1));
    for (const [sel, kind] of [['#passage', 'passage'], ['#note', 'note'], ['#check', 'check']]) add(main.querySelector(sel), sel.slice(1), kind, textOf(main.querySelector(sel)));
    for (const host of markMath(main)) {
      anchors.push({id: host.dataset.guideId, kind: 'formula', text: host.dataset.tex, tokens: JSON.parse(host.dataset.parts || '[]').map(p => p[0])});
    }
    const figure = main.querySelector('#figure img') || main.querySelector('figure img');
    if (figure && seen(figure)) {
      const cap = figure.closest('figure') && figure.closest('figure').querySelector('figcaption');
      figure.dataset.guideId = 'figure';
      anchors.push({id: 'figure', kind: 'figure', text: cut([figure.alt, cap && cap.textContent].filter(Boolean).join('. ')), labels: await labelsOf(figure)});
    }
    main.querySelectorAll('figcaption, .rk-title').forEach((c, n) => n < 4 && add(c, 'cap' + (n + 1), 'caption', textOf(c)));
    let demo = {};
    const rk = [...main.querySelectorAll('[data-rupaka][data-rk-ready="1"]')].find(seen);
    if (rk) { const d = demoOf(rk); if (d) { anchors.push(...d.anchors); demo = d.demo; } }
    const video = main.querySelector('#guide-video[data-vid]');
    if (video) add(video, 'video', 'video', cut(video.dataset.title || 'The explainer video'));
    const src = main.querySelector('#passage .src-line');
    return {page: location.pathname, title: document.title, step: h1 ? cut(h1.textContent, 200) : '', slug: (main.querySelector('[data-concept]') || {dataset: {}}).dataset.concept || '',
            source: src ? cut(src.textContent) : '', anchors: anchors.slice(0, 40), demo, ...(video && {video: {id: video.dataset.vid}})};
  }

  // --- show while you talk ---------------------------------------------------------------------------------------------
  // While the guide asks (the key is held, or the box is open), the pointer path is kept in memory: page pixels, at most 30 Hz,
  // the last 15 s and 600 points, each [x, y, t] with t in ms from the start of the question. The ask takes it and forgets it.
  // `gestures` finds what the learner showed: a closed loop is a circle, a still pointer after a move is a point. The same rules
  // are in the overlay (mac/Sources/AbhyasaGuide/Gestures.swift), and both test against tests/data/gesture_paths.json.
  const G = {hz: 30, keep: 15000, most: 600, dwellPx: 12, dwellMs: 400, travelPx: 40, turnDeg: 300, maxTurnDeg: 540, minSide: 24,
             closePx: 20, closeFrac: .35, thinPx: 3, loopMs: 8000, nearMs: 1000, items: 5, fade: 1500};
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  function gestures(pts, end) {   // pts [[x, y, t]] in time order -> [{kind, box: [x0, y0, x1, y1], t}], the latest first
    pts = (pts || []).slice(-G.most);
    const n = pts.length, out = [];
    if (end == null) end = n ? pts[n - 1][2] : 0;
    const q = [];   // the path with no steps under thinPx, for the turns
    for (const p of pts) if (!q.length || dist(p, q[q.length - 1]) >= G.thinPx) q.push(p);
    const circles = [];
    for (let i = 0; i < q.length - 2;) {
      let turn = 0, x0 = q[i][0], y0 = q[i][1], x1 = x0, y1 = y0, hit = -1;
      for (let j = i + 1; j < q.length; j++) {
        x0 = Math.min(x0, q[j][0]); y0 = Math.min(y0, q[j][1]); x1 = Math.max(x1, q[j][0]); y1 = Math.max(y1, q[j][1]);
        if (q[j][2] - q[i][2] > G.loopMs) break;
        if (j >= i + 2) {
          const ax = q[j - 1][0] - q[j - 2][0], ay = q[j - 1][1] - q[j - 2][1], bx = q[j][0] - q[j - 1][0], by = q[j][1] - q[j - 1][1];
          turn += Math.atan2(ax * by - ay * bx, ax * bx + ay * by) * 180 / Math.PI;
        }
        if (Math.abs(turn) > G.maxTurnDeg) break;
        const w = x1 - x0, h = y1 - y0;
        if (Math.abs(turn) >= G.turnDeg && Math.min(w, h) >= G.minSide && dist(q[j], q[i]) <= Math.max(G.closePx, G.closeFrac * Math.max(w, h))) { hit = j; break; }
      }
      if (hit < 0) { i++; continue; }
      circles.push({kind: 'circle', box: [x0, y0, x1, y1].map(Math.round), t: Math.round(q[hit][2]), t0: q[i][2]});
      i = hit;
    }
    const points = [];
    for (let i = 0, from = 0; i < n;) {
      let j = i;
      while (j + 1 < n && dist(pts[j + 1], pts[i]) <= G.dwellPx) j++;
      const until = j + 1 < n ? pts[j + 1][2] : end;
      if (until - pts[i][2] < G.dwellMs) { i++; continue; }
      const blob = pts.slice(i, j + 1), c = [0, 1].map(k => blob.reduce((s, p) => s + p[k], 0) / blob.length);
      if (pts.slice(from, i).some(p => dist(p, c) >= G.travelPx)) {   // only after a move: a hand that rests on the mouse shows nothing
        const inCircle = circles.some(g => c[0] >= g.box[0] - G.dwellPx && c[0] <= g.box[2] + G.dwellPx && c[1] >= g.box[1] - G.dwellPx && c[1] <= g.box[3] + G.dwellPx &&
                                           pts[i][2] >= g.t0 && pts[i][2] <= g.t + G.nearMs);
        if (!inCircle) points.push({kind: 'point', box: [c[0] - G.dwellPx, c[1] - G.dwellPx, c[0] + G.dwellPx, c[1] + G.dwellPx].map(Math.round), t: Math.round(pts[i][2])});
      }
      from = i; i = j + 1;
    }
    return [...circles, ...points].sort((a, b) => b.t - a.t).slice(0, G.items).map(({kind, box, t}) => ({kind, box, t}));
  }

  // The anchors under a gesture, the best first: for a circle, the anchors that it covers most (by the share of the two boxes);
  // for a point, the anchors that hold it, the smallest first. `anchors` is [{id, box: [x0, y0, x1, y1]}] in the same pixels.
  const area = b => Math.max(0, b[2] - b[0]) * Math.max(0, b[3] - b[1]);
  const meet = (a, b) => [Math.max(a[0], b[0]), Math.max(a[1], b[1]), Math.min(a[2], b[2]), Math.min(a[3], b[3])];
  function under(g, anchors) {
    if (g.kind === 'point') {
      const c = [(g.box[0] + g.box[2]) / 2, (g.box[1] + g.box[3]) / 2];
      return anchors.filter(a => c[0] >= a.box[0] && c[0] <= a.box[2] && c[1] >= a.box[1] && c[1] <= a.box[3]).sort((a, b) => area(a.box) - area(b.box)).slice(0, 4);
    }
    return anchors.map(a => { const i = area(meet(g.box, a.box)); return {a, i, s: i / (area(g.box) + area(a.box) - i || 1)}; })
                  .filter(o => o.i > 0 && (o.i >= .25 * area(g.box) || o.i >= .5 * area(o.a.box))).sort((x, y) => y.s - x.s).slice(0, 4).map(o => o.a);
  }
  // The focus for the ask: each gesture with its anchors, and its box from 0 to 1000 of the first anchor (the part of the gesture
  // inside it), so the tutor can mark it with {"a": id, "box": box}. A gesture on no anchor is left out.
  function focusOf(gs, anchors) {
    const out = [];
    for (const g of gs || []) {
      const as = under(g, anchors);
      if (!as.length) continue;
      const a = as[0].box, w = a[2] - a[0], h = a[3] - a[1], m = meet(g.box, a);
      if (w <= 0 || h <= 0) continue;
      const box = [(m[0] - a[0]) / w, (m[1] - a[1]) / h, (m[2] - a[0]) / w, (m[3] - a[1]) / h].map(v => Math.round(Math.max(0, Math.min(1, v)) * 1000));
      if (box[0] >= box[2] || box[1] >= box[3]) continue;
      out.push({kind: g.kind, box, anchors: as.map(x => x.id), t: g.t, ...(g.words && {words: g.words})});
    }
    return out;
  }

  // The trail: a faint line of the last 1.5 s of the path, and a soft ring when a gesture is found. It never takes a click.
  // With prefers-reduced-motion there is no trail, only the ring, and the ring does not move.
  let rec = null;   // {t0, pts, said, rings, timer} while the guide asks; null at all other times
  const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  function trailLayer() {
    let t = document.getElementById('board-trail');
    if (!t) {
      t = Object.assign(document.createElement('div'), {id: 'board-trail', className: 'board-trail'});
      t.setAttribute('aria-hidden', 'true');
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.append(document.createElementNS('http://www.w3.org/2000/svg', 'polyline'));
      t.append(svg); document.body.append(t);
    }
    return t;
  }
  function drawTrail() {
    if (!rec || reducedMotion()) return;
    const now = performance.now() - rec.t0, live = rec.pts.filter(p => now - p[2] < G.fade);
    trailLayer().querySelector('polyline').setAttribute('points', live.map(p => p[0] + ',' + p[1]).join(' '));
    rec.drawing = live.length > 0;
    if (rec.drawing) requestAnimationFrame(drawTrail);
  }
  function ring(g) {
    const r = Object.assign(document.createElement('div'), {className: 'board-trail-ring' + (g.kind === 'point' ? ' point' : '')}), pad = g.kind === 'point' ? 6 : 8;
    Object.assign(r.style, {left: g.box[0] - pad + 'px', top: g.box[1] - pad + 'px', width: g.box[2] - g.box[0] + 2 * pad + 'px', height: g.box[3] - g.box[1] + 2 * pad + 'px'});
    trailLayer().append(r);
    setTimeout(() => r.remove(), G.fade);
  }
  function spot(end) {   // ring each gesture of the last 4 s once, as the learner makes it
    if (!rec) return;
    const now = end ?? performance.now() - rec.t0;
    for (const g of gestures(rec.pts.filter(p => now - p[2] < 4000), now)) {
      const k = g.kind + Math.round(g.box[0] / 24) + ':' + Math.round(g.box[1] / 24);
      if (!rec.rings.has(k)) { rec.rings.add(k); ring(g); }
    }
  }
  function heard_(r) {   // what the box says now (typed, or written by the mic), kept with its time
    const b = box(), v = b ? b.value : '', s = r.said;
    if (!s.length || s[s.length - 1][1] !== v) s.push([Math.round(performance.now() - r.t0), v]);
  }
  function onMove(e) {
    if (!rec || (e.target.closest && e.target.closest('#guide-form, #guide-strip'))) return;
    const t = performance.now() - rec.t0, ps = rec.pts;
    if (ps.length && t - ps[ps.length - 1][2] < 1000 / G.hz) return;
    ps.push([Math.round(e.pageX), Math.round(e.pageY), Math.round(t)]);
    while (ps.length > G.most || t - ps[0][2] > G.keep) ps.shift();
    heard_(rec);
    if (!rec.drawing) { rec.drawing = true; requestAnimationFrame(drawTrail); }
    spot();
    clearTimeout(rec.timer); rec.timer = setTimeout(() => spot(), G.dwellMs + 50);   // a still pointer shows its ring
  }
  function startShow() {
    if (rec) return;
    rec = {t0: performance.now(), pts: [], said: [], rings: new Set(), timer: 0, drawing: false};
    addEventListener('mousemove', onMove, {capture: true, passive: true});
  }
  function stopShow() {   // the path and what was said with it; then nothing of it is kept
    if (!rec) return null;
    const r = rec; rec = null;
    heard_(r);
    removeEventListener('mousemove', onMove, {capture: true});
    clearTimeout(r.timer);
    const t = document.getElementById('board-trail'); if (t) t.remove();
    return {pts: r.pts, said: r.said, end: Math.round(performance.now() - r.t0)};
  }
  const wordsAt = (said, t) => {   // the last words in the box a little after `t`: speech comes in late
    let v = '';
    for (const [k, s] of said) if (k <= t + 1500) v = s;
    return cut(v.split(/\s+/).slice(-8).join(' '), 80);
  };

  // The focus of a question: the gestures, mapped to the anchors that capture() found. A gesture on no anchor gets the smallest
  // element with text or a picture under its centre, as a new anchor (f1, f2, …), when that element is in the page.
  function focusFor(shown, ctx) {
    if (!shown || !shown.pts.length) return [];
    const gs = gestures(shown.pts, shown.end);
    if (!gs.length) return [];
    const boxOf = id => { const e = document.querySelector(`[data-guide-id="${CSS.escape(id)}"]`); if (!e) return null; const r = e.getBoundingClientRect(); return [r.left + scrollX, r.top + scrollY, r.right + scrollX, r.bottom + scrollY]; };
    const anchors = ctx.anchors.map(a => ({id: a.id, box: boxOf(a.id)})).filter(a => a.box);
    const main = document.querySelector('main') || document.body;
    for (const g of gs) {
      if (under(g, anchors).length) continue;
      let el = document.elementFromPoint((g.box[0] + g.box[2]) / 2 - scrollX, (g.box[1] + g.box[3]) / 2 - scrollY);
      while (el && el !== main && !(el.tagName === 'IMG' || cut(el.textContent, 1))) el = el.parentElement;
      if (!el || el === main || !main.contains(el) || el.closest('#guide-form, #guide-strip, #board-host, nav')) continue;
      const id = el.dataset.guideId || 'f' + (anchors.filter(a => /^f\d+$/.test(a.id)).length + 1);
      if (!el.dataset.guideId) { el.dataset.guideId = id; ctx.anchors.unshift({id, kind: el.tagName === 'IMG' ? 'figure' : 'text', text: el.tagName === 'IMG' ? cut(el.alt) : textOf(el)}); }
      anchors.unshift({id, box: boxOf(id)});
    }
    ctx.anchors = ctx.anchors.slice(0, 40);
    return focusOf(gs.map(g => ({...g, words: wordsAt(shown.said, g.t)})), anchors.filter(a => ctx.anchors.some(x => x.id === a.id)));
  }

  // --- asking ----------------------------------------------------------------------------------------------------------
  const form = () => document.getElementById('guide-form'), box = () => document.getElementById('guide-box');
  const heard = t => { const h = form() && form().querySelector('.guide-heard'); if (h) h.textContent = t; };
  const say = t => window.abhyasaBoard && abhyasaBoard.note(t);
  function open(text) {
    const f = form(), b = box();
    if (!f || !b) return;
    const sel = cut(String(getSelection() || ''), 80);
    f.hidden = false; heard(''); startShow();
    b.value = text != null ? text : sel ? `I don't get "${sel}"` : '';
    b.focus(); b.setSelectionRange(b.value.length, b.value.length);
  }
  function close() { stopShow(); if (form()) form().hidden = true; }

  // Ask the tutor: read the page, post the question with it, and play the board that comes back. A sure tutor sends each step
  // when it is whole: the first step starts a streaming board, and each next step goes to abhyasaBoard.add. The board event at
  // the end is the whole board: it finishes the streaming board, or plays as it is when no step came. The times go into
  // `abhyasaGuideLast`: from the press of Explain to the first step, to the board, and to the first mark.
  let asks = 0;   // a newer question takes the place of an older one, so the steps of the older one go nowhere
  async function ask(said) {
    said = cut(said, 300);
    if (!said) return;
    const shown = stopShow();   // what the learner showed with the pointer while they asked
    close();
    const t0 = performance.now(), last = window.abhyasaGuideLast = {said, t0}, n = ++asks;
    const opts = () => ({labels, quiet: !!window.abhyasaGuideQuiet}), mark = () => document.addEventListener('board:first', () => { last.first_ms = Math.round(performance.now() - t0); }, {once: true});
    let labels = {}, live = null;   // live: the promise of the streaming board, with each add after it
    say('The tutor reads the page.');
    try {
      const ctx = await capture();
      const focus = focusFor(shown, ctx);
      if (focus.length) ctx.focus = last.focus = focus;
      last.capture_ms = Math.round(performance.now() - t0);
      labels = Object.fromEntries(ctx.anchors.filter(a => a.labels).map(a => [a.id, a.labels]));
      const r = await fetch(me.ask, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({said, ctx})});
      if (!r.ok) return say(cut(await r.text(), 200) || 'The tutor could not answer. Try again.');
      const rd = r.body.getReader(), dec = new TextDecoder();
      let buf = '';
      for (;;) {
        const {value, done} = await rd.read();
        if (done) break;
        buf += dec.decode(value, {stream: true});
        let k;
        while ((k = buf.indexOf('\n\n')) >= 0) {
          const ev = buf.slice(0, k); buf = buf.slice(k + 2);
          if (!ev.startsWith('data: ')) continue;
          const m = JSON.parse(ev.slice(6));
          if (n !== asks) return rd.cancel();
          if (m.wait) say(m.wait);
          if (m.error) say(m.error);
          if (m.step && !live) {
            last.step_ms = Math.round(performance.now() - t0); mark();
            live = abhyasaBoard.play({steps: [m.step], tier: m.tier || 'tutor', sources: [], streaming: true}, opts());
          } else if (m.step) live = live.then(() => n === asks && abhyasaBoard.add(m.step));
          if (m.board) {
            last.board_ms = Math.round(performance.now() - t0); last.server_ms = m.board.ms; last.tier = m.board.tier;
            if (!live) { mark(); await abhyasaBoard.play(m.board, opts()); }
            else {
              await live;
              const b = abhyasaBoard.state;   // null when the learner stopped the board
              if (n === asks && b && b.streaming && !abhyasaBoard.finish(m.board)) await abhyasaBoard.play(m.board, opts());
            }
          }
        }
      }
    } catch (e) { say('The tutor could not answer. Make sure that abhyasa runs, then try again.'); }
  }

  // --- Hyper+E: hold to talk, tap to type -------------------------------------------------------------------------------
  // Hyper is ⌃⌥⇧⌘ (Caps Lock with a key remapper). A hold of HOLD ms or more starts the mic of the voice block into the box;
  // the release stops it, and the words go to the tutor when the last of them is in. A tap opens the box. macOS sends no
  // keyup for E while ⌘ is down, so the keyup of any of the four modifiers is a release too.
  const HOLD = 300;
  let held = null, mic = null;
  function micButton() {
    const tpl = document.getElementById('mic-float');
    if (!tpl) return null;
    if (!mic || !mic.isConnected) {
      mic = Object.assign(document.createElement('button'), {type: 'button', id: 'guide-mic', hidden: true});
      mic.innerHTML = '<span class="say">Speak</span><i class="lvl"></i>';   // fixed markup, as the voice block makes it
      for (const k of ['vad', 'start', 'seg', 'stop', 'events']) mic.dataset[k] = tpl.dataset[k];
      mic.dataset.into = 'guide-box';
      form().append(mic);
    }
    return mic;
  }
  function talk() {
    open('');
    const b = micButton();
    if (!b || !window.abhyasaMic) { heard('Type your question. The mic is not ready.'); return; }
    heard('The mic is on. Release the key to send.');
    abhyasaMic(b);
  }
  async function endTalk() {
    const b = micButton();
    if (!b || !window.abhyasaDict || abhyasaDict.btn !== b) return;
    heard('The app writes what you said.');
    await abhyasaMic(b);   // the second press stops it; the last words still come in
    const end = performance.now() + 15000;
    while (performance.now() < end && (b.classList.contains('busy') || b.classList.contains('on'))) await new Promise(ok => setTimeout(ok, 100));
    if (box().value.trim()) ask(box().value); else heard('The mic heard nothing. Type your question.');
  }
  addEventListener('keydown', e => {
    if (e.code !== 'KeyE' || !(e.metaKey && e.altKey && e.ctrlKey && e.shiftKey)) return;
    e.preventDefault(); e.stopImmediatePropagation();   // before core.js, which would press the ⌥E button of a concept page
    if (e.repeat || held) return;
    if (me.warm) fetch(me.warm, {method: 'POST'}).catch(() => {});   // the model starts while you talk or type; the server limits how often
    held = {timer: setTimeout(() => { if (held) { held.talking = true; talk(); } }, HOLD)};
  }, true);
  const release = e => {
    if (!held || !(e.code === 'KeyE' || /^(Meta|Alt|Control|Shift)/.test(e.key || ''))) return;
    const h = held; held = null; clearTimeout(h.timer);
    if (h.talking) endTalk(); else open();
  };
  addEventListener('keyup', release, true);
  addEventListener('blur', () => release({code: 'KeyE'}));

  document.addEventListener('click', e => { if (e.target.closest && e.target.closest('#guide-go')) { e.preventDefault(); open(); } });
  document.addEventListener('click', e => {   // a time in the transcript seeks the video on the page; a click with a modifier opens YouTube
    const a = e.target.closest && e.target.closest('#guide-video a[data-t]');
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || !window.abhyasaBoard || !abhyasaBoard.seekVideo) return;
    e.preventDefault(); abhyasaBoard.seekVideo(+a.dataset.t);
  });
  document.addEventListener('submit', e => { if (e.target.id === 'guide-form') { e.preventDefault(); ask(box().value); } });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && e.target.id === 'guide-box') { e.preventDefault(); e.stopPropagation(); close(); } });

  window.abhyasaGuide = {capture, texParts: (...a) => abhyasaTex.texParts(...a), labelsOf, ask, open, gestures, focusOf, G};
})();
