// The screen guide on the page: it reads what the page shows (the anchors), asks the tutor, and gives the board to board.js.
// The model never sends code. Only the anchors that this file finds can carry a mark. Formula parts come from core/texparts.js.

// --- what the page shows --------------------------------------------------------------------------------------------
if (typeof window !== 'undefined' && !window.abhyasaGuide) (() => {
  const me = document.currentScript ? document.currentScript.dataset : {};
  const info = (() => { try { return JSON.parse(me.info || '{}'); } catch (e) { return {}; } })();   // who gets what: the guide model, the figure model, the speech engine
  const HERE = 'on this Mac';
  const where = w => !w || !w.where ? '' : w.where === HERE ? HERE : w.who ? `hosted · ${w.who}` : 'hosted';
  const cut = (s, n = 300) => String(s || '').replace(/\s+/g, ' ').trim().slice(0, n);
  const seen = el => el && (el.checkVisibility ? el.checkVisibility() : el.offsetParent !== null);
  const texOf = k => {   // the TeX of a formula as the page wrote it: a marked formula keeps it in data-tex, and its annotation holds the ids
    const h = k.closest('[data-tex]'); if (h) return h.dataset.tex;
    const a = k.querySelector('annotation[encoding="application/x-tex"]'); return a ? a.textContent : '';
  };
  // The text of `el`, with each formula as its TeX between $ signs, and no hidden MathML. A part that is not inline on the page
  // (a paragraph, a label, a pill) gets a space before and after it, so its words do not run into the next words. The source line of a
  // passage and the buttons are not text of the page: the source goes in `source`.
  const SKIP = 'script, style, textarea, input, select, button, .guide-go, .src-line';
  const textOf = el => {
    if (!el) return '';
    const c = el.cloneNode(true), mine = [...el.querySelectorAll('*')], copies = [...c.querySelectorAll('*')];
    mine.forEach((m, n) => { if (!m.closest('.katex') && getComputedStyle(m).display !== 'inline') copies[n].dataset.guideGap = '1'; });
    c.querySelectorAll('.katex').forEach(k => k.replaceWith(`$${texOf(k)}$`));
    c.querySelectorAll(SKIP).forEach(x => x.remove());
    c.querySelectorAll('[data-guide-gap]').forEach(x => { x.before(' '); x.after(' '); });
    return cut(c.textContent, 300);
  };
  const sourceOf = line => {   // the title and the place of a source line, with no pill and no link to open it
    if (!line) return '';
    const c = line.cloneNode(true);
    c.querySelectorAll('.pill, .src-open, button').forEach(x => x.remove());
    return cut(c.textContent);
  };
  const figs = {};   // figure src -> labels, for this page load

  // The last graded try of a check, from its thread (a walk step or a session): the learner's answer, the outcome, the feedback,
  // the Error line, the gaps that the answer points at, whether the check is closed, and the tries that are left. Each field has
  // the bound of the server (TRY in abhyasa.guide). Null when the check has no graded try yet.
  const TRY = {answer: 400, feedback: 500, error: 240, outcome: 40, gaps: 5, gap: 60};
  const plain = (el, drop, n) => {   // the text of `el` with its formulas as TeX, without the parts that `drop` names
    if (!el) return '';
    const c = el.cloneNode(true);
    c.querySelectorAll('.katex').forEach(k => k.replaceWith(`$${texOf(k)}$`));
    c.querySelectorAll(`${SKIP}, ${drop}`).forEach(x => x.remove());
    return cut(c.textContent, n);
  };
  function tryOf(chk) {
    const you = [...chk.querySelectorAll('.thread > li.you')].pop();
    let fb = you && you.nextElementSibling;
    while (fb && (fb.matches('.you, .hint, .extra') || !fb.matches('li.m'))) fb = fb.nextElementSibling;   // the reply to the try: a nudge or the close
    if (!you || !fb) return null;
    const gaps = [...chk.querySelectorAll('.rh-gapline b')].flatMap(b => b.textContent.split(',')).map(g => cut(g, TRY.gap)).filter(Boolean).slice(0, TRY.gaps);
    const left = /\b(\d+|one|two)\s+(?:more\s+)?tr(?:y|ies)\b/i.exec(((chk.querySelector('.conf .mute') || document.getElementById('left') || {}).textContent) || '');
    const n = left ? ({one: 1, two: 2}[left[1].toLowerCase()] ?? +left[1]) : null;
    const closed = chk.matches('.shut, .done') || !!chk.querySelector('.check.shut, .check.done, .thread > li.close');
    const tag = fb.querySelector('.tag');
    return {el: you, answer: plain(you, '.lbl, .thought', TRY.answer), outcome: tag ? cut(tag.textContent, TRY.outcome) : '',
            feedback: plain(fb, '.lbl, .tag, .err, .lesson, .now, .cites, .feedback, form', TRY.feedback),
            error: cut(plain(fb.querySelector('.err'), '.k', TRY.error), TRY.error), gaps, state: closed ? 'closed' : 'open', ...(n != null && !closed && {left: n})};
  }

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

  // What the page shows. A figure gets its labels only with {labels: true}: its picture goes to the vision model then.
  async function capture({labels = false} = {}) {
    const main = document.querySelector('main') || document.body, anchors = [];
    const add = (el, id, kind, text) => { if (el && seen(el)) { el.dataset.guideId = id; anchors.push({id, kind, text}); } };
    const h1 = main.querySelector('h1');
    add(h1, 'title', 'title', textOf(h1));
    const passage = main.querySelector('#passage') || main.querySelector('.walk-passages blockquote');   // a concept page shows its passage from a walk
    add(main.querySelector('.statement'), 'statement', 'text', textOf(main.querySelector('.statement')));   // the statement of a concept page
    add(passage, 'passage', 'passage', textOf(passage));
    add(main.querySelector('#note'), 'note', 'note', textOf(main.querySelector('#note')));
    const chk = main.querySelector('#check') || main.querySelector('#chat .check.qa');   // the check of a walk step, else the question of a session
    add(chk, 'check', 'check', textOf(chk));
    const tried = chk && seen(chk) && tryOf(chk);   // the learner's last graded try, so the guide can explain the gaps in it
    if (tried) { const {el, ...t} = tried; el.dataset.guideId = 'try'; anchors.push({id: 'try', kind: 'try', text: cut(t.answer, 300), ...t}); }
    for (const host of markMath(main)) {
      anchors.push({id: host.dataset.guideId, kind: 'formula', text: host.dataset.tex, tokens: JSON.parse(host.dataset.parts || '[]').map(p => p[0])});
    }
    const figure = main.querySelector('#figure img') || main.querySelector('figure img');
    if (figure && seen(figure)) {
      const cap = figure.closest('figure') && figure.closest('figure').querySelector('figcaption');
      figure.dataset.guideId = 'figure';
      anchors.push({id: 'figure', kind: 'figure', text: cut(cap ? cap.textContent : figure.alt), ...(labels && {labels: await labelsOf(figure)})});   // the caption, else the alt
    }
    main.querySelectorAll('figcaption, .rk-title').forEach((c, n) => n < 4 && add(c, 'cap' + (n + 1), 'caption', textOf(c)));
    let demo = {};
    const rk = [...main.querySelectorAll('[data-rupaka][data-rk-ready="1"]')].find(seen);
    if (rk) { const d = abhyasaBoard.demoAnchors(rk); if (d) { anchors.push(...d.anchors); demo = d.demo; } }
    const video = main.querySelector('#guide-video[data-vid]');
    if (video) add(video, 'video', 'video', cut(video.dataset.title || 'The explainer video'));
    const src = passage && passage.querySelector('.src-line');
    return {page: location.pathname, title: document.title, step: h1 ? cut(h1.textContent, 200) : '', slug: (main.querySelector('[data-concept]') || {dataset: {}}).dataset.concept || '',
            source: sourceOf(src), anchors: anchors.slice(0, 40), demo, ...(video && {video: {id: video.dataset.vid}})};
  }

  // --- show while you talk ---------------------------------------------------------------------------------------------
  // While the guide asks (the key is held, or the box is open), the pointer path is kept in memory: page pixels, at most 30 Hz,
  // the last 15 s and 600 points, each [x, y, t] with t in ms from the start of the question. The ask takes it and forgets it.
  // `gestures` finds what the learner showed: a closed loop is a circle, a still pointer after a move is a point. The same rules
  // are in the overlay (mac/Sources/AbhyasaGuide/Gestures.swift), and both test against tests/data/gesture_paths.json.
  const G = {hz: 30, keep: 15000, most: 600, dwellPx: 12, dwellMs: 400, travelPx: 40, turnDeg: 300, maxTurnDeg: 540, minSide: 24,
             closePx: 20, closeFrac: .35, thinPx: 3, loopMs: 8000, nearMs: 1000, items: 5, fade: 1500, lenFrac: 1.5, stepFrac: .5};
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  function gestures(pts, end) {   // pts [[x, y, t]] in time order -> [{kind, box: [x0, y0, x1, y1], t}], the latest first
    pts = (pts || []).slice(-G.most);
    const n = pts.length, out = [];
    if (end == null) end = n ? pts[n - 1][2] : 0;
    const q = [];   // the path with no steps under thinPx, for the turns
    for (const p of pts) if (!q.length || dist(p, q[q.length - 1]) >= G.thinPx) q.push(p);
    const circles = [];
    for (let i = 0; i < q.length - 2;) {
      let turn = 0, x0 = q[i][0], y0 = q[i][1], x1 = x0, y1 = y0, hit = -1, len = 0, step = 0;
      for (let j = i + 1; j < q.length; j++) {
        x0 = Math.min(x0, q[j][0]); y0 = Math.min(y0, q[j][1]); x1 = Math.max(x1, q[j][0]); y1 = Math.max(y1, q[j][1]);
        const d = dist(q[j], q[j - 1]); len += d; step = Math.max(step, d);
        if (q[j][2] - q[i][2] > G.loopMs) break;
        if (j >= i + 2) {
          const ax = q[j - 1][0] - q[j - 2][0], ay = q[j - 1][1] - q[j - 2][1], bx = q[j][0] - q[j - 1][0], by = q[j][1] - q[j - 1][1];
          turn += Math.atan2(ax * by - ay * bx, ax * bx + ay * by) * 180 / Math.PI;
        }
        if (Math.abs(turn) > G.maxTurnDeg) break;
        const w = x1 - x0, h = y1 - y0;
        if (Math.abs(turn) >= G.turnDeg && Math.min(w, h) >= G.minSide && dist(q[j], q[i]) <= Math.max(G.closePx, G.closeFrac * Math.max(w, h))) { hit = j; break; }
      }
      // a smooth loop only: its path is not much longer than the round of its box, and no one step jumps across it (a shaking hand)
      const half = (x1 - x0 + y1 - y0) / 2;
      if (hit < 0 || len > G.lenFrac * Math.PI * half || step > G.stepFrac * half) { i++; continue; }
      const box = [x0, y0, x1, y1].map(Math.round), t0 = q[i][2];   // a loop on an earlier circle of the last second is the same circle
      if (!circles.some(g => g.t >= t0 - G.nearMs && Math.min(box[2], g.box[2]) > Math.max(box[0], g.box[0]) && Math.min(box[3], g.box[3]) > Math.max(box[1], g.box[1])))
        circles.push({kind: 'circle', box, t: Math.round(q[hit][2]), t0});
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
  const follow = on => { const p = form() && form().querySelector('.guide-follow'); if (p) { p.hidden = !on; p.textContent = on ? 'The guide follows your pointer while you ask.' : ''; } };
  function startShow() {
    if (rec) return;
    follow(true);
    rec = {t0: performance.now(), pts: [], said: [], rings: new Set(), timer: 0, drawing: false};
    addEventListener('mousemove', onMove, {capture: true, passive: true});
  }
  function stopShow() {   // the path and what was said with it; then nothing of it is kept
    if (!rec) return null;
    const r = rec; rec = null;
    follow(false);
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

  // --- the thread of the page ------------------------------------------------------------------------------------------
  // A follow-up ("say that more simply", "why?") means the last board. So the page keeps the last 3 turns on this page, each the
  // question, the lines that its board said and its tier, and sends them with the next question. They are in memory only: the
  // thread clears when the page changes, after 10 minutes with no question, or with Start fresh. Nothing goes to disk, and the
  // server keeps none of it. The bounds are the server's too (`clean_context`): a cut line or turn there is cut here first.
  const TH = {turns: 3, said: 300, says: 6, say: 160, total: 1500, idle: 600000};
  const pageKey = () => location.pathname;
  let thread = {page: pageKey(), at: 0, turns: []};
  const size = t => t.said.length + t.says.reduce((n, x) => n + x.length, 0);
  function fresh() { thread = {page: pageKey(), at: 0, turns: []}; threadLine(); }
  function turns() {   // the thread now; an old one or one of another page goes first
    if (thread.turns.length && (thread.page !== pageKey() || Date.now() - thread.at > TH.idle)) fresh();
    return thread.turns;
  }
  function keep(said, board, page) {   // the turn of a board that the learner saw, on the page where they asked
    const says = (board && board.steps || []).map(x => cut(x && x.say, TH.say)).filter(Boolean).slice(0, TH.says);
    if (!says.length || page !== pageKey()) return;
    const ts = [...turns(), {said: cut(said, TH.said), says, t: board.tier || 'tutor'}].slice(-TH.turns);
    while (ts.length && ts.reduce((n, t) => n + size(t), 0) > TH.total) ts.shift();
    thread = {page, at: Date.now(), turns: ts};
  }
  function threadLine() {   // "Follows up on: <the last question>", with Start fresh, under the box while a thread exists
    const p = form() && form().querySelector('.guide-thread'), ts = turns();
    if (!p) return;
    p.hidden = !ts.length;
    const last = ts.length ? ts[ts.length - 1].said : '';
    p.querySelector('.guide-thread-said').textContent = last ? `Follows up on: ${last.length > 60 ? last.slice(0, 59) + '…' : last}` : '';
  }
  document.addEventListener('htmx:afterSwap', e => {   // a new main page (a link of the app, hx-boost): a new thread
    const t = e.detail && e.detail.target, main = document.querySelector('main');
    if (t && (t === document.body || t.tagName === 'MAIN' || (main && t.contains(main)))) fresh();
  });
  addEventListener('popstate', () => fresh());

  // --- asking ----------------------------------------------------------------------------------------------------------
  const form = () => document.getElementById('guide-form'), box = () => document.getElementById('guide-box');
  const heard = t => { const h = form() && form().querySelector('.guide-heard'); if (h) h.textContent = t; };
  const say = t => window.abhyasaBoard && abhyasaBoard.note(t);
  function open(text) {
    const f = form(), b = box();
    if (!f || !b) return;
    const sel = cut(String(getSelection() || ''), 80);
    f.hidden = false; heard(''); threadLine(); startShow();
    const st = document.getElementById('guide-strip');   // a follow-up opens the box while the board strip shows: the box goes over the strip
    f.style.bottom = '';
    if (st && !st.hidden && st.offsetHeight + 8 > parseFloat(getComputedStyle(f).bottom)) f.style.bottom = st.offsetHeight + 8 + 'px';
    if (!localStorage.getItem('guide-told')) {   // the first Explain: one line, no sheet
      localStorage.setItem('guide-told', '1');
      const m = info.model || {};
      heard(`When you ask, the guide sends your question and the page text to ${m.model || 'the tutor'} (${where(m) || 'hosted'}). Esc stops it.`);
    }
    b.value = text != null ? text : sel ? `Explain "${sel}"` : '';
    b.focus(); b.setSelectionRange(b.value.length, b.value.length);
  }
  function close() { stopShow(); if (form()) form().hidden = true; }

  // What the read takes, in one line: "Reads this page: the passage, the note, 2 formulas and 1 figure."
  function readLine(ctx) {
    const k = kind => ctx.anchors.filter(a => a.kind === kind).length, n = (x, w) => `${x} ${w}${x === 1 ? '' : 's'}`, out = [];
    for (const [kind, w] of [['passage', 'the passage'], ['note', 'the note'], ['check', 'the check'], ['try', 'your last try'], ['demo', 'the demo'], ['video', 'the video']]) if (k(kind)) out.push(w);
    if (k('formula')) out.push(n(k('formula'), 'formula'));
    if (k('figure')) out.push(n(k('figure'), 'figure'));
    return out.length ? `Reads this page: ${out.length > 1 ? out.slice(0, -1).join(', ') + ' and ' + out[out.length - 1] : out[0]}.` : 'Reads this page.';
  }
  // The picture of a figure goes to the vision model only when the question is about it: the learner showed it with the pointer,
  // or the question names a figure, or a word of its caption. The name of the idea (the title) is not a word of the figure: a walk
  // figure with no caption has the alt "A figure for <idea>", and each question on the page names the idea.
  // A figure that this page load already read sends nothing.
  const FIG_WORDS = /\b(figure|fig|picture|image|diagram|plot|graph|chart|drawing|label|labels|axis|axes|curve)\b/i;
  function aboutFigure(said, ctx, img) {
    const a = ctx.anchors.find(x => x.id === 'figure');
    if (!a || !img) return false;
    if (figs[img.src] || (ctx.focus || []).some(f => f.anchors.includes('figure')) || FIG_WORDS.test(said)) return true;
    const idea = new Set(flatWords((ctx.anchors.find(x => x.id === 'title') || {}).text)), words = new Set(flatWords(a.text).filter(w => !idea.has(w)));
    return flatWords(said).some(w => words.has(w));
  }
  const flatWords = t => String(t || '').toLowerCase().split(/[^a-z0-9]+/).filter(w => w.length >= 4);

  // Ask the tutor: read the page, post the question with it, and play the board that comes back. A sure tutor sends each step
  // when it is whole: the first step starts a streaming board, and each next step goes to abhyasaBoard.add. The board event at
  // the end is the whole board: it finishes the streaming board, or plays as it is when no step came. The times go into
  // `abhyasaGuideLast`: from the press of Explain to the first step, to the board, and to the first mark.
  let asks = 0, ctl = null, busy = 0, drew = false;   // a newer question takes the place of an older one: its request stops, and its steps go nowhere
  const STOPPED = 'Stopped. The tutor got the question, but the guide shows no answer.';
  const status = e => window.abhyasaBoard && abhyasaBoard.status ? abhyasaBoard.status(e) : say(e.wait);
  const drawing = () => status({wait: 'Draws over the page.', state: 'drawing', where: HERE});   // the page sets this state: the server never sends it
  function halt() {   // Stop or Esc while the guide works: the request ends, so the server closes the model stream
    if (!busy || !ctl) return false;
    ctl.abort(); busy = 0;
    if (!drew) say(STOPPED);   // no step showed yet
    return true;
  }
  document.addEventListener('board:stop', e => { if (e.detail && e.detail.by === 'learner') halt(); });
  // Esc while the box is open closes it, and Esc while the state line shows stops the guide, before a board draws. It runs in the
  // capture phase of the document, before the Esc of core.js, which goes up one level: the learner stays on the page.
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape' || (window.abhyasaBoard && abhyasaBoard.state)) return;
    if (busy) halt(); else if (form() && !form().hidden) close(); else return;
    e.preventDefault(); e.stopImmediatePropagation();
  }, {capture: true});
  const voiceOn = () => info.voice !== false && !window.abhyasaGuideQuiet;

  // --- the natural voice -----------------------------------------------------------------------------------------------
  // When the setting voice.out is not `browser`, the server says each line (info.say, `/guide/say`): a WAV and the start time of
  // each word. The page plays it and lights each word at its time. Each step asks for its line as soon as it comes, so line 2 is
  // ready when line 1 ends. When the route fails, the board speaks with the browser voice, and the strip says so one time.
  const natural = () => !!(info.say && info.out && info.out.engine && info.out.engine !== 'browser');
  const lines = new Map();   // the text of a line -> the promise of its audio, for this page load
  function line(text) {
    if (!lines.has(text)) {
      const p = fetch(info.say, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text})}).then(async r => {
        const d = await r.json().catch(() => ({}));
        if (!r.ok || !d.audio) throw new Error(d.error || 'The natural voice did not answer.');
        return d;
      });
      p.catch(() => lines.delete(text));   // a failed line is asked again the next time
      lines.set(text, p);
      while (lines.size > 40) lines.delete(lines.keys().next().value);
    }
    return lines.get(text);
  }
  let fellBack = false;
  function browserVoice(text, onWord, done, why) {
    if (!fellBack && window.abhyasaBoard) {
      fellBack = true;
      console.warn('guide: natural voice', why);
      abhyasaBoard.notice({text: 'The natural voice did not answer. The browser voice reads the steps now.', href: '/settings#g-voice', link: 'Settings'});
    }
    return window.abhyasaBoard && abhyasaBoard.speakBrowser(text, onWord, done);
  }
  function speakNatural(text, onWord, done) {   // the host speak of board.js: see its API
    let audio = null, url = null, tick = 0, stopped = false, hush = null;
    const clean = () => { clearInterval(tick); if (audio) { audio.pause(); audio.removeAttribute('src'); } if (url) URL.revokeObjectURL(url); audio = url = null; };
    const fail = why => { if (stopped) return; clean(); hush = browserVoice(text, onWord, done, why); };
    line(text).then(d => {
      if (stopped) return;
      const bytes = Uint8Array.from(atob(d.audio), c => c.charCodeAt(0)), words = d.words || [];
      url = URL.createObjectURL(new Blob([bytes], {type: 'audio/wav'}));
      audio = new Audio(url);
      let k = 0;
      const mark = () => { while (audio && k < words.length && words[k] <= audio.currentTime + .02) onWord(k++); };
      audio.addEventListener('playing', () => { clearInterval(tick); tick = setInterval(mark, 40); mark(); });
      audio.addEventListener('ended', () => { while (k < words.length) onWord(k++); clean(); done(); });
      audio.addEventListener('error', () => fail('the audio did not play'));
      const r = audio.play();
      if (r && r.catch) r.catch(e => fail(e && e.message));
    }).catch(e => fail(e && e.message));
    return () => { stopped = true; clean(); if (typeof hush === 'function') hush(); };
  }
  function voiceOffer() {   // the first board with the browser voice says one time that a natural voice can read the steps
    if (natural() || !voiceOn() || localStorage.getItem('guide-voice-offered')) return null;
    localStorage.setItem('guide-voice-offered', '1');
    return {text: 'A natural voice can read the steps, on this Mac. It is a download of 225 MB.', href: '/settings#g-voice', link: 'Get it in Settings'};
  }
  function setVoice(on) {
    info.voice = on;
    if (me.voice) fetch(me.voice, {method: 'POST', body: new URLSearchParams({on: on ? '1' : '0'})}).catch(() => {});
  }
  function hintLine(text) {   // the open check says that the board counted as a hint on it
    const c = document.getElementById('check');
    if (!c || !text) return;
    let p = c.querySelector('.guide-hint-used');
    if (!p) { p = Object.assign(document.createElement('p'), {className: 'guide-hint-used mute'}); (c.querySelector('form') || c).prepend(p); }
    p.textContent = text;
  }
  // "Show me …" to the guide: Show. On an idea page the card fills the Show slot of the idea (#show-slot); on any other page it
  // comes in the side panel at the top right, where the board builds its example. With no idea for the page, the panel links to the Library.
  function showDemo(sh, said) {
    if (window.abhyasaBoard) abhyasaBoard.stop();
    const old = document.getElementById('guide-show'); if (old) old.remove();
    const slot = document.getElementById('show-slot'), html = typeof sh.html === 'string' && sh.html;
    if (html && slot) {   // the card of the demo block, from this app: htmx runs its wait and its scripts
      if (window.htmx) htmx.swap(slot, html, {swapStyle: 'innerHTML'}); else slot.innerHTML = html;
      slot.scrollIntoView({block: 'nearest', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
      return;
    }
    const c = Object.assign(document.createElement('aside'), {id: 'guide-show', className: 'guide-show'});
    c.setAttribute('aria-label', 'Show: a demo from the guide');
    const head = Object.assign(document.createElement('p'), {className: 'guide-show-head mute', textContent: `Show: ${cut(said, 80)} `});
    const x = Object.assign(document.createElement('button'), {type: 'button', className: 'guide-show-close', textContent: '×', title: 'Close the demo'});
    x.setAttribute('aria-label', 'Close the demo'); x.addEventListener('click', () => c.remove());
    const body = Object.assign(document.createElement('div'), {className: 'guide-show-body'});
    head.append(x); c.append(head, body); document.body.append(c);
    if (html) { if (window.htmx) htmx.swap(body, html, {swapStyle: 'innerHTML'}); else body.innerHTML = html; }
    else if (/^\/(?!\/)/.test(String(sh.href || ''))) {
      const p = Object.assign(document.createElement('p'), {className: 'mute', textContent: sh.find ? 'This page names no idea of yours yet. ' : ''});
      p.append(Object.assign(document.createElement('a'), {href: sh.href, textContent: sh.find ? 'Find it in your library' : `Open the demo of ${cut(sh.title || 'this idea', 60)}`}));
      body.append(p);
    }
  }
  document.addEventListener('keydown', e => {   // Esc closes the demo card when no board shows and the box is closed
    const c = document.getElementById('guide-show');
    if (e.key !== 'Escape' || !c || (window.abhyasaBoard && abhyasaBoard.state) || (form() && !form().hidden) || busy) return;
    c.remove(); e.preventDefault(); e.stopImmediatePropagation();
  }, {capture: true});

  async function ask(said) {
    said = cut(said, 300);
    if (!said) return;
    const shown = stopShow();   // what the learner showed with the pointer while they asked
    close();
    const t0 = performance.now(), last = window.abhyasaGuideLast = {said, t0}, n = ++asks, page = pageKey();
    const offer = voiceOffer();
    const opts = () => ({labels, quiet: !voiceOn(), who: asked, onVoice: setVoice, point: info.point, ...(natural() && {host: {speak: speakNatural}, voiceAt: info.out}), ...(offer && {notice: offer})}), mark = () => document.addEventListener('board:first', () => { last.first_ms = Math.round(performance.now() - t0); }, {once: true});
    let labels = {}, live = null, whole = false, asked = info.model || null, saved = null;   // live: the promise of the streaming board, with each add after it
    const got = [];   // the steps that came, for a stream that ends with no board event
    if (ctl) ctl.abort();
    const me_ = ctl = new AbortController(); busy = n; drew = false;
    if (window.abhyasaBoard && abhyasaBoard.state) abhyasaBoard.stop();   // the board of the older question goes
    try {
      const ctx = await capture();
      const focus = focusFor(shown, ctx);
      if (focus.length) ctx.focus = last.focus = focus;
      last.capture_ms = Math.round(performance.now() - t0);
      status({wait: readLine(ctx), state: 'reading', where: HERE});
      const img = ctx.anchors.some(a => a.id === 'figure') && document.querySelector('[data-guide-id="figure"]');
      if (aboutFigure(said, ctx, img)) {   // the picture leaves the page only now, and the line says where it goes
        const v = info.vision || {};
        if (!figs[img.src]) status({wait: `Sends the picture of this figure to ${v.model || 'the tutor'} to find its labels. abhyasa does not keep the picture.`, state: 'asking', ...v});
        ctx.anchors.find(a => a.id === 'figure').labels = await labelsOf(img);
        if (n !== asks) return;
      }
      labels = Object.fromEntries(ctx.anchors.filter(a => a.labels).map(a => [a.id, a.labels]));
      const th = turns().map(t => ({...t}));   // the last questions on this page go too, and the server's line says so
      if (th.length) thread.at = Date.now();
      const r = await fetch(me.ask, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({said, ctx, ...(th.length && {thread: th})}), signal: me_.signal});
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
          if (m.wait) { if (m.state === 'asking' && m.model) asked = {model: m.model, where: m.where, who: m.who}; status(m); }
          if (m.saved) saved = m.saved;
          if (m.error) say(m.error);
          if (m.show) { busy = 0; showDemo(m.show, said); }
          if (m.step) got.push(m.step);
          if (natural() && voiceOn()) for (const s of m.step ? [m.step] : m.board ? m.board.steps || [] : []) if (s && s.say) line(s.say).catch(() => {});   // each line before it is needed
          if (m.step && !live) {
            last.step_ms = Math.round(performance.now() - t0); mark(); drew = true; drawing();
            live = abhyasaBoard.play({steps: [m.step], tier: m.tier || 'tutor', sources: [], streaming: true}, opts());
          } else if (m.step) live = live.then(() => n === asks && abhyasaBoard.add(m.step));
          if (m.board) {
            whole = true; busy = 0; keep(said, m.board, page);
            if (saved) m.board.saved = saved;
            hintLine(m.board.hint);
            last.board_ms = Math.round(performance.now() - t0); last.server_ms = m.board.ms; last.tier = m.board.tier;
            if (!live) { mark(); drew = true; drawing(); await abhyasaBoard.play(m.board, opts()); }
            else {
              await live;
              const b = abhyasaBoard.state;   // null when the learner stopped the board
              if (n === asks && b && b.streaming && !abhyasaBoard.finish(m.board)) await abhyasaBoard.play(m.board, opts());
            }
          }
        }
      }
      if (live && !whole && n === asks) {   // the stream ended after steps, with no board: end the board with the steps that came
        keep(said, {steps: got, tier: 'tutor'}, page);
        await live;
        if (n === asks && abhyasaBoard.state && abhyasaBoard.state.streaming) abhyasaBoard.finish({steps: got, tier: 'tutor', sources: [], end: ''});
      }
    } catch (e) { if (e.name !== 'AbortError') say('The tutor could not answer. Make sure that abhyasa is open, then try again.'); }
    finally { if (busy === n) busy = 0; }
  }

  // --- Hyper+E: hold to talk, tap to type ----------------------------------------------------------------------------
  // Hyper is ⌃⌥⇧⌘ (Caps Lock with a key remapper). A hold of HOLD ms or more starts the mic of the voice block into the box;
  // the release stops it, and the words stay in the box when the last of them is in: the learner can change them, and Enter sends. A tap opens the box. macOS sends no
  // keyup for E while ⌘ is down, so the keyup of any of the four modifiers is a release too.
  const HOLD = 300;
  let held = null, mic = null;
  function micButton() {
    const tpl = document.getElementById('mic-float');
    if (!tpl) return null;
    if (!mic || !mic.isConnected) {
      mic = Object.assign(document.createElement('button'), {type: 'button', id: 'guide-mic', className: 'mic mini', hidden: true, title: 'The mic is on'});
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
    if (!b || !window.abhyasaMic) { heard('abhyasa cannot use the mic. Type your question.'); return; }
    heard(`The mic is on. Let go of Caps+E to stop. Speech: ${where(info.speech) || HERE}.`);
    b.hidden = false;   // its dot and level show while you talk
    abhyasaMic(b);
  }
  async function endTalk() {
    const b = micButton();
    if (!b || !window.abhyasaDict || abhyasaDict.btn !== b) return;
    const sp = info.speech || {};
    heard(`${sp.model || 'The speech engine'} writes your words (${where(sp) || HERE}).`);
    await abhyasaMic(b);   // the second press stops it; the last words still come in
    const end = performance.now() + 15000;
    while (performance.now() < end && (b.classList.contains('busy') || b.classList.contains('on'))) await new Promise(ok => setTimeout(ok, 100));
    b.hidden = true;
    const x = box();   // the transcript stays in the box, so the learner can change it; Enter sends, Esc closes
    if (!x.value.trim()) return heard('The mic heard nothing. Type your question.');
    heard(EDIT);
    x.focus(); x.setSelectionRange(x.value.length, x.value.length);   // the learner just spoke into the box: not a focus steal
  }
  const EDIT = 'Change the words if you need to. Return sends them.';
  document.addEventListener('keydown', e => {   // ⌘↩ sends too (a plain ↩ submits the form)
    if (e.key === 'Enter' && e.metaKey && e.target === box() && !form().hidden) { e.preventDefault(); ask(box().value); }
  });
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

  document.addEventListener('click', e => { if (e.target.closest && e.target.closest('#guide-go, [data-guide-open]')) { e.preventDefault(); open(); } });   // Explain in the top bar, or in the row of a check
  document.addEventListener('click', e => {   // Start fresh: the next question has no thread; the box keeps the focus
    if (!(e.target.closest && e.target.closest('#guide-form .guide-fresh'))) return;
    e.preventDefault(); fresh(); if (box()) box().focus();
  });
  document.addEventListener('click', e => {   // a time in the transcript seeks the video on the page; a click with a modifier opens YouTube
    const a = e.target.closest && e.target.closest('#guide-video a[data-t]');
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || !window.abhyasaBoard || !abhyasaBoard.seekVideo) return;
    e.preventDefault(); abhyasaBoard.seekVideo(+a.dataset.t);
  });
  document.addEventListener('submit', e => { if (e.target.id === 'guide-form') { e.preventDefault(); ask(box().value); } });

  window.abhyasaGuide = {capture, texParts: (...a) => abhyasaTex.texParts(...a), labelsOf, ask, open, gestures, focusOf, G, readLine, aboutFigure, halt, speakNatural, info,
                        thread: () => turns().map(t => ({...t, says: [...t.says]})), fresh};
})();
