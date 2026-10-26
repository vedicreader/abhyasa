// The concept graph on one canvas. d3-force moves the nodes in the Free and Groups layouts; Path and Rings put each node
// at a fixed place. d3-zoom moves the camera. One frame loop draws, and only when something changed.
// The levers in #levers (made by ui.py) change the layout, the look and what shows. The levers, the positions that you
// drag and the camera stay in localStorage, so the graph looks the same when you come back.
(async () => {
  const root = document.getElementById('graph'); if (!root) return;
  const cv = root.querySelector('canvas'), ctx = cv.getContext('2d'), tip = root.querySelector('.tip');
  const panel = root.querySelector('#levers'), note = root.querySelector('.note'), stage = root.querySelector('.stage');
  const KEY = 'abhyasa.graph.v1', DEPTHS = ['unseen', 'recognise', 'recall', 'explain', 'apply', 'transfer'];
  const STATIC = new Set(['path', 'rings']), DAY = 86400;
  const g = await (await fetch(root.dataset.url)).json();
  note.remove();
  if (!g.nodes.length) { stage.append(Object.assign(document.createElement('p'), {className: 'hint note', textContent: 'No concepts yet.'})); return; }

  // ---- the levers and what is saved -------------------------------------------------------------------------------
  const DEF = {mode: 'force', spacing: 50, link: 50, push: 50, size: 50, sizeBy: 'seen', colorBy: 'floor', labels: 'all',
               floorLo: 0, floorHi: 5, dueOnly: false, hideUnseen: false, related: true, steps: 1, frozen: false, subs: {}};
  let store; try { store = JSON.parse(localStorage.getItem(KEY)) || {}; } catch { store = {}; }
  store.pos ||= {}; store.pins ||= {}; store.cam ||= {};
  const S = {...DEF, ...store.set, subs: {...(store.set || {}).subs}};
  let saveT; const save = () => { clearTimeout(saveT); saveT = setTimeout(() => {
    store.set = S; try { localStorage.setItem(KEY, JSON.stringify(store)); } catch {} }, 300); };
  const logv = (p, lo, hi) => lo * Math.exp(p / 100 * Math.log(hi / lo));   // 0..100 to lo..hi, the default (50) in the middle
  const sp = () => logv(S.spacing, .5, 2), sz = () => logv(S.size, .5, 2);
  const linkLen = () => logv(S.link, 15, 135), charge = () => -logv(S.push, 30, 480);

  // ---- the data ---------------------------------------------------------------------------------------------------
  const now = Date.now() / 1000, nodes = g.nodes, byId = new Map(nodes.map(n => [n.id, n]));
  const links = g.links.map(l => ({kind: l.kind === 'gap' ? 'prereq' : l.kind, s: byId.get(l.source), t: byId.get(l.target)})).filter(l => l.s && l.t).map(l => ({...l, source: l.s, target: l.t}));
  const subjects = [...new Set(nodes.map(n => n.subject || 'general'))];
  nodes.forEach(n => { n.subject ||= 'general'; n.days = n.seen && n.due ? (n.due - now) / DAY : null; n.nb = new Set(); });
  links.forEach(l => { l.s.nb.add(l.t); l.t.nb.add(l.s); });
  const isDue = n => n.days !== null && n.days <= 0, learned = n => n.floor > 0 || n.seen > 0;
  const dueness = n => n.days === null ? 0 : n.days <= 0 ? 1 : Math.max(0, 1 - n.days / 14);
  if (root.dataset.subject && subjects.includes(root.dataset.subject)) subjects.forEach(s => S.subs[s] = s === root.dataset.subject);

  // ---- the colours, from the theme --------------------------------------------------------------------------------
  let C = {};
  const probe = root.appendChild(document.createElement('i'));
  const v = name => { probe.style.color = `var(${name})`; return getComputedStyle(probe).color; };
  const themed = () => {
    C = {bg: v('--bg'), fg: v('--fg'), mute: v('--mute'), rule: v('--rule'), line: v('--line'), acc: v('--acc'), no: v('--no'), ok: v('--ok'),
         subs: [1, 2, 3, 4, 5, 6].map(i => v(`--g${i}`)), serif: getComputedStyle(root).getPropertyValue('--serif')};
    C.dark = d3.hsl(C.bg).l < .5;   // the theme and the mode are on <html>, so the page bg says which
    C.floor = d3.interpolateRgb(d3.interpolateRgb(C.bg, C.acc)(.4), C.acc);
    C.due = d3.interpolateRgb(C.no, C.ok);
    C.state = {strong: C.ok, learning: C.floor(.3), fading: C.due(.5), weak: C.no, gap: C.acc};
  };
  themed();
  const subCol = s => C.subs[subjects.indexOf(s) % C.subs.length];
  const fill = n => S.colorBy === 'subject' ? subCol(n.subject)
    : S.colorBy === 'understanding' ? (C.state[n.state] || C.bg)
    : S.colorBy === 'due' ? (n.days === null ? C.bg : C.due(Math.min(1, Math.max(0, n.days / 14))))
    : n.floor ? C.floor((n.floor - 1) / 4) : C.bg;
  const hollow = n => S.colorBy === 'subject' ? false : S.colorBy === 'understanding' ? !C.state[n.state] : S.colorBy === 'due' ? n.days === null : !n.floor;
  const rad = n => sz() * (4.5 + (S.sizeBy === 'seen' ? 1.6 * Math.sqrt(Math.min(n.seen, 16))
    : S.sizeBy === 'due' ? 6 * dueness(n) : S.sizeBy === 'depth' ? 1.6 * Math.min(n.depth || 0, 6) : 1));

  // ---- what shows -------------------------------------------------------------------------------------------------
  let focus = null, picked = root.dataset.focus && byId.get(root.dataset.focus) || null, hover = null, hits = null;
  let vis = [], visLinks = [], visSet = new Set();
  const passes = n => S.subs[n.subject] !== false && n.floor >= S.floorLo && n.floor <= S.floorHi &&
                      (!S.dueOnly || isDue(n)) && (!S.hideUnseen || n.seen > 0);
  const near = () => {   // the focus concept and the concepts within `steps` links of it
    const seen = new Set([focus]); let edge = [focus];
    for (let i = 0; i < S.steps; i++) edge = edge.flatMap(n => [...n.nb].filter(m => !seen.has(m) && (S.related || linkKind(n, m) === 'prereq') && seen.add(m)));
    return seen;
  };
  const kinds = new Map(links.map(l => [l.s.id + '>' + l.t.id, l.kind]));
  const linkKind = (a, b) => kinds.get(a.id + '>' + b.id) || kinds.get(b.id + '>' + a.id);
  const filter = () => {
    const f = focus && near();
    vis = nodes.filter(n => passes(n) && (!f || f.has(n)) || n === focus);
    visSet = new Set(vis);
    visLinks = links.filter(l => visSet.has(l.s) && visSet.has(l.t) && (S.related || l.kind === 'prereq'));
    depths();
  };
  const depths = () => {   // the longest chain of prereqs before each concept; a cycle does not loop
    const pre = new Map(vis.map(n => [n, []])), indeg = new Map(vis.map(n => [n, 0]));
    visLinks.forEach(l => { if (l.kind === 'prereq') { pre.get(l.t).push(l.s); indeg.set(l.t, indeg.get(l.t) + 1); } });
    const out = new Map(vis.map(n => [n, []])); visLinks.forEach(l => l.kind === 'prereq' && out.get(l.s).push(l.t));
    vis.forEach(n => { n.depth = 0; n.linked = pre.get(n).length > 0 || out.get(n).length > 0; });
    let q = vis.filter(n => !indeg.get(n));
    while (q.length) { const n = q.pop(); for (const m of out.get(n)) { m.depth = Math.max(m.depth, n.depth + 1); indeg.set(m, indeg.get(m) - 1); if (!indeg.get(m)) q.push(m); } }
  };

  // ---- the layouts ------------------------------------------------------------------------------------------------
  let captions = [];   // [x, y, text, kind] in world units, drawn at a fixed screen size
  const pinned = () => new Set(store.pins[S.mode] || []);
  const sim = d3.forceSimulation().stop().on('tick', dirty).on('end', keep);
  const forces = () => {
    const groups = S.mode === 'groups', k = sp(), centre = groupCentres();
    sim.nodes(vis).velocityDecay(.4)
      .force('link', d3.forceLink(visLinks).distance(l => linkLen() * (l.kind === 'related' ? 1.3 : 1)).strength(l => (l.kind === 'related' ? .3 : .7) * (groups && l.s.subject !== l.t.subject ? .15 : 1) / Math.min(l.s.nb.size, l.t.nb.size)))
      .force('charge', d3.forceManyBody().strength(charge() * (groups ? .6 : 1)).distanceMax(500 * k))
      .force('x', d3.forceX(n => groups ? centre.get(n.subject)[0] : 0).strength(groups ? .14 : .05))
      .force('y', d3.forceY(n => groups ? centre.get(n.subject)[1] : 0).strength(groups ? .14 : .05))
      .force('collide', d3.forceCollide(n => rad(n) + 3 * k));
    const pins = pinned(); vis.forEach(n => { n.fx = n.fy = null; if (pins.has(n.id) && store.pos[S.mode]?.[n.id]) [n.fx, n.fy] = store.pos[S.mode][n.id]; });
  };
  const groupCentres = () => {   // the subjects on a circle, far enough apart for their sizes
    const subs = subjects.filter(s => vis.some(n => n.subject === s)), size = s => Math.sqrt(vis.filter(n => n.subject === s).length);
    const R = subs.length < 2 ? 0 : d3.sum(subs, size) * 24 * sp() / Math.PI;
    return new Map(subs.map((s, i) => [s, [R * Math.cos(2 * Math.PI * i / subs.length - Math.PI / 2), R * Math.sin(2 * Math.PI * i / subs.length - Math.PI / 2)]]));
  };
  const pathTargets = () => {   // a block for each subject: one column for each step of prereqs, then a grid of the rest
    const k = sp(), col = 190 * k, row = 26 * k, aspect = (cv.clientWidth || 900) / (cv.clientHeight || 600), blocks = [];
    for (const s of subjects) {
      const ns = vis.filter(n => n.subject === s); if (!ns.length) continue;
      const T = new Map(), caps = [[-12, 0, s, 'band']], linked = ns.filter(n => n.linked), loose = ns.filter(n => !n.linked).sort((a, b) => a.name.localeCompare(b.name));
      let top = row * 1.4, wide = 0;
      if (linked.length) {
        const cols = d3.groups(linked, n => n.depth).sort((a, b) => a[0] - b[0]).map(([, c]) => c.sort((a, b) => a.name.localeCompare(b.name)));
        const at = new Map();
        cols.forEach((c, d) => {   // order each column by where its prereqs sit, so the lines cross less
          if (d) c.sort((a, b) => bary(a, at) - bary(b, at));
          c.forEach((n, i) => at.set(n, i - (c.length - 1) / 2));
        });
        // A long path wraps like a line of text: as many columns on a line as make the block about the shape of the screen.
        // When it wraps, the columns get wider for the long names of lessons, and the step heads go, as they no longer line up.
        const rows = d3.max(cols, c => c.length), cw = col * 2, fits = m => m * cw / (Math.ceil(cols.length / m) * (rows + 1) * row);
        const per = d3.least(d3.range(1, cols.length + 1), m => Math.abs(Math.log(fits(m) / aspect))), wrap = per < cols.length;
        const lineH = (rows + (wrap ? 1 : 1.6)) * row, step = wrap ? cw : col;
        cols.forEach((c, d) => {
          const x = (d % per) * step, y0 = top + Math.floor(d / per) * lineH;
          c.forEach(n => T.set(n, [x, y0 + row * (wrap ? .5 : .9) + (at.get(n) + (rows - 1) / 2) * row]));
          if (!wrap) caps.push([x - 6, y0, `step ${d + 1}`, 'col']);
        });
        wide = Math.ceil(per * step / col); top += Math.ceil(cols.length / per) * lineH + row * .5;
      }
      if (loose.length) {
        const n = Math.max(wide, 2, Math.round(Math.sqrt(loose.length * aspect * row / col)));
        caps.push([-6, top, 'no prereqs yet', 'col']); top += row * .9;
        loose.forEach((m, i) => T.set(m, [(i % n) * col, top + Math.floor(i / n) * row]));
        top += Math.ceil(loose.length / n) * row; wide = n;
      }
      blocks.push({T, caps, w: wide * col, h: top});
    }
    // Put the blocks in rows, as words on a page, with the number on a row that makes the whole about the shape of the screen.
    const gx = col * .6, gy = row * 3, pack = m => {
      let y = 0, W = 0; const at = [];
      for (let i = 0; i < blocks.length; i += m) {
        const line = blocks.slice(i, i + m); let x = 0;
        line.forEach(b => { at.push([x, y]); x += b.w + gx; });
        W = Math.max(W, x - gx); y += d3.max(line, b => b.h) + gy;
      }
      return {at, W, H: y - gy};
    };
    const best = d3.least(d3.range(1, blocks.length + 1).map(pack), p => Math.abs(Math.log(p.W / p.H / aspect)));
    const T = new Map(); captions = [];
    blocks.forEach((b, i) => { const [ox, oy] = best.at[i];
      b.T.forEach(([x, y], n) => T.set(n, [x + ox, y + oy])); b.caps.forEach(([x, y, t, kd]) => captions.push([x + ox, y + oy, t, kd])); });
    return T;
  };
  const bary = (n, at) => { const p = [...n.nb].filter(m => at.has(m) && linkKind(m, n) === 'prereq'); return p.length ? d3.mean(p, m => at.get(m)) : 0; };
  const ringTargets = () => {   // a slice for each subject, sized by its count; rings go out by prereq steps, then one band for the rest
    const T = new Map(), k = sp(), gap = 30 * k, slot = 24 * k, r0 = 90 * k, total = vis.length;
    const subs = subjects.filter(s => vis.some(n => n.subject === s)).map(s => ({s, ns: vis.filter(n => n.subject === s)}));
    let a0 = -Math.PI / 2, maxR = r0; captions = [];
    subs.forEach(o => { o.a0 = a0; o.wedge = 2 * Math.PI * o.ns.length / total; o.pad = subs.length > 1 ? Math.min(.12, o.wedge * .1) : 0; a0 += o.wedge; });
    const put = (o, grp, ring) => {   // fill rings from `ring` out, as many on each ring as there is room for; return the next free ring
      grp.sort((a, b) => a.name.localeCompare(b.name));
      for (let i = 0; i < grp.length; ring++) {
        const r = r0 + ring * gap, span = o.wedge - 2 * o.pad, cap = Math.max(1, Math.floor(span * r / slot)), part = grp.slice(i, i + cap);
        part.forEach((n, j) => { const a = o.a0 + o.pad + span * (part.length === 1 ? .5 : (j + .5) / part.length); T.set(n, [r * Math.cos(a), r * Math.sin(a)]); });
        i += cap; maxR = Math.max(maxR, r);
      }
      return ring;
    };
    let band = 0;
    for (const o of subs) { let ring = 0; for (const [, grp] of d3.groups(o.ns.filter(n => n.linked), n => n.depth).sort((a, b) => a[0] - b[0])) ring = put(o, grp, ring); band = Math.max(band, ring); }
    for (const o of subs) put(o, o.ns.filter(n => !n.linked), band ? band + 1 : 0);
    for (const o of subs) { const am = o.a0 + o.wedge / 2, r = maxR + gap * 2.2; captions.push([r * Math.cos(am), r * Math.sin(am), o.s, 'ring']); }
    return T;
  };

  // Move the nodes to `T` (node -> [x, y]) in a short glide; the nodes that you dragged stay where you put them.
  let tween = null;
  const glide = (T, ms = 650) => {
    const pins = pinned(), P = store.pos[S.mode] || {};
    vis.forEach(n => { if (pins.has(n.id) && P[n.id]) T.set(n, P[n.id]); if (!T.has(n)) T.set(n, [n.x ?? 0, n.y ?? 0]); if (STATIC.has(S.mode)) n.fx = n.fy = null; });
    tween = {t0: performance.now(), ms, from: new Map(vis.map(n => [n, [n.x ?? T.get(n)[0], n.y ?? T.get(n)[1]]])), to: T};
    dirty();
  };
  const glideStep = ts => {
    const p = Math.min(1, (ts - tween.t0) / tween.ms), e = d3.easeCubicInOut(p);
    tween.to.forEach(([x, y], n) => { const [x0, y0] = tween.from.get(n); n.x = x0 + (x - x0) * e; n.y = y0 + (y - y0) * e; });
    if (p >= 1) tween = null;
    return !!tween;
  };
  const layout = ({fresh = false, fit: f = false} = {}) => {   // put the visible nodes in place for the current mode
    sim.stop(); filter();
    if (STATIC.has(S.mode)) { glide(S.mode === 'path' ? pathTargets() : ringTargets()); }
    else {
      captions = [];
      const P = store.pos[S.mode], cold = fresh || vis.some(n => n.x === undefined);
      forces();
      if (P && !fresh && vis.every(n => P[n.id])) glide(new Map(vis.map(n => [n, P[n.id]])));
      else {
        vis.forEach(n => { if (P?.[n.id] && !fresh) [n.x, n.y] = P[n.id]; else if (n.x === undefined) seed(n); });
        if (cold) { sim.alpha(1); for (let i = 0; i < 240; i++) sim.tick(); }   // settle before the first frame, so nothing flies about
        if (!S.frozen) sim.alpha(cold ? .06 : .5).restart(); else keep();
      }
    }
    panel.querySelector('[name=freeze]').disabled = STATIC.has(S.mode);
    if (f && !tween && sim.alpha() > .1 && !S.frozen) fitLater = true;   // fit when the nodes stop moving
    else if (f) setTimeout(fit, tween ? tween.ms * .4 : 0);
    dirty();
  };
  const seed = n => {   // a new node starts next to a neighbour that has a place, or at a random place near the middle
    const m = [...n.nb].find(m => m.x !== undefined), a = Math.random() * 2 * Math.PI, r = m ? 20 : 120 * Math.random();
    n.x = (m ? m.x : 0) + r * Math.cos(a); n.y = (m ? m.y : 0) + r * Math.sin(a);
  };
  let fitLater = false;
  function keep() {   // save the positions of the force layouts after they stop moving
    if (fitLater) { fitLater = false; fit(); }
    if (STATIC.has(S.mode)) return;
    const P = store.pos[S.mode] ||= {}; vis.forEach(n => P[n.id] = [Math.round(n.x * 10) / 10, Math.round(n.y * 10) / 10]); save();
  }

  // ---- the camera -------------------------------------------------------------------------------------------------
  let t = d3.zoomIdentity, W = 0, H = 0, dpr = 1;
  const zoom = d3.zoom().scaleExtent([.08, 6]).on('zoom', e => { t = e.transform; hideTip(); dirty(); })
    .on('end', () => { store.cam[S.mode] = {k: t.k, x: t.x, y: t.y}; save(); });
  const sel = d3.select(cv);
  const box = () => {
    const T = tween ? [...tween.to.values()] : vis.map(n => [n.x, n.y]);
    if (!T.length) return [[-1, -1], [1, 1]];
    if (STATIC.has(S.mode)) captions.forEach(c => T.push([c[0], c[1]]));   // the subject names must show too
    return [[d3.min(T, p => p[0]), d3.min(T, p => p[1])], [d3.max(T, p => p[0]), d3.max(T, p => p[1])]];
  };
  function fit(ms = 450) {
    // room in screen pixels: 150 on the right for the labels, 30 at the other edges
    const [[x0, y0], [x1, y1]] = box(), k = Math.min(2.2, (W - 180) / Math.max(1, x1 - x0), (H - 60) / Math.max(1, y1 - y0));
    sel.transition().duration(ms).call(zoom.transform, d3.zoomIdentity.translate(30 - k * x0 + (W - 180 - k * (x1 - x0)) / 2, H / 2).scale(k).translate(0, -(y0 + y1) / 2));
  }
  const centre = n => { const [x, y] = tween?.to.get(n) || [n.x, n.y], k = Math.max(t.k, 1.4);
    sel.transition().duration(500).call(zoom.transform, d3.zoomIdentity.translate(W / 2, H / 2).scale(k).translate(-x, -y)); };
  const resize = () => {
    const r = stage.getBoundingClientRect(); dpr = window.devicePixelRatio || 1; W = r.width; H = r.height;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); cv.style.width = W + 'px'; cv.style.height = H + 'px'; dirty();
  };

  // ---- drawing ----------------------------------------------------------------------------------------------------
  let raf = 0; const stats = {frames: 0, draw: 0, max: 0, sum: 0};
  function dirty() { if (!raf) raf = requestAnimationFrame(frame); }
  function frame(ts) { raf = 0; const more = tween && glideStep(ts); draw(); if (more) dirty(); }
  const region = document.createElement('canvas'), rctx = region.getContext('2d'), soft = document.createElement('canvas'), sctx = soft.getContext('2d');
  const widths = new Map(); const width = n => widths.get(n) ?? (widths.set(n, ctx.measureText(n.name).width), widths.get(n));
  const lit = () => {   // the nodes in full colour: what you point at and its neighbours, or what you find; null for all
    if (hover) return new Set([hover, ...[...hover.nb].filter(m => visSet.has(m))]);
    return hits;
  };
  function draw() {
    const t0 = performance.now(), L = lit(), k = t.k;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
    if (S.mode === 'groups') regions();
    ctx.save(); ctx.translate(t.x, t.y); ctx.scale(k, k);
    // the links: prereqs are lines with an arrow, related links are dashes
    const curve = S.mode === 'path';
    for (const [kind, on] of [['related', false], ['prereq', false], ['related', true], ['prereq', true]]) {
      const ls = visLinks.filter(l => l.kind === kind && (!!L && L.has(l.s) && L.has(l.t) && (!hover || l.s === hover || l.t === hover)) === on);
      if (!ls.length) continue;
      ctx.beginPath();
      for (const l of ls) { ctx.moveTo(l.s.x, l.s.y); if (curve) { const mx = (l.s.x + l.t.x) / 2; ctx.bezierCurveTo(mx, l.s.y, mx, l.t.y, l.t.x, l.t.y); } else ctx.lineTo(l.t.x, l.t.y); }
      ctx.setLineDash(kind === 'related' ? [3 / k, 3 / k] : []);
      ctx.strokeStyle = on ? C.acc : kind === 'prereq' ? C.mute : C.rule;
      ctx.globalAlpha = on ? 1 : L ? .15 : kind === 'prereq' ? .6 : 1;
      ctx.lineWidth = (on ? 1.6 : 1) / k; ctx.stroke();
      if (kind === 'prereq') {   // the arrow heads, at the edge of the later concept
        ctx.beginPath(); const a = 7 / k;
        for (const l of ls) {
          const ang = curve ? Math.atan2(0, l.t.x - l.s.x) : Math.atan2(l.t.y - l.s.y, l.t.x - l.s.x), r = rad(l.t) + 1.5 / k;
          const x = l.t.x - r * Math.cos(ang), y = l.t.y - r * Math.sin(ang);
          ctx.moveTo(x, y); ctx.lineTo(x - a * Math.cos(ang - .4), y - a * Math.sin(ang - .4)); ctx.lineTo(x - a * Math.cos(ang + .4), y - a * Math.sin(ang + .4)); ctx.closePath();
        }
        ctx.fillStyle = on ? C.acc : C.mute; ctx.fill();
      }
    }
    ctx.setLineDash([]); ctx.globalAlpha = 1;
    // the nodes: the fill shows the colour lever, a red ring shows a review that is due, a dot shows a node you put in place
    const pins = pinned();
    for (const n of vis) {
      const r = rad(n), dim = L && !L.has(n);
      ctx.globalAlpha = dim ? .2 : 1;
      ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 2 * Math.PI); ctx.fillStyle = fill(n); ctx.fill();
      const due = isDue(n) && S.colorBy !== 'due';
      ctx.lineWidth = (due ? 2.2 : n === picked ? 2.4 : 1) / k;
      ctx.strokeStyle = n === picked ? C.fg : due ? C.no : hollow(n) ? C.mute : C.bg; ctx.stroke();
      if (n === picked) { ctx.beginPath(); ctx.arc(n.x, n.y, r + 4 / k, 0, 2 * Math.PI); ctx.strokeStyle = C.acc; ctx.lineWidth = 1.5 / k; ctx.stroke(); }
      if (pins.has(n.id)) { ctx.beginPath(); ctx.arc(n.x, n.y, Math.min(r * .35, 2.2 / k + r * .1), 0, 2 * Math.PI); ctx.fillStyle = hollow(n) ? C.mute : C.bg; ctx.fill(); }
    }
    ctx.globalAlpha = 1; ctx.restore();
    labels(L);
    const d = performance.now() - t0; stats.frames++; stats.draw = d; stats.sum += d; stats.max = Math.max(stats.max, d);
  }
  function regions() {   // a soft tint under each subject in the Groups layout; one colour does not add up where it overlaps
    const q = 4, w = Math.ceil(W / q), h = Math.ceil(H / q);
    if (region.width !== w || region.height !== h) { region.width = soft.width = w; region.height = soft.height = h; }
    rctx.setTransform(1, 0, 0, 1, 0, 0); rctx.clearRect(0, 0, w, h);
    rctx.setTransform(t.k / q, 0, 0, t.k / q, t.x / q, t.y / q);
    const R = 30 * sp();
    for (const n of vis) { rctx.beginPath(); rctx.arc(n.x, n.y, R, 0, 2 * Math.PI); rctx.fillStyle = subCol(n.subject); rctx.fill(); }
    // blur at a quarter of the size, where it costs little, then scale it up; the scale-up smooths it too
    sctx.clearRect(0, 0, w, h); sctx.filter = `blur(${Math.max(1, 2.5 * t.k)}px)`; sctx.drawImage(region, 0, 0); sctx.filter = 'none';
    ctx.save(); ctx.globalAlpha = C.dark ? .16 : .12; ctx.imageSmoothingEnabled = true; ctx.drawImage(soft, 0, 0, w * q, h * q); ctx.restore();
    const groups = d3.groups(vis, n => n.subject);
    captions = groups.map(([s, ns]) => [d3.mean(ns, n => n.x), d3.min(ns, n => n.y) - R * .9, s, 'group']);
  }
  function labels(L) {   // labels at a fixed screen size; a label that would cover another one is left out
    const want = S.labels, k = t.k, cell = 40, grid = new Map(), placed = [];
    ctx.font = '12px ' + C.serif; ctx.textBaseline = 'middle';
    const rank = n => (S.mode === 'path' && n.linked ? 1e4 : 0) + (n === picked ? 1e6 : 0) + (n === hover ? 2e6 : 0) + (hits?.has(n) ? 5e5 : 0) + (L?.has(n) ? 1e5 : 0) + n.floor * 100 + Math.min(n.seen, 50) + n.nb.size * 3;
    const cand = vis.filter(n => n === picked || n === hover || (L ? L.has(n) : want === 'all' || (want === 'learned' && learned(n)) || n === focus))
      .filter(n => want !== 'hover' || L || n === picked || n === focus || n === hover).sort((a, b) => rank(b) - rank(a));
    const hit = (x0, y0, x1, y1) => {
      for (let i = Math.floor(x0 / cell); i <= Math.floor(x1 / cell); i++) for (let j = Math.floor(y0 / cell); j <= Math.floor(y1 / cell); j++)
        for (const b of grid.get(i * 1e5 + j) || []) if (b[0] < x1 && b[2] > x0 && b[1] < y1 && b[3] > y0) return true;
      return false;
    };
    const add = b => { for (let i = Math.floor(b[0] / cell); i <= Math.floor(b[2] / cell); i++) for (let j = Math.floor(b[1] / cell); j <= Math.floor(b[3] / cell); j++) { const key = i * 1e5 + j; grid.has(key) ? grid.get(key).push(b) : grid.set(key, [b]); } };
    const heads = words(hit, add);
    vis.forEach(n => { const x = t.applyX(n.x), y = t.applyY(n.y), r = rad(n) * k; add([x - r, y - r, x + r, y + r]); });   // labels do not cover nodes
    ctx.font = '12px ' + C.serif;
    for (const n of cand) {
      const x = t.applyX(n.x), y = t.applyY(n.y), r = rad(n) * k, w = width(n), must = n === hover || n === picked;
      if (x < -200 || y < -20 || x > W + 20 || y > H + 20) continue;
      let b = [x + r + 4, y - 8, x + r + 4 + w, y + 8];
      if (!must && hit(...b)) { b = [x - r - 4 - w, y - 8, x - r - 4, y + 8]; if (S.mode === 'path' || hit(...b)) continue; }   // in Path, a label on the left reads as the column before
      add(b); placed.push([n, b]);
    }
    ctx.lineJoin = 'round'; ctx.lineWidth = 3; ctx.strokeStyle = C.bg;
    for (const [n, b] of placed) {
      const strong = n === picked || n === hover || n === focus || hits?.has(n);
      ctx.font = (strong ? '600 13px ' : '12px ') + C.serif;
      ctx.fillStyle = strong || L?.has(n) ? C.fg : C.mute;
      ctx.strokeText(n.name, b[0], (b[1] + b[3]) / 2); ctx.fillText(n.name, b[0], (b[1] + b[3]) / 2);
    }
    heads();
  }
  function words(hit, add) {   // subject names and column heads, in small spaced capitals; a head that would cover something is left out
    const big = c => c[3] !== 'col', font = c => (big(c) ? '600 12px ' : '500 11px ') + C.serif, keep = [];
    if ('letterSpacing' in ctx) ctx.letterSpacing = '1.5px';
    for (const c of [...captions].sort((a, b) => big(b) - big(a))) {
      ctx.font = font(c); const txt = c[2].toUpperCase(), w = ctx.measureText(txt).width, X = t.applyX(c[0]), Y = t.applyY(c[1]);
      const x0 = big(c) && c[3] !== 'band' ? X - w / 2 : X, b = [x0 - 2, Y - 8, x0 + w + 2, Y + 8];
      if (hit(...b)) continue; add(b); keep.push([c, txt, x0, Y]);
    }
    if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';
    return () => {
      if ('letterSpacing' in ctx) ctx.letterSpacing = '1.5px';
      ctx.lineWidth = 4; ctx.strokeStyle = C.bg; ctx.textAlign = 'left';
      for (const [c, txt, x, y] of keep) { ctx.font = font(c); ctx.fillStyle = big(c) ? C.fg : C.mute; ctx.strokeText(txt, x, y); ctx.fillText(txt, x, y); }
      if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';
    };
  }

  // ---- pointing, dragging, clicking -------------------------------------------------------------------------------
  const pick = (px, py) => {   // the nearest visible node within reach of the pointer
    let best = null, bd = Infinity;
    for (const n of vis) { const dx = t.applyX(n.x) - px, dy = t.applyY(n.y) - py, d = dx * dx + dy * dy, r = rad(n) * t.k + 6; if (d < r * r && d < bd) { best = n; bd = d; } }
    return best;
  };
  const hideTip = () => { tip.hidden = true; };
  const showTip = (n, px, py) => {
    const due = n.days === null ? 'new' : n.days <= 0 ? 'due now' : n.days < 1 ? `due in ${Math.round(n.days * 24)} h` : `due in ${Math.round(n.days)} d`;
    tip.textContent = ''; tip.append(Object.assign(document.createElement('b'), {textContent: n.name}),
      Object.assign(document.createElement('span'), {textContent: `${n.subject} · ${DEPTHS[n.floor]} · ${due} · ${n.nb.size} links`}),
      ...(n.reasons || []).slice(0, 3).map(r => Object.assign(document.createElement('span'), {textContent: r, className: 'why'})));
    tip.hidden = false; tip.style.left = Math.min(px + 14, W - tip.offsetWidth - 4) + 'px'; tip.style.top = Math.max(4, py - tip.offsetHeight - 10) + 'px';
  };
  cv.addEventListener('pointermove', e => {
    if (e.buttons) return;
    const n = pick(e.offsetX, e.offsetY); cv.style.cursor = n ? 'pointer' : 'grab';
    if (n !== hover) { hover = n; dirty(); }
    n ? showTip(n, e.offsetX, e.offsetY) : hideTip();
  });
  cv.addEventListener('pointerleave', () => { hover = null; hideTip(); dirty(); });
  cv.addEventListener('pointerdown', () => root.focus({preventScroll: true}));
  let moved = 0;
  const drag = d3.drag().subject(e => { const n = pick(e.x, e.y); return n && {n, x: t.applyX(n.x), y: t.applyY(n.y)}; })
    .on('start', e => { moved = 0; hideTip(); if (!S.frozen && !STATIC.has(S.mode)) sim.alphaTarget(.25).restart(); })
    .on('drag', e => {
      moved += Math.abs(e.dx) + Math.abs(e.dy); if (moved < 4) return;
      const n = e.subject.n; n.fx = n.x = t.invertX(e.x); n.fy = n.y = t.invertY(e.y); dirty();
    })
    .on('end', e => {
      const n = e.subject.n; sim.alphaTarget(0);
      if (moved < 4) { n.fx = n.fy = null; return e.sourceEvent.shiftKey ? (picked = picked === n ? null : n, showFocus(), dirty()) : (location = '/c/' + encodeURIComponent(n.id)); }
      const pins = store.pins[S.mode] ||= []; if (!pins.includes(n.id)) pins.push(n.id);
      (store.pos[S.mode] ||= {})[n.id] = [n.x, n.y];
      if (STATIC.has(S.mode)) { n.fx = n.fy = null; save(); } else if (S.frozen) keep(); else save();
      dirty();
    });
  sel.call(drag).call(zoom).on('dblclick.zoom', null);

  // ---- the levers -------------------------------------------------------------------------------------------------
  const $ = name => panel.querySelector(`[name="${name}"]`);
  const show = () => {   // the levers show the saved settings
    panel.querySelectorAll('[name=mode]').forEach(r => r.checked = r.value === S.mode);
    for (const k of ['spacing', 'link', 'push', 'size', 'steps', 'sizeBy', 'colorBy', 'labels', 'floorLo', 'floorHi']) $(k).value = S[k];
    for (const k of ['dueOnly', 'hideUnseen', 'related']) $(k).checked = S[k];
    subjects.forEach(s => { const b = $('sub:' + s); if (b) b.checked = S.subs[s] !== false; });
    $('freeze').firstChild.textContent = S.frozen ? 'Let it move' : 'Freeze';
    const motion = !STATIC.has(S.mode); $('link').disabled = $('push').disabled = !motion;
    legend(); showFocus();
  };
  const legend = () => {
    const el = panel.querySelector('.legend'), sw = (c, t, ring, w = 1) => { const s = document.createElement('span'), i = document.createElement('i');
      i.style.background = c; if (ring) i.style.boxShadow = `inset 0 0 0 ${w}px ${ring}`; s.append(i, t); return s; };
    el.replaceChildren(...(S.colorBy === 'subject' ? subjects.map(s => sw(subCol(s), s))
      : S.colorBy === 'understanding' ? [['strong', 'strong'], ['learning', 'learning'], ['fading', 'fading'], ['weak', 'weak'], ['gap', 'a gap you named']].map(([k, t]) => sw(C.state[k], t)).concat([sw(C.bg, 'unseen', C.mute)])
      : S.colorBy === 'due' ? [sw(C.no, 'due now'), sw(C.due(.5), 'in a week'), sw(C.ok, 'later'), sw(C.bg, 'new', C.mute)]
      : [sw(C.bg, 'unseen', C.mute), ...[1, 3, 5].map(f => sw(C.floor((f - 1) / 4), DEPTHS[f]))]),
      ...(S.colorBy !== 'due' ? [sw(C.bg, 'due', C.no, 2)] : []));
  };
  const showFocus = () => {
    const el = panel.querySelector('#focus-name');
    el.textContent = focus ? `Shows ${focus.name} and what is ${S.steps} ${S.steps > 1 ? 'steps' : 'step'} away. ⎋ stops it.`
      : picked ? `Press E to show only ${picked.name} and its neighbours.` : 'Point at a concept and press E, or find a concept.';
  };
  const relayout = ['mode', 'spacing', 'floorLo', 'floorHi', 'dueOnly', 'hideUnseen', 'related', 'steps'];
  panel.addEventListener('input', e => {
    const el = e.target, k = el.name; if (!k || k === 'q') return;
    if (k.startsWith('sub:')) S.subs[k.slice(4)] = el.checked;
    else if (el.type === 'checkbox') S[k] = el.checked;
    else if (el.type === 'radio') return setMode(el.value);
    else S[k] = el.tagName === 'SELECT' && !k.startsWith('floor') ? el.value : +el.value;
    if (k === 'floorLo' && S.floorLo > S.floorHi) S.floorHi = S.floorLo;
    if (k === 'floorHi' && S.floorHi < S.floorLo) S.floorLo = S.floorHi;
    save(); show();
    if (k === 'link' || k === 'push' || k === 'size') { if (STATIC.has(S.mode)) return dirty(); forces(); if (!S.frozen) sim.alpha(.4).restart(); return dirty(); }
    if (k === 'steps' && !focus) return;
    if (relayout.includes(k) || k.startsWith('sub:')) layout();
    if (k === 'sizeBy' && !STATIC.has(S.mode)) { forces(); if (!S.frozen) sim.alpha(.2).restart(); }
    dirty();
  });
  const setMode = m => {
    if (m === S.mode) return;
    S.mode = m; save(); show(); hover = null;
    const cam = store.cam[m]; layout({fit: !cam});
    if (cam) sel.transition().duration(450).call(zoom.transform, d3.zoomIdentity.translate(cam.x, cam.y).scale(cam.k));
  };
  const freeze = () => {
    if (STATIC.has(S.mode)) return;
    S.frozen = !S.frozen; save(); show();
    if (S.frozen) { sim.stop(); keep(); } else sim.alpha(.3).restart();
  };
  const reset = () => {   // forget the positions of this layout and lay it out again
    delete store.pos[S.mode]; delete store.pins[S.mode]; delete store.cam[S.mode];
    vis.forEach(n => { n.fx = n.fy = null; }); save(); layout({fresh: true, fit: true});
  };
  const levers = () => {
    const m = S.mode; Object.assign(S, structuredClone(DEF), {mode: m}); focus = null; hits = null; $('q').value = ''; save(); show(); layout({fit: true});
  };
  const setFocus = n => { focus = n; picked = n || picked; if (n) { q.value = ''; hits = null; list.replaceChildren(); } show(); layout({fit: true}); };
  panel.addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    ({freeze, fit: () => fit(), reset, levers})[b.name]?.();
  });

  // ---- find -------------------------------------------------------------------------------------------------------
  const q = $('q'), list = document.createElement('ul'); list.className = 'found'; q.after(list);
  const found = () => {
    const s = q.value.trim().toLowerCase();
    if (!s) { hits = null; list.replaceChildren(); return dirty(); }
    const all = nodes.filter(n => n.name.toLowerCase().includes(s) || n.id.includes(s))
      .sort((a, b) => a.name.toLowerCase().startsWith(s) ? -1 : b.name.toLowerCase().startsWith(s) ? 1 : a.name.localeCompare(b.name));
    hits = new Set(all.filter(n => visSet.has(n)));
    list.replaceChildren(...all.slice(0, 6).map(n => { const li = document.createElement('li'), a = document.createElement('a');
      a.textContent = n.name; a.href = '#'; a.onclick = ev => { ev.preventDefault(); go(n); };
      li.append(a); if (!visSet.has(n)) li.append(Object.assign(document.createElement('small'), {textContent: ' hidden by the levers'})); return li; }));
    if (!all.length) list.replaceChildren(Object.assign(document.createElement('li'), {className: 'hint', textContent: 'No concept has this name.'}));
    dirty();
  };
  const go = n => {   // pick a concept and centre on it; show it first if the levers hide it
    picked = n;
    if (!visSet.has(n)) { focus = null; S.subs[n.subject] = true; S.floorLo = 0; S.floorHi = 5; S.dueOnly = S.hideUnseen = false; save(); show(); layout(); }
    showFocus(); setTimeout(() => centre(n), tween ? 300 : 0); dirty();
  };
  q.addEventListener('input', found);
  q.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); const n = [...(hits || [])][0] || null; const first = list.querySelector('a'); n ? go(n) : first?.click(); }
    if (e.key === 'Escape') { q.value = ''; found(); root.focus(); }
  });

  // ---- keys, only while the graph has focus -----------------------------------------------------------------------
  root.addEventListener('keydown', e => {
    if (e.metaKey || e.ctrlKey || e.altKey || e.target === q) return;
    const k = e.code, own = e.target === root;
    if (/^Digit[1-4]$/.test(k)) setMode(['force', 'path', 'rings', 'groups'][+k[5] - 1]);
    else if (k === 'KeyF') fit();
    else if (k === 'KeyR') reset();
    else if (k === 'Space' && own) freeze();
    else if (k === 'KeyS') q.focus();
    else if (k === 'KeyE') { const n = hover || picked; if (focus && (!n || n === focus)) setFocus(null); else if (n) setFocus(n); }
    else if (k === 'KeyW') { S.labels = {all: 'learned', learned: 'hover', hover: 'all'}[S.labels]; save(); show(); dirty(); }
    else if (k === 'KeyD') { S.dueOnly = !S.dueOnly; save(); show(); layout(); }
    else if (k === 'Escape') { if (focus) setFocus(null); else { picked = null; q.value = ''; found(); showFocus(); } }
    else return;
    e.preventDefault();
  });

  // ---- start ------------------------------------------------------------------------------------------------------
  new ResizeObserver(resize).observe(stage); resize();
  document.addEventListener('abhyasa:theme', () => { themed(); legend(); dirty(); });   // core.js sends it for a new theme or mode
  show(); layout();
  const cam = store.cam[S.mode];
  if (cam && !picked) sel.call(zoom.transform, d3.zoomIdentity.translate(cam.x, cam.y).scale(cam.k));
  else setTimeout(() => { fit(0); if (picked) setTimeout(() => centre(picked), 50); }, tween ? tween.ms : 0);
  root.focus({preventScroll: true});
  window.abhyasaGraph = {nodes, stats, get t() { return t; }, get mode() { return S.mode; }, get vis() { return vis; }, get moving() { return !!tween || sim.alpha() > sim.alphaMin(); }};
})();
