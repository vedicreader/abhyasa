// The Tree layout of the graph, as pure functions: no page, no d3, so node tests them (tests/test_graph_tree.py).
// Each subject is a root. A concept sits under the prereq in its own subject that is deepest (the longest chain of
// prereqs before it); its other prereqs are cross-links. A cycle of prereqs does not loop and drops no concept.
(function (root) {
  const WORDS = {unseen: 'not started', learning: 'under way', mastered: 'mastered', due: 'review due'};
  const ORDER = ['unseen', 'learning', 'mastered', 'due'];
  // The due rule of the graph (`isDue` in graph.js): a seen concept whose review time has come. Mastered is depth `ready` or more.
  const status = (n, ready, now) => n.seen && n.due && n.due <= now ? 'due' : (n.floor || 0) >= ready ? 'mastered' : (n.floor || 0) > 0 ? 'learning' : 'unseen';
  const byName = (a, b) => a.name.localeCompare(b.name) || (a.key < b.key ? -1 : a.key > b.key ? 1 : 0);
  const end = x => x && typeof x === 'object' ? x.id : x;   // a link end is an id, or a node after d3 or graph.js has joined it

  function build(nodes, links, {ready = 3, now = Date.now() / 1000} = {}) {
    const by = new Map(nodes.map(n => [n.id, n])), pre = new Map(), out = new Map();
    nodes.forEach(n => { pre.set(n.id, []); out.set(n.id, []); });
    for (const l of links) {
      if (l.kind !== 'prereq' && l.kind !== 'gap') continue;
      const s = end(l.source), t = end(l.target);
      if (!by.has(s) || !by.has(t) || s === t || pre.get(t).includes(s)) continue;
      pre.get(t).push(s); out.get(s).push(t);
    }
    // The depth of each concept, in the order of Kahn's sort. When only cycles are left, the first concept by name takes
    // its depth from the prereqs that have one, and the sort goes on; each pass settles one concept, so it ends.
    const ids = nodes.map(n => n.id).sort((a, b) => by.get(a).name.localeCompare(by.get(b).name) || (a < b ? -1 : 1));
    const left = new Map(ids.map(i => [i, pre.get(i).length])), depth = new Map(), q = ids.filter(i => !left.get(i)).reverse();
    const settle = i => {
      depth.set(i, Math.max(-1, ...pre.get(i).filter(p => depth.has(p)).map(p => depth.get(p))) + 1);
      for (const m of out.get(i)) if (!depth.has(m)) { left.set(m, left.get(m) - 1); if (!left.get(m)) q.push(m); }
    };
    while (depth.size < ids.length) { const i = q.length ? q.pop() : ids.find(j => !depth.has(j)); if (!depth.has(i)) settle(i); }

    const byKey = new Map(), roots = [], cross = [];
    for (const s of [...new Set(nodes.map(n => n.subject || 'general'))]) {
      const r = {key: 's:' + s, kind: 'subject', name: s, subject: s, parent: null, children: [], size: 0, counts: {unseen: 0, learning: 0, mastered: 0, due: 0}};
      byKey.set(r.key, r); roots.push(r);
    }
    for (const n of nodes) {
      const subject = n.subject || 'general';
      byKey.set(n.id, {key: n.id, kind: 'concept', id: n.id, name: n.name, subject, floor: n.floor || 0, due: n.due ?? null, seen: n.seen || 0,
                       depth: depth.get(n.id), status: status(n, ready, now), parent: null, children: [], size: 0});
    }
    for (const n of nodes) {
      const it = byKey.get(n.id), d = it.depth;
      // the parent: the deepest prereq in the same subject that sits before this concept; ties go by name
      const ok = pre.get(n.id).map(p => byKey.get(p)).filter(p => p.subject === it.subject && p.depth < d).sort((a, b) => b.depth - a.depth || byName(a, b));
      const parent = ok[0] || byKey.get('s:' + it.subject);
      it.parent = parent.key; parent.children.push(it);
      for (const p of pre.get(n.id)) if (p !== parent.key) cross.push({source: p, target: n.id});
    }
    const sum = it => { it.children.sort(byName); it.size = it.children.reduce((a, c) => a + 1 + sum(c), 0); return it.size; };
    roots.sort(byName).forEach(r => { sum(r); walk(r, it => { if (it.kind === 'concept') r.counts[it.status]++; }); });
    return {roots, byKey, cross, ready};
  }

  function walk(it, f) { const stack = [it]; while (stack.length) { const x = stack.pop(); f(x); for (let i = x.children.length - 1; i >= 0; i--) stack.push(x.children[i]); } }

  // The rows that show, in order: each item with its depth (a root is 0). The items under a closed branch do not show.
  function rows(tree, collapsed = new Set()) {
    const out = [], go = (it, d) => { out.push({item: it, depth: d}); if (!collapsed.has(it.key)) it.children.forEach(c => go(c, d + 1)); };
    tree.roots.forEach(r => go(r, 0));
    return out;
  }

  // The arrow keys: `parent`, `child` (the first one, when the branch is open), `prev` and `next` (the siblings). With
  // nowhere to go, the key stays; with no key yet, it goes to the first root.
  function move(tree, key, dir, collapsed = new Set()) {
    const it = key != null && tree.byKey.get(key);
    if (!it) return tree.roots[0]?.key ?? null;
    if (dir === 'parent') return it.parent ?? it.key;
    if (dir === 'child') return !collapsed.has(it.key) && it.children.length ? it.children[0].key : it.key;
    const sibs = it.parent ? tree.byKey.get(it.parent).children : tree.roots, i = sibs.indexOf(it);
    const j = dir === 'prev' ? i - 1 : dir === 'next' ? i + 1 : i;
    return (sibs[j] || it).key;
  }

  // The open branches above an item, so that a find or a key can show an item that a closed branch hides.
  function above(tree, key) { const out = []; let it = tree.byKey.get(key); while (it && it.parent) { out.push(it.parent); it = tree.byKey.get(it.parent); } return out; }

  const api = {WORDS, ORDER, status, build, rows, move, above, walk};
  if (typeof module === 'object' && module.exports) module.exports = api; else root.abhyasaTree = api;
})(typeof self !== 'undefined' ? self : this);
