// The concept graph on one canvas. d3-force moves the nodes in the Free and Groups layouts; Path and Rings put each node
// at a fixed place. d3-zoom moves the camera. One frame loop draws, and only when something changed.
// The levers in #levers (made by ui.py) change the layout, the look and what shows. The levers, the positions that you
// drag and the camera stay in localStorage, so the graph looks the same when you come back.
(async () => {
  const root = document.getElementById('graph'); if (!root) return;
  const cv = root.querySelector('canvas'), ctx = cv.getContext('2d'), tip = root.querySelector('.tip');
  const panel = root.querySelector('#levers'), note = root.querySelector('.note'), stage = root.querySelector('.stage');
  const KEY = 'abhyasa.graph.v1', DEPTHS = ['unseen', 'recognise', 'recall', 'explain', 'apply', 'transfer'];
  const STATIC = new Set(['path', 'rings', 'tree']), DAY = 86400, TT = window.abhyasaTree;   // TT: graphtree.js, the pure part of the Tree
  const g = await (await fetch(root.dataset.url)).json();
  note.remove();
  if (!g.nodes.length) { stage.append(Object.assign(document.createElement('p'), {className: 'hint note', textContent: 'Each idea that you learn shows here. Start with a walk.'})); return; }

  // ---- the levers and what is saved -------------------------------------------------------------------------------
  const DEF = {mode: 'force', spacing: 50, link: 50, push: 50, size: 50, sizeBy: 'seen', colorBy: 'floor', labels: 'all', groupBy: 'subject',
               floorLo: 0, floorHi: 5, dueOnly: false, hideUnseen: false, related: true, steps: 1, frozen: false, asList: false, subs: {}};
  let store; try { store = JSON.parse(localStorage.getItem(KEY)) || {}; } catch { store = {}; }
  store.pos ||= {}; store.pins ||= {}; store.cam ||= {}; store.collapsed ||= [];   // collapsed: the closed branches of the Tree
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
  nodes.forEach(n => { n.subject ||= 'general'; n.gkey = n.group?.length ? `${n.subject} › ${n.group[0]}` : `${n.subject} · not sorted`; n.days = n.seen && n.due ? (n.due - now) / DAY : null; n.nb = new Set(); });
  links.forEach(l => { l.s.nb.add(l.t); l.t.nb.add(l.s); });
  const isDue = n => n.days !== null && n.days <= 0, learned = n => n.floor > 0 || n.seen > 0;
  const dueness = n => n.days === null ? 0 : n.days <= 0 ? 1 : Math.max(0, 1 - n.days / 14);
  if (root.dataset.subject && subjects.includes(root.dataset.subject)) subjects.forEach(s => S.subs[s] = s === root.dataset.subject);
  const READY = g.ready ?? 3;   // the depth at which a concept is ready (abhyasa.path.READY): the Tree calls it mastered
  const openC = n => (window.abhyasaGo || (u => location = u))('/c/' + encodeURIComponent(n.id));   // a click on a concept opens it, in each layout
  const review = n => n.days === null ? 'no review yet' : n.days <= 0 ? 'review due now'
    : n.days < 1 ? `next review in ${Math.max(1, Math.round(n.days * 24))} h` : `next review in ${Math.round(n.days)} ${Math.round(n.days) === 1 ? 'day' : 'days'}`;

  // ---- what went up since your last visit ---------------------------------------------------------------------------
  // The floors of the last visit stay in localStorage. Each idea whose floor went up gets one soft ring pulse in its new colour,
  // and a new idea fades in beside its first prereq. A quiet line says how many. A floor that went down shows only its new colour.
  // With reduced motion: only the line and the colours.
  const SEEN = 'abhyasa.graph.seen', PULSE = 600, FADE = 220, motion = abhyasaMotion();
  let last; try { last = JSON.parse(localStorage.getItem(SEEN)); } catch { last = null; }
  const before = last && last.floors || null;
  const rose = before ? nodes.filter(n => n.id in before && n.floor > before[n.id]) : [];
  const fresh = before ? nodes.filter(n => !(n.id in before)) : [];
  try { localStorage.setItem(SEEN, JSON.stringify({at: Date.now(), floors: {...before, ...Object.fromEntries(nodes.map(n => [n.id, n.floor]))}})); } catch {}
  const ideas = n => `${n} ${n === 1 ? 'idea' : 'ideas'}`;
  const said = [rose.length ? `${ideas(rose.length)} went up since your last visit.` : '', fresh.length ? `You have ${fresh.length} new ${fresh.length === 1 ? 'idea' : 'ideas'} since your last visit.` : ''].filter(Boolean);
  if (said.length) stage.append(Object.assign(document.createElement('p'), {className: 'moved', textContent: said.join(' ')}));
  let pulse = null;   // {t0, ring: Set, fade: Set} while the pulse runs

  // ---- the colours, from the theme --------------------------------------------------------------------------------
  let C = {};
  const probe = root.appendChild(document.createElement('i'));
  const v = name => { probe.style.color = `var(${name})`; return getComputedStyle(probe).color; };
  const UNSEEN = .3;   // how far an unseen node goes from the page colour to the text colour: the raised colour is too close to the page in the dark themes
  const themed = () => {
    C = {bg: v('--bg'), fg: v('--fg'), ink2: v('--ink2'), mute: v('--mute'), raised: v('--raised'), rule: v('--rule'), line: v('--line'), acc: v('--acc'), no: v('--no'), ok: v('--ok'),
         subs: [1, 2, 3, 4, 5, 6].map(i => v(`--g${i}`)), serif: getComputedStyle(root).getPropertyValue('--serif')};
    C.unseen = d3.interpolateRgb(C.bg, C.fg)(UNSEEN);
    C.dark = d3.hsl(C.bg).l < .5;   // the theme and the mode are on <html>, so the page bg says which
    C.floor = d3.interpolateRgb(d3.interpolateRgb(C.bg, C.acc)(.4), C.acc);
    C.due = d3.interpolateRgb(C.no, C.ok);
    C.state = {strong: C.ok, learning: C.floor(.3), fading: C.due(.5), weak: C.no, gap: C.acc};
    C.status = {unseen: C.unseen, learning: C.floor(.3), mastered: C.ok, due: C.no};   // the four words of the Tree
  };
  themed();
  const subCol = s => C.subs[subjects.indexOf(s) % C.subs.length];
  // A cluster is a subject, or with Group by group a subject and the first level of its group (for example `jyotisha › nakshatras`).
  const ckey = n => S.groupBy === 'group' ? n.gkey : n.subject, clusters = () => [...new Set(nodes.map(ckey))];
  const fill = n => S.mode === 'tree' ? C.status[n.tstatus] || C.unseen : S.colorBy === 'subject' ? subCol(n.subject)
    : S.colorBy === 'understanding' ? (C.state[n.state] || C.unseen)
    : S.colorBy === 'due' ? (n.days === null ? C.unseen : C.due(Math.min(1, Math.max(0, n.days / 14))))
    : n.floor ? C.floor((n.floor - 1) / 4) : C.unseen;
  const hollow = n => S.mode === 'tree' ? n.tstatus === 'unseen' : S.colorBy === 'subject' ? false : S.colorBy === 'understanding' ? !C.state[n.state] : S.colorBy === 'due' ? n.days === null : !n.floor;
  const rad = n => sz() * (4.5 + (S.sizeBy === 'seen' ? 1.6 * Math.sqrt(Math.min(n.seen, 16))
    : S.sizeBy === 'due' ? 6 * dueness(n) : S.sizeBy === 'depth' ? 1.6 * Math.min(n.depth || 0, 6) : 1));

  // ---- what shows -------------------------------------------------------------------------------------------------
  let focus = null, picked = root.dataset.focus && byId.get(root.dataset.focus) || null, hover = null, hits = null;
  let vis = [], visLinks = [], visSet = new Set();
  let tree = null, cur = null, tpos = new Map(), toggles = [], capHits = [], lastLabels = [];   // the Tree: its items, the key of the arrow keys, root places, hit boxes
  const collapsed = new Set(store.collapsed);
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
    if (S.mode === 'tree') buildTree();
  };
  const buildTree = () => {   // the tree of what the levers show; a closed branch then hides the concepts under it
    const pl = links.filter(l => l.kind === 'prereq' && visSet.has(l.s) && visSet.has(l.t)).map(l => ({source: l.s.id, target: l.t.id, kind: 'prereq'}));
    tree = TT.build(vis, pl, {ready: READY, now});
    tree.byKey.forEach(it => { if (it.kind === 'concept') byId.get(it.id).tstatus = it.status; });
    const shown = new Set(TT.rows(tree, collapsed).map(r => r.item.key));
    vis = vis.filter(n => shown.has(n.id)); visSet = new Set(vis); visLinks = visLinks.filter(l => visSet.has(l.s) && visSet.has(l.t));
    if (!cur && picked && shown.has(picked.id)) cur = picked.id;
    if (cur && !shown.has(cur)) cur = tree.byKey.has(cur) ? TT.above(tree, cur).find(k => shown.has(k)) || null : null;
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
    sim.force('x', null).force('y', null).nodes(vis).velocityDecay(.4)   // the old centres do not know the new clusters
      .force('link', d3.forceLink(visLinks).distance(l => linkLen() * (l.kind === 'related' ? 1.3 : 1)).strength(l => (l.kind === 'related' ? .3 : .7) * (groups && ckey(l.s) !== ckey(l.t) ? .15 : 1) / Math.min(l.s.nb.size, l.t.nb.size)))
      .force('charge', d3.forceManyBody().strength(charge() * (groups ? .6 : 1)).distanceMax(500 * k))
      .force('x', d3.forceX(n => groups ? centre.get(ckey(n))[0] : 0).strength(groups ? .14 : .05))
      .force('y', d3.forceY(n => groups ? centre.get(ckey(n))[1] : 0).strength(groups ? .14 : .05))
      .force('collide', d3.forceCollide(n => rad(n) + 3 * k));
    const pins = pinned(); vis.forEach(n => { n.fx = n.fy = null; if (pins.has(n.id) && store.pos[S.mode]?.[n.id]) [n.fx, n.fy] = store.pos[S.mode][n.id]; });
  };
  const groupCentres = () => {   // the subjects on a circle, far enough apart for their sizes
    const subs = clusters().filter(s => vis.some(n => ckey(n) === s)), size = s => Math.sqrt(vis.filter(n => ckey(n) === s).length);
    const R = subs.length < 2 ? 0 : d3.sum(subs, size) * 24 * sp() / Math.PI;
    return new Map(subs.map((s, i) => [s, [R * Math.cos(2 * Math.PI * i / subs.length - Math.PI / 2), R * Math.sin(2 * Math.PI * i / subs.length - Math.PI / 2)]]));
  };
  const pathTargets = () => {   // a block for each subject: one column for each step of prereqs, then a grid of the rest
    const k = sp(), col = 190 * k, row = 26 * k, aspect = (cv.clientWidth || 900) / (cv.clientHeight || 600), blocks = [];
    for (const s of clusters()) {
      const ns = vis.filter(n => ckey(n) === s); if (!ns.length) continue;
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
    const subs = clusters().filter(s => vis.some(n => ckey(n) === s)).map(s => ({s, ns: vis.filter(n => ckey(n) === s)}));
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
  // The Tree, left to right: d3's tidy tree (Reingold-Tilford) gives each row, so no two branches cover each other; each
  // column is as wide as its widest name, so a name does not run into the next column. The subjects are the roots.
  const treeTargets = () => {
    const T = new Map(), k = sp(); tpos = new Map(); captions = [];
    if (!tree) return T;
    const row = Math.max(30 * k, 2 * (d3.max(vis, rad) || 5) + 10), gap = 44 * k;
    const top = d3.hierarchy({key: '', kind: 'top', children: tree.roots}, d => d.kind === 'top' || !collapsed.has(d.key) ? d.children : null);
    const sub = d => d.ancestors().at(-2);   // the subject of a row
    d3.tree().nodeSize([row, 1]).separation((a, b) => sub(a) !== sub(b) ? 2.2 : a.parent === b.parent ? 1 : 1.25)(top);
    const wide = []; top.each(d => { if (d.depth) wide[d.depth] = Math.max(wide[d.depth] || 0, itemW(d.data)); });
    const col = [0, 0]; for (let i = 2; i < wide.length; i++) col[i] = col[i - 1] + wide[i - 1] + gap;
    top.each(d => { if (!d.depth) return; const p = [col[d.depth], d.x]; tpos.set(d.data.key, p); if (d.data.kind === 'concept') T.set(byId.get(d.data.id), p); });
    return T;
  };
  const tw = new Map(), textW = (s, font = '13px ' + C.serif) => {   // the width of a text at a fixed screen size, measured once
    const key = font + '|' + s; if (!tw.has(key)) { ctx.save(); ctx.font = font; tw.set(key, ctx.measureText(s).width); ctx.restore(); } return tw.get(key);
  };
  const suffix = it => !it.children.length ? '' : collapsed.has(it.key) ? `  ▸ ${it.size}` : '  ▾';   // a closed branch says how many it hides
  const capText = r => `${r.name} · ${r.size}${collapsed.has(r.key) ? '  ▸' : ''}`;
  const capW = r => { const s = capText(r).toUpperCase(); return textW(s, '600 12px ' + C.serif) + 1.5 * s.length; };
  const rootR = () => 5 * sz();
  const itemW = it => it.kind === 'subject' ? rootR() + 6 + capW(it) : rad(byId.get(it.id)) + 4 + textW(it.name) + (suffix(it) ? textW(suffix(it)) : 0);
  const itemOf = n => tree?.byKey.get(n.id);

  // Move the nodes to `T` (node -> [x, y]) in a short glide; the nodes that you dragged stay where you put them.
  let tween = null;
  const glide = (T, ms = 650) => {
    const pins = pinned(), P = store.pos[S.mode] || {};
    vis.forEach(n => { if (pins.has(n.id) && P[n.id]) T.set(n, P[n.id]); if (!T.has(n)) T.set(n, [n.x ?? 0, n.y ?? 0]); if (STATIC.has(S.mode)) n.fx = n.fy = null; });
    if (ms <= 0) { T.forEach(([x, y], n) => { n.x = x; n.y = y; }); tween = null; return dirty(); }   // reduced motion: the nodes go to their places at once
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
    if (STATIC.has(S.mode)) { glide(S.mode === 'path' ? pathTargets() : S.mode === 'tree' ? treeTargets() : ringTargets(), S.mode === 'tree' && !motion ? 0 : 650); }
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
    else if (f) setTimeout(() => fit(S.mode === 'tree' && !motion ? 0 : 450), tween ? tween.ms * .4 : 0);
    dirty();
  };
  const seed = n => {   // a new node starts next to a neighbour that has a place, or at a random place near the middle
    const placed = [...n.nb].filter(m => m.x !== undefined), m = placed.find(m => kinds.get(m.id + '>' + n.id) === 'prereq') || placed[0];
    const a = Math.random() * 2 * Math.PI, r = m ? 20 : 120 * Math.random();
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
    .on('end', () => { store.cam[S.mode] = {k: t.k, x: t.x, y: t.y, w: W}; save(); });   // the width too: a new width fits again
  const sel = d3.select(cv);
  const box = () => {
    const T = tween ? [...tween.to.values()] : vis.map(n => [n.x, n.y]);
    if (S.mode === 'tree' && tree) tpos.forEach((p, key) => T.push(p, [p[0] + itemW(tree.byKey.get(key)) + 12, p[1]]));   // the names and the roots must show too
    if (!T.length) return [[-1, -1], [1, 1]];
    if (STATIC.has(S.mode) && S.mode !== 'tree') captions.forEach(c => T.push([c[0], c[1]]));   // the subject names must show too
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
  function frame(ts) {
    raf = 0; const more = tween && glideStep(ts); draw();
    if (pulse && performance.now() - pulse.t0 >= PULSE) { pulse = null; draw(); }
    if (more || pulse) dirty();
  }
  const region = document.createElement('canvas'), rctx = region.getContext('2d'), soft = document.createElement('canvas'), sctx = soft.getContext('2d');
  const widths = new Map(); const width = n => widths.get(n) ?? (widths.set(n, ctx.measureText(n.name).width), widths.get(n));
  const lit = () => {   // the nodes in full colour: what you point at and its neighbours, or what you find; null for all
    if (hover) return new Set([hover, ...[...hover.nb].filter(m => visSet.has(m))]);
    return hits;
  };
  function treeLinks(L, k) {   // the branches from the end of a name to the child, the other prereqs as thin dashes, and the roots
    const at = it => it.kind === 'subject' ? tpos.get(it.key) : [byId.get(it.id).x, byId.get(it.id).y];
    const from = it => it.kind === 'subject' ? rootR() + (6 + capW(it) + 8) / k : rad(byId.get(it.id)) + (4 + textW(it.name) + (suffix(it) ? textW(suffix(it)) : 0) + 6) / k;
    ctx.beginPath();
    for (const l of tree.cross) {   // as a branch: from the end of the name of the prereq to the left edge of the concept, so it does not cross a name
      const a = byId.get(l.source), b = byId.get(l.target); if (!visSet.has(a) || !visSet.has(b)) continue;
      const x0 = b.x > a.x ? Math.max(a.x, Math.min(a.x + from(tree.byKey.get(a.id)), b.x - 14 / k)) : a.x, x1 = b.x - rad(b), mx = (x0 + x1) / 2;
      ctx.moveTo(x0, a.y); ctx.bezierCurveTo(mx, a.y, mx, b.y, x1, b.y);
    }
    ctx.setLineDash([2 / k, 3 / k]); ctx.strokeStyle = C.mute; ctx.globalAlpha = L ? .12 : .5; ctx.lineWidth = .8 / k; ctx.stroke(); ctx.setLineDash([]);
    for (const on of [false, true]) {
      ctx.beginPath();
      for (const it of tree.byKey.values()) {
        if (it.kind !== 'concept') continue;
        const n = byId.get(it.id), par = tree.byKey.get(it.parent), p = par && at(par); if (!visSet.has(n) || !p) continue;
        if ((!!L && L.has(n) && (par.kind === 'subject' || L.has(byId.get(par.id)))) !== on) continue;
        const x0 = Math.max(p[0], Math.min(p[0] + from(par), n.x - 14 / k)), x1 = n.x - rad(n), mx = (x0 + x1) / 2;
        ctx.moveTo(x0, p[1]); ctx.bezierCurveTo(mx, p[1], mx, n.y, x1, n.y);
      }
      ctx.strokeStyle = on ? C.acc : C.mute; ctx.globalAlpha = on ? 1 : L ? .2 : .8; ctx.lineWidth = (on ? 1.8 : 1.2) / k; ctx.stroke();
    }
    ctx.globalAlpha = 1;
    for (const r of tree.roots) {   // a root: a small square in the colour of its subject
      const p = tpos.get(r.key), s = rootR(); if (!p) continue;
      ctx.fillStyle = subCol(r.subject); ctx.fillRect(p[0] - s, p[1] - s, 2 * s, 2 * s);
      if (cur === r.key) { ctx.strokeStyle = C.acc; ctx.lineWidth = 1.5 / k; ctx.strokeRect(p[0] - s - 4 / k, p[1] - s - 4 / k, 2 * s + 8 / k, 2 * s + 8 / k); }
    }
  }
  function draw() {
    const t0 = performance.now(), L = lit(), k = t.k;
    if (S.mode === 'tree' && tree) captions = tree.roots.filter(r => tpos.has(r.key)).map(r => { const p = tpos.get(r.key); return [p[0] + rootR() + 6 / k, p[1], capText(r), 'band', r.key]; });
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
    regions();
    ctx.save(); ctx.translate(t.x, t.y); ctx.scale(k, k);
    // the links: prereqs are lines with an arrow, related links are dashes
    const curve = S.mode === 'path';
    if (S.mode === 'tree' && tree) treeLinks(L, k);
    else for (const [kind, on] of [['related', false], ['prereq', false], ['related', true], ['prereq', true]]) {
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
      const r = rad(n), dim = L && !L.has(n), age = pulse ? performance.now() - pulse.t0 : PULSE;
      ctx.globalAlpha = (dim ? .2 : 1) * (pulse && pulse.fade.has(n) ? Math.min(1, age / FADE) : 1);
      ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 2 * Math.PI); ctx.fillStyle = fill(n); ctx.fill();
      const due = isDue(n) && S.colorBy !== 'due' && S.mode !== 'tree';   // in the Tree, the fill says review due
      ctx.lineWidth = (due ? 2.2 : n === picked ? 2.4 : 1) / k;
      ctx.strokeStyle = n === picked ? C.fg : due ? C.no : hollow(n) ? C.mute : C.bg; ctx.stroke();
      if (n === picked) { ctx.beginPath(); ctx.arc(n.x, n.y, r + 4 / k, 0, 2 * Math.PI); ctx.strokeStyle = C.acc; ctx.lineWidth = 1.5 / k; ctx.stroke(); }
      if (pins.has(n.id)) { ctx.beginPath(); ctx.arc(n.x, n.y, Math.min(r * .35, 2.2 / k + r * .1), 0, 2 * Math.PI); ctx.fillStyle = hollow(n) ? C.mute : C.bg; ctx.fill(); }
      if (pulse && pulse.ring.has(n) && age < PULSE) {   // one soft ring that grows out and fades
        const p = age / PULSE, e = d3.easeCubicOut(p);
        ctx.beginPath(); ctx.arc(n.x, n.y, r + (2 + 10 * e) / k, 0, 2 * Math.PI);
        ctx.globalAlpha = .7 * (1 - p); ctx.strokeStyle = hollow(n) ? C.mute : fill(n); ctx.lineWidth = 2 / k; ctx.stroke();
      }
    }
    ctx.globalAlpha = 1; ctx.restore();
    labels(L);
    const d = performance.now() - t0; stats.frames++; stats.draw = d; stats.sum += d; stats.max = Math.max(stats.max, d);
  }
  let regionList = [];
  function regions() {   // a soft tint and a label for each cluster: Groups, Path, and Free with Colour by subject; one colour does not add up where it overlaps
    regionList = [];
    const on = S.mode === 'groups' || S.mode === 'path' || (S.mode === 'force' && S.colorBy === 'subject');
    if (!on) { if (S.mode === 'force') captions = []; return; }
    const q = 4, w = Math.ceil(W / q), h = Math.ceil(H / q), R = 30 * sp(), box = S.mode === 'path', groups = d3.groups(vis, ckey);
    if (region.width !== w || region.height !== h) { region.width = soft.width = w; region.height = soft.height = h; }
    rctx.setTransform(1, 0, 0, 1, 0, 0); rctx.clearRect(0, 0, w, h);
    rctx.setTransform(t.k / q, 0, 0, t.k / q, t.x / q, t.y / q);
    for (const [key, ns] of groups) {
      rctx.fillStyle = subCol(ns[0].subject); rctx.beginPath();
      if (box) {   // Path: a rounded box round the block, as the nodes sit in columns
        const x0 = d3.min(ns, n => n.x) - 16, y0 = d3.min(ns, n => n.y) - 14, x1 = d3.max(ns, n => n.x) + 16, y1 = d3.max(ns, n => n.y) + 14;
        rctx.roundRect(x0, y0, x1 - x0, y1 - y0, 14);
      } else for (const n of ns) { rctx.moveTo(n.x + R, n.y); rctx.arc(n.x, n.y, R, 0, 2 * Math.PI); }
      rctx.fill();
      regionList.push({key, n: ns.length});
    }
    // blur at a quarter of the size, where it costs little, then scale it up; the scale-up smooths it too
    sctx.clearRect(0, 0, w, h); sctx.filter = `blur(${Math.max(1, 2.5 * t.k)}px)`; sctx.drawImage(region, 0, 0); sctx.filter = 'none';
    ctx.save(); ctx.globalAlpha = C.dark ? .16 : .12; ctx.imageSmoothingEnabled = true; ctx.drawImage(soft, 0, 0, w * q, h * q); ctx.restore();
    if (S.mode !== 'path') captions = groups.map(([s, ns]) => [d3.mean(ns, n => n.x), d3.min(ns, n => n.y) - R * .9, s, 'group']);   // the label sits above its region
  }
  function labels(L) {   // labels at a fixed screen size; a label that would cover another one is left out
    const tr = S.mode === 'tree' && !!tree, want = tr ? 'all' : S.labels, k = t.k, cell = 40, grid = new Map(), placed = [];   // the Tree shows each name
    toggles = []; capHits = []; lastLabels = [];
    ctx.font = '13px ' + C.serif; ctx.textBaseline = 'middle';
    const rank = n => (S.mode === 'path' && n.linked ? 1e4 : 0) + (n === picked ? 1e6 : 0) + (n === hover ? 2e6 : 0) + (hits?.has(n) ? 5e5 : 0) + (L?.has(n) ? 1e5 : 0) + n.floor * 100 + Math.min(n.seen, 50) + n.nb.size * 3;
    const cand = vis.filter(n => n === picked || n === hover || (L ? L.has(n) : want === 'all' || (want === 'learned' && learned(n)) || n === focus))
      .filter(n => want !== 'hover' || L || n === picked || n === focus || n === hover).sort((a, b) => rank(b) - rank(a));
    const hit = (x0, y0, x1, y1) => {
      for (let i = Math.floor(x0 / cell); i <= Math.floor(x1 / cell); i++) for (let j = Math.floor(y0 / cell); j <= Math.floor(y1 / cell); j++)
        for (const b of grid.get(i * 1e5 + j) || []) if (b[0] < x1 && b[2] > x0 && b[1] < y1 && b[3] > y0) return true;
      return false;
    };
    const add = b => { for (let i = Math.floor(b[0] / cell); i <= Math.floor(b[2] / cell); i++) for (let j = Math.floor(b[1] / cell); j <= Math.floor(b[3] / cell); j++) { const key = i * 1e5 + j; grid.has(key) ? grid.get(key).push(b) : grid.set(key, [b]); } };
    const EDGE = 4, inside = b => b[0] >= EDGE && b[2] <= W - EDGE;
    const into = b => { const dx = b[0] < EDGE ? EDGE - b[0] : Math.min(0, W - EDGE - b[2]); return dx ? [b[0] + dx, b[1], b[2] + dx, b[3]] : b; };   // a label that is wider than the room left moves into the view
    const heads = words(hit, add, into);
    vis.forEach(n => { const x = t.applyX(n.x), y = t.applyY(n.y), r = rad(n) * k; add([x - r, y - r, x + r, y + r]); });   // labels do not cover nodes
    ctx.font = '13px ' + C.serif;
    for (const n of cand) {
      const x = t.applyX(n.x), y = t.applyY(n.y), r = rad(n) * k, w = width(n) + (tr && suffix(itemOf(n)) ? textW(suffix(itemOf(n))) : 0), must = n === hover || n === picked;
      if (x < -200 || y < -20 || x > W + 20 || y > H + 20) continue;
      const right = [x + r + 4, y - 9, x + r + 4 + w, y + 9], left = [x - r - 4 - w, y - 9, x - r - 4, y + 9];
      let b = tr || inside(right) || !inside(left) ? right : left;   // at the right edge, the label goes at the left of its node; in the Tree, always at the right, where its branch starts
      if (!must && hit(...b)) { if (b === left || tr || S.mode === 'path' || !inside(left) || hit(...left)) continue; b = left; }   // in Path, a label on the left reads as the column before
      b = into(b); add(b); placed.push([n, b]); lastLabels.push(n.id);
    }
    ctx.lineJoin = 'round'; ctx.lineWidth = 3; ctx.strokeStyle = C.bg;
    for (const [n, b] of placed) {
      const strong = n === picked || n === hover || n === focus || hits?.has(n);
      ctx.font = (strong ? '600 13px ' : '13px ') + C.serif;
      ctx.fillStyle = strong || L?.has(n) ? C.fg : C.ink2;
      ctx.strokeText(n.name, b[0], (b[1] + b[3]) / 2); ctx.fillText(n.name, b[0], (b[1] + b[3]) / 2);
      const it = tr && itemOf(n), suf = it && suffix(it);
      if (suf) {   // the open or closed mark of a branch, quiet; a click on it closes or opens the branch
        const x0 = b[0] + ctx.measureText(n.name).width, y = (b[1] + b[3]) / 2;
        ctx.font = '13px ' + C.serif; ctx.fillStyle = C.mute; ctx.strokeText(suf, x0, y); ctx.fillText(suf, x0, y);
        toggles.push([it.key, [x0, b[1], x0 + textW(suf) + 4, b[3]]]);
      }
    }
    heads();
  }
  function words(hit, add, into) {   // subject names and column heads, in small spaced capitals; a head that would cover something is left out
    const big = c => c[3] !== 'col', font = c => (big(c) ? '600 12px ' : '500 11px ') + C.serif, keep = [];
    if ('letterSpacing' in ctx) ctx.letterSpacing = '1.5px';
    for (const c of [...captions].sort((a, b) => big(b) - big(a))) {
      ctx.font = font(c); const txt = c[2].toUpperCase(), w = ctx.measureText(txt).width, X = t.applyX(c[0]), Y = t.applyY(c[1]);
      const b = into([(big(c) && c[3] !== 'band' ? X - w / 2 : X) - 2, Y - 8, (big(c) && c[3] !== 'band' ? X + w / 2 : X + w) + 2, Y + 8]);   // a head at an edge moves into the view
      if (hit(...b)) continue; add(b); keep.push([c, txt, b[0] + 2, Y]); if (c[4]) capHits.push([c[4], b]);   // c[4]: the key of a root of the Tree
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
      Object.assign(document.createElement('span'), {textContent: S.mode === 'tree' ? `${TT.WORDS[n.tstatus]} · depth ${DEPTHS[n.floor]} · ${review(n)}` : `${n.subject} · ${DEPTHS[n.floor]} · ${due} · ${n.nb.size} links`}),
      ...(n.reasons || []).slice(0, 3).map(r => Object.assign(document.createElement('span'), {textContent: r, className: 'why'})));
    tip.hidden = false; tip.style.left = Math.min(px + 14, W - tip.offsetWidth - 4) + 'px'; tip.style.top = Math.max(4, py - tip.offsetHeight - 10) + 'px';
  };
  // The Tree: a root, its name, or the mark after a name closes or opens a branch. Clicking a concept opens it, as in each layout.
  const counted = r => `${r.size} ${r.size === 1 ? 'concept' : 'concepts'}` + (r.size ? ': ' + TT.ORDER.filter(s => r.counts[s]).map(s => `${r.counts[s]} ${TT.WORDS[s]}`).join(', ') : '');
  const rootTip = (r, px, py) => {
    tip.textContent = ''; tip.append(Object.assign(document.createElement('b'), {textContent: r.name}), Object.assign(document.createElement('span'), {textContent: counted(r)}));
    tip.hidden = false; tip.style.left = Math.min(px + 14, W - tip.offsetWidth - 4) + 'px'; tip.style.top = Math.max(4, py - tip.offsetHeight - 10) + 'px';
  };
  const treeHit = (px, py) => {
    if (S.mode !== 'tree' || !tree) return null;
    const inb = b => px >= b[0] && px <= b[2] && py >= b[1] && py <= b[3];
    for (const [key, b] of [...toggles, ...capHits]) if (inb(b)) return key;
    for (const r of tree.roots) { const p = tpos.get(r.key); if (p && Math.hypot(t.applyX(p[0]) - px, t.applyY(p[1]) - py) < rootR() * t.k + 6) return r.key; }
    return null;
  };
  const say = it => {   // the words for the item of the arrow keys: the live line beside the graph reads them out
    if (it.kind === 'subject') return `${it.name}: ${counted(it)}.${collapsed.has(it.key) ? ' Closed.' : ''}`;
    const n = byId.get(it.id), kids = it.children.length ? ` ${collapsed.has(it.key) ? 'Closed' : 'Open'} branch of ${it.size}.` : '';
    return `${it.name}: ${TT.WORDS[it.status]}, depth ${DEPTHS[it.floor]}, ${review(n)}.${kids}`;
  };
  const itemTip = it => {
    const p = it.kind === 'subject' ? tpos.get(it.key) : [byId.get(it.id).x, byId.get(it.id).y]; if (!p) return;
    const x = t.applyX(p[0]), y = t.applyY(p[1]);
    it.kind === 'subject' ? rootTip(it, x, y) : showTip(byId.get(it.id), x, y);
  };
  const setCur = key => {   // move the arrow-key item; the view follows it when it goes out of sight, at once with reduced motion
    const it = key && tree?.byKey.get(key); if (!it) return;
    cur = key; picked = it.kind === 'concept' ? byId.get(it.id) : null;
    const p = it.kind === 'subject' ? tpos.get(key) : [picked.x, picked.y], x = t.applyX(p[0]), y = t.applyY(p[1]);
    panel.querySelector('#focus-name').textContent = say(it);
    if (x < 8 || x > W - 160 || y < 12 || y > H - 12) {   // out of sight: the fit leaves 30 px at the left and room for the names at the right
      const to = d3.zoomIdentity.translate(W / 2 - 110, H / 2).scale(t.k).translate(-p[0], -p[1]);
      if (motion) { sel.transition().duration(400).call(zoom.transform, to); setTimeout(() => itemTip(it), 430); } else { sel.call(zoom.transform, to); itemTip(it); }
    } else itemTip(it);
    dirty();
  };
  const toggle = key => {   // close or open a branch; the closed branches stay in localStorage
    if (!tree?.byKey.get(key)?.children.length) return;
    collapsed.has(key) ? collapsed.delete(key) : collapsed.add(key); store.collapsed = [...collapsed]; save();
    if (cur && TT.above(tree, cur).includes(key)) cur = key;
    hideTip(); layout(); renderList();
    if (cur) panel.querySelector('#focus-name').textContent = say(tree.byKey.get(cur));
  };
  const treeKey = code => {   // ← the parent, → the first child (it opens a closed branch first), ↑ ↓ the siblings, ⏎ opens, ␣ closes or opens
    const it = cur && tree.byKey.get(cur);
    if (!it) return setCur(TT.move(tree, null, 'next'));
    if (code === 'Enter' || code === 'NumpadEnter') return it.kind === 'concept' ? openC(byId.get(it.id)) : toggle(it.key);
    if (code === 'Space') return toggle(it.key);
    if (code === 'ArrowRight' && collapsed.has(it.key)) return toggle(it.key);
    setCur(TT.move(tree, cur, {ArrowLeft: 'parent', ArrowRight: 'child', ArrowUp: 'prev', ArrowDown: 'next'}[code], collapsed));
  };
  cv.addEventListener('pointermove', e => {
    if (e.buttons) return;
    const n = pick(e.offsetX, e.offsetY), tk = !n && treeHit(e.offsetX, e.offsetY); cv.style.cursor = n || tk ? 'pointer' : 'grab';
    if (n !== hover) { hover = n; dirty(); }
    n ? showTip(n, e.offsetX, e.offsetY) : tk && tree.byKey.get(tk).kind === 'subject' ? rootTip(tree.byKey.get(tk), e.offsetX, e.offsetY) : hideTip();
  });
  cv.addEventListener('pointerleave', () => { hover = null; hideTip(); dirty(); });
  cv.addEventListener('click', e => { if (pick(e.offsetX, e.offsetY)) return; const k = treeHit(e.offsetX, e.offsetY); if (k) { cur = k; toggle(k); } });
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
      if (moved < 4) { n.fx = n.fy = null; return e.sourceEvent.shiftKey ? (picked = picked === n ? null : n, showFocus(), dirty()) : openC(n); }
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
    for (const k of ['spacing', 'link', 'push', 'size', 'steps', 'sizeBy', 'colorBy', 'labels', 'groupBy', 'floorLo', 'floorHi']) $(k).value = S[k];
    for (const k of ['dueOnly', 'hideUnseen', 'related', 'asList']) $(k).checked = S[k];
    panel.querySelector('.tree-only').hidden = S.mode !== 'tree'; $('colorBy').disabled = S.mode === 'tree';   // the Tree colours by its four words
    subjects.forEach(s => { const b = $('sub:' + s); if (b) b.checked = S.subs[s] !== false; });
    $('freeze').firstChild.textContent = S.frozen ? 'Let it move' : 'Freeze';
    const motion = !STATIC.has(S.mode); $('link').disabled = $('push').disabled = !motion;
    legend(); showFocus();
  };
  const legend = () => {
    const el = panel.querySelector('.legend'), sw = (c, t, ring, w = 1) => { const s = document.createElement('span'), i = document.createElement('i');
      i.style.background = c; if (ring) i.style.boxShadow = `inset 0 0 0 ${w}px ${ring}`; s.append(i, t); return s; };
    el.replaceChildren(...(S.mode === 'tree' ? TT.ORDER.map(s => sw(C.status[s], TT.WORDS[s], s === 'unseen' ? C.mute : null))
      : S.colorBy === 'subject' ? subjects.map(s => sw(subCol(s), s))
      : S.colorBy === 'understanding' ? [['strong', 'strong'], ['learning', 'learning'], ['fading', 'fading'], ['weak', 'weak'], ['gap', 'a gap you named']].map(([k, t]) => sw(C.state[k], t)).concat([sw(C.unseen, 'unseen', C.mute)])
      : S.colorBy === 'due' ? [sw(C.no, 'due now'), sw(C.due(.5), 'in a week'), sw(C.ok, 'later'), sw(C.unseen, 'new', C.mute)]
      : [sw(C.unseen, 'unseen', C.mute), ...[1, 3, 5].map(f => sw(C.floor((f - 1) / 4), DEPTHS[f]))]),
      ...(S.colorBy !== 'due' && S.mode !== 'tree' ? [sw(C.bg, 'due', C.no, 2)] : []));
  };
  const showFocus = () => {
    const el = panel.querySelector('#focus-name');
    el.textContent = focus ? `Shows ${focus.name} and what is ${S.steps} ${S.steps > 1 ? 'steps' : 'step'} away. ⎋ stops it.`
      : picked ? `Press E to show only ${picked.name} and its neighbours.` : 'Point at a concept and press E, or find a concept.';
  };
  const relayout = ['mode', 'groupBy', 'spacing', 'floorLo', 'floorHi', 'dueOnly', 'hideUnseen', 'related', 'steps'];
  panel.addEventListener('input', e => {
    const el = e.target, k = el.name; if (!k || k === 'q') return;
    if (k.startsWith('sub:')) S.subs[k.slice(4)] = el.checked;
    else if (el.type === 'checkbox') S[k] = el.checked;
    else if (el.type === 'radio') return setMode(el.value);
    else S[k] = el.tagName === 'SELECT' && !k.startsWith('floor') ? el.value : +el.value;
    if (k === 'floorLo' && S.floorLo > S.floorHi) S.floorHi = S.floorLo;
    if (k === 'floorHi' && S.floorHi < S.floorLo) S.floorLo = S.floorHi;
    save(); show();
    if (k === 'asList') return renderList();
    if (k === 'link' || k === 'push' || k === 'size') { if (STATIC.has(S.mode)) return dirty(); forces(); if (!S.frozen) sim.alpha(.4).restart(); return dirty(); }
    if (k === 'groupBy') {   // the layouts that cluster forget their saved places, so the nodes gather in the new clusters
      delete store.pos.groups; delete store.pins.groups; delete store.cam.groups; save();
      return layout({fresh: true, fit: true});
    }
    if (k === 'steps' && !focus) return;
    if (relayout.includes(k) || k.startsWith('sub:')) layout();
    if (k === 'sizeBy' && !STATIC.has(S.mode)) { forces(); if (!S.frozen) sim.alpha(.2).restart(); }
    dirty();
  });
  const setMode = m => {
    if (m === S.mode) return;
    S.mode = m; save(); show(); hover = null; hideTip();
    const cam = store.cam[m]; layout({fit: !cam}); renderList();
    if (cam) sel.transition().duration(m === 'tree' && !motion ? 0 : 450).call(zoom.transform, d3.zoomIdentity.translate(cam.x, cam.y).scale(cam.k));
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
  // ---- the Tree as a list: the same tree as text, with the status words, for a screen reader and for the find -------
  const outline = root.querySelector('.outline');
  const el = (tag, props = {}, ...kids) => { const e = Object.assign(document.createElement(tag), props); e.append(...kids); return e; };
  const renderList = () => {
    const on = S.mode === 'tree' && S.asList && !!tree;
    outline.hidden = !on; cv.style.visibility = on ? 'hidden' : '';
    if (!on) return outline.replaceChildren();
    hideTip();
    const s = q.value.trim().toLowerCase(), keep = new Set();   // with a find: the concepts that match, and the branches above them
    if (s) tree.byKey.forEach(it => { if (it.kind === 'concept' && (it.name.toLowerCase().includes(s) || it.id.includes(s))) [it.key, ...TT.above(tree, it.key)].forEach(k => keep.add(k)); });
    const line = it => it.kind === 'subject' ? [el('b', {textContent: it.name}), el('small', {textContent: ` ${counted(it)}`})]
      : [el('i', {className: 'dot', style: `background:${C.status[it.status]}${it.status === 'unseen' ? `;box-shadow:inset 0 0 0 1px ${C.mute}` : ''}`, ariaHidden: 'true'}),
         el('a', {href: '/c/' + encodeURIComponent(it.id), textContent: it.name, onclick: ev => { ev.preventDefault(); openC(byId.get(it.id)); }}),
         el('span', {className: 'st st-' + it.status, textContent: ` ${TT.WORDS[it.status]}`}),
         el('small', {textContent: ` · ${DEPTHS[it.floor]} · ${review(byId.get(it.id))}`})];
    const item = it => {
      const kids = it.children.filter(c => !s || keep.has(c.key));
      if (!kids.length) return el('li', {}, ...line(it));
      const d = el('details', {open: !!s || !collapsed.has(it.key)}, el('summary', {}, ...line(it)), el('ul', {}, ...kids.map(item)));
      d.addEventListener('toggle', () => {   // a branch that you close here is closed on the canvas too; a find opens branches but does not save that
        if (q.value.trim() || !d.open === collapsed.has(it.key)) return;
        d.open ? collapsed.delete(it.key) : collapsed.add(it.key); store.collapsed = [...collapsed]; save(); layout();
      });
      return el('li', {}, d);
    };
    const roots = tree.roots.filter(r => !s || keep.has(r.key));
    outline.replaceChildren(el('h2', {textContent: 'The tree as a list'}),
      roots.length ? el('ul', {className: 'tree-list'}, ...roots.map(item)) : el('p', {className: 'hint', textContent: 'No concept has this name.'}));
  };
  q.addEventListener('input', () => { found(); renderList(); });
  q.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); const n = [...(hits || [])][0] || null; const first = list.querySelector('a'); n ? go(n) : first?.click(); }
    if (e.key === 'Escape') { q.value = ''; found(); renderList(); root.focus(); }
  });

  // ---- keys, only while the graph has focus -----------------------------------------------------------------------
  root.addEventListener('keydown', e => {
    if (e.metaKey || e.ctrlKey || e.altKey || e.target === q || e.target.closest('.grip')) return;
    const k = e.code, own = e.target === root;
    if (S.mode === 'tree' && tree && !S.asList && own && /^(Arrow(Up|Down|Left|Right)|Enter|NumpadEnter|Space)$/.test(k)) { treeKey(k); return e.preventDefault(); }
    if (/^Digit[1-5]$/.test(k)) setMode(['force', 'path', 'rings', 'groups', 'tree'][+k[5] - 1]);
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
  // The tools panel: its edge is a grip (core grip.js). The canvas takes the rest of the width, and the observer below fits the graph again.
  abhyasaGrip(root.querySelector('.grip'), {box: panel, key: 'abhyasa.graph.w', bounds: () => [220, root.clientWidth * .45],
                                            apply: w => w == null ? root.style.removeProperty('--gw') : root.style.setProperty('--gw', w + 'px')}).restore();
  // The canvas box can change (the window, the pane, the panel): the nodes fit in it again, with no glide for reduced motion.
  let ready = false;
  new ResizeObserver(() => { resize(); if (ready) fit(motion ? 250 : 0); }).observe(stage); resize();
  const onTheme = () => { if (!root.isConnected) return document.removeEventListener('abhyasa:theme', onTheme); themed(); legend(); dirty(); };   // core.js sends it for a new theme or mode; a host that swaps pages leaves this one behind
  document.addEventListener('abhyasa:theme', onTheme);
  show(); layout(); renderList();
  const cam = store.cam[S.mode];
  if (cam && !picked && Math.abs((cam.w || W) - W) < 40) sel.call(zoom.transform, d3.zoomIdentity.translate(cam.x, cam.y).scale(cam.k));
  else setTimeout(() => { fit(0); if (picked) setTimeout(() => centre(picked), 50); }, tween ? tween.ms : 0);
  ready = true;
  root.focus({preventScroll: true});
  if (motion && (rose.length || fresh.length)) setTimeout(() => { pulse = {t0: performance.now(), ring: new Set(rose), fade: new Set(fresh)}; dirty(); }, tween ? tween.ms : 150);
  window.abhyasaGraph = {nodes, get regions() { return regionList.map(r => ({...r, label: !!captions.find(c => c[2] === r.key)})); }, get captions() { return captions.map(c => c[2]); }, stats, rose: rose.map(n => n.id), fresh: fresh.map(n => n.id), get pulsing() { return !!pulse; }, get t() { return t; }, get mode() { return S.mode; }, get vis() { return vis; },
    get tree() { return tree && {roots: tree.roots.map(r => r.key), cross: tree.cross.length, cursor: cur, collapsed: [...collapsed], rows: TT.rows(tree, collapsed).map(r => r.item.key), labels: lastLabels, toggles: toggles.map(([k, b]) => [k, b]), caps: capHits.map(([k, b]) => [k, b])}; }, get moving() { return !!tween || (!STATIC.has(S.mode) && sim.alpha() > sim.alphaMin()); }};   // a layout with fixed places stops the force simulation part-way, so its alpha says nothing there
})();
