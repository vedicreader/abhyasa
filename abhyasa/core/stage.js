// The stage: the presenter window and the audience window of a talk, in step over a BroadcastChannel (core/stage.py tells the rest).
// The channel name has the talk id and the random run key, so two talks or two runs never mix, and an old audience window does
// not drive a new run. Only windows of the same origin can join a BroadcastChannel.
// Each message is small data with `v: 1`. `valid` checks it against the table TYPES: a field that is not in the table for its
// `t` makes it invalid. The sender throws on an invalid message, so a bug shows in tests; the receiver drops one with no error.
// The channel carries data only. Each window draws its own slides, and text from a message goes in with textContent only.
// This file binds no key by itself: the host gives `presenter` its keys, as an object of key name -> function.
var abhyasaStage = globalThis.abhyasaStage || (() => {
  const V = 1, MOST = 65536, DEEP = 8;
  const isLocal = u => typeof u === 'string' && u.startsWith('/') && !u.startsWith('//') && !/[\x00-\x1f\x7f\\]/.test(u);   // as is_local in pane.py
  const isObj = v => v !== null && typeof v === 'object' && !Array.isArray(v) && [Object.prototype, null].includes(Object.getPrototypeOf(v));

  // Data that JSON can carry, at most DEEP levels down and with at most `left` parts: structured clone can carry more (a Map, a loop).
  // No key anywhere is a name that can change a prototype, so code that copies a part of a message stays safe.
  const PROTO = ['__proto__', 'constructor', 'prototype'];
  function plain(v, depth = 0, left = {n: 40000}) {
    if (--left.n < 0 || depth > DEEP) return false;
    if (v === null || typeof v === 'string' || typeof v === 'boolean') return true;
    if (typeof v === 'number') return Number.isFinite(v);
    if (Array.isArray(v)) return Object.getPrototypeOf(v) === Array.prototype && v.every(x => plain(x, depth + 1, left));
    return isObj(v) && Object.keys(v).every(k => !PROTO.includes(k) && plain(v[k], depth + 1, left));
  }

  // The field rules. Each one is a function of the value that gives true or false.
  const str = (most, re) => v => typeof v === 'string' && v.length <= most && (!re || re.test(v));
  const int = (lo, hi) => v => Number.isInteger(v) && v >= lo && v <= hi;
  const part = v => typeof v === 'number' && v >= 0 && v <= 1;   // NaN fails each test
  const bool = v => typeof v === 'boolean';
  const orNull = f => v => v === null || f(v);
  const list = (most, f) => v => Array.isArray(v) && v.length <= most && v.every(f);
  const either = (...fs) => v => fs.some(f => f(v));
  // `need`: no value means each field must be there; a list of names means those must be there and the others may be;
  // a list of lists means the names must be exactly one of the lists.
  function fits(v, fields, need, keys = Object.keys(v)) {
    if (!keys.every(k => Object.hasOwn(fields, k) && fields[k](v[k]))) return false;
    if (!need) return keys.length === Object.keys(fields).length;
    if (Array.isArray(need[0])) return need.some(n => n.length === keys.length && n.every(k => Object.hasOwn(v, k)));
    return need.every(k => Object.hasOwn(v, k));
  }
  const shape = (fields, need) => v => isObj(v) && fits(v, fields, need);

  const SLIDE = str(5, /^s[0-9]{1,4}$/), ID = str(64, /^[A-Za-z0-9_-]{1,64}$/), N = int(0, 1e6);
  const CODE = str(6, /^[A-HJKMNP-Z2-9]{6}$/);
  const JOIN = str(64, /^http:\/\/(10\.\d{1,3}|172\.(1[6-9]|2\d|3[01])|192\.168|127\.0)\.\d{1,3}\.\d{1,3}:\d{2,5}\/j\/[A-HJKMNP-Z2-9]{6}$/);
  // At most 6 options, as in a talk now. By ruling, Option C adds its own types with their own limits through `add`; these stay.
  const PICK = either(int(0, 5), list(6, int(0, 5)));   // an option, or the options in order
  // The public part of a question: never its `answer` (spec 7.7).
  const ASK = shape({kind: v => ['choice', 'order', 'words', 'scale'].includes(v), q: str(500), options: list(6, str(200)), most: int(1, 500)}, ['kind', 'q']);
  const ROUND = shape({counts: list(6, N), n: N}, ['n']);

  // One row for each `t`: {fields, need, ok}. `ok` is a check of the whole message, after the fields pass.
  const TYPES = {
    go: {fields: {slide: SLIDE, beat: int(0, 50)}},
    point: {fields: {x: part, y: part, id: ID, off: v => v === true}, need: [['x', 'y'], ['id'], ['off']]},
    demo: {fields: {slug: str(80, /^[a-z0-9-]{1,80}$/), state: isObj, gates: v => isObj(v) && Object.entries(v).every(([k, x]) => ID(k) && x === 'done')}},
    ask: {fields: {slide: SLIDE, ask: orNull(ASK)}},
    result: {fields: {slide: SLIDE, kind: str(8, /^(choice|order|words|scale)$/), rounds: list(2, ROUND), right: orNull(PICK), main: orNull(PICK)}},
    pair: {fields: {on: bool, prompt: str(200)}, need: ['on']},
    pane: {fields: {url: orNull(v => str(2048)(v) && isLocal(v))}},
    blank: {fields: {on: bool}},
    end: {fields: {}},
    hello: {fields: {}},
    here: {fields: {}},
    join: {fields: {url: orNull(JOIN), code: orNull(CODE)}, ok: m => m.url === null ? m.code === null : m.url.endsWith('/j/' + m.code)},
    room: {fields: {joined: N, answered: N}},
    question: {fields: {text: orNull(str(280))}},
  };

  function valid(m) {
    if (!isObj(m) || m.v !== V || typeof m.t !== 'string' || !Object.hasOwn(TYPES, m.t) || !plain(m)) return false;
    if (JSON.stringify(m).length > MOST) return false;
    const row = TYPES[m.t], keys = Object.keys(m).filter(k => k !== 'v' && k !== 't');
    return fits(m, row.fields, row.need, keys) && (!row.ok || row.ok(m));
  }

  // A later task adds a message type here (and to STAGE_TYPES in stage.py). It never changes a type that is there.
  function add(t, fields, need, ok) {
    if (!/^[a-z]{1,16}$/.test(t) || Object.hasOwn(TYPES, t)) throw Error('cannot add the stage message type ' + t);
    if (!isObj(fields) || !Object.entries(fields).every(([k, f]) => /^[a-z][A-Za-z0-9]{0,31}$/.test(k) && typeof f === 'function'))
      throw Error('the fields of a stage message type must be names with rule functions');
    if (ok !== undefined && typeof ok !== 'function') throw Error('the whole-message check must be a function');
    // a frozen copy, so a later change to the caller's objects cannot change the type
    const copy = Object.freeze(Object.assign(Object.create(null), fields));
    const needs = need === undefined ? undefined : Object.freeze(need.map(n => Array.isArray(n) ? Object.freeze([...n]) : n));
    TYPES[t] = Object.freeze({fields: copy, need: needs, ok});
  }

  function channel(name) {
    if (typeof name !== 'string' || !name) throw Error('a stage channel needs a name');
    const bc = new BroadcastChannel('abhyasa-stage:' + name), fns = Object.create(null);
    bc.onmessage = e => { if (valid(e.data)) for (const f of fns[e.data.t] || []) f(e.data); };
    return {
      send(msg) {
        const m = Object.assign({v: V}, msg);
        if (!valid(m)) throw Error('not a valid stage message');
        bc.postMessage(m);
      },
      on(t, fn) {
        if (!Object.hasOwn(TYPES, t)) throw Error('not a stage message type: ' + t);
        (fns[t] ||= []).push(fn);
        return () => { fns[t] = fns[t].filter(f => f !== fn); };
      },
      close() { bc.close(); for (const t in fns) delete fns[t]; },
    };
  }

  const DRAWN = ['go', 'ask', 'result', 'pair', 'join', 'room', 'question', 'demo', 'end'];
  const child = (el, cls, tag = 'div') => el.querySelector(':scope > .' + cls) || el.appendChild(Object.assign(document.createElement(tag), {className: cls}));

  // The audience window: the laser dot, the lit id, the blank screen and the side pane. `draw(msg)` draws the rest.
  function audience(el, {ch, draw = () => {}, fade = 1500, title} = {}) {
    const dot = child(el, 'stage-dot'), blank = child(el, 'stage-blank');
    dot.setAttribute('aria-hidden', 'true');
    blank.textContent = title ?? el.dataset.title ?? '';
    let dotT = 0, litT = 0, lit = null;
    const hide = () => { clearTimeout(dotT); dot.classList.remove('on'); };
    const unlight = () => { clearTimeout(litT); lit?.classList.remove('lit'); lit = null; };
    const pane = url => {
      let f = el.querySelector(':scope > iframe.stage-pane');
      if (!isLocal(url)) { f?.remove(); el.classList.remove('beside'); return; }
      f ||= child(el, 'stage-pane', 'iframe');
      f.title = 'Side pane';
      if (f.getAttribute('src') !== url) f.setAttribute('src', url);
      el.classList.add('beside');
    };
    const offs = [
      ch.on('point', m => {
        if (m.off) return hide();
        if (m.id) {
          unlight();
          lit = el.querySelector('#' + CSS.escape(m.id));
          if (lit) { lit.classList.add('lit'); litT = setTimeout(unlight, 3000); }
          return;
        }
        dot.style.left = m.x * 100 + '%'; dot.style.top = m.y * 100 + '%';
        dot.classList.add('on'); clearTimeout(dotT); dotT = setTimeout(hide, fade);
      }),
      ch.on('blank', m => el.classList.toggle('blank', m.on)),
      ch.on('pane', m => pane(m.url)),
      ...DRAWN.map(t => ch.on(t, draw)),
    ];
    ch.send({t: 'hello'});
    const beat = setInterval(() => ch.send({t: 'here'}), 2000);
    return {stop() { clearInterval(beat); hide(); unlight(); offs.forEach(f => f()); }};
  }

  // The presenter window: the talk keys, and the laser from the pointer over `el`.
  // A key works only when `html` has the class `talk`, the focus is not in a text box, and the focus is not in the demo
  // (`[data-rupaka]`), where the demo's own keys win; Esc still comes here, so it can leave the demo. ⌥, ⌘ and Ctrl keys go on
  // to core.js. The name of a key is its `e.code`, with `Shift+` before it when Shift is down; a digit is its `e.key`.
  // The listener is on `document` in the capture phase, so the talk's Esc comes before the Esc of core.js. A function that
  // gives false lets the key go on.
  function presenter(el, ch, {keys = {}} = {}) {
    const root = document.documentElement, box = 'textarea, input, select, [contenteditable]:not([contenteditable="false"])';
    let laser = false, frame = 0, at = null;
    const onKey = e => {
      if (!root.classList.contains('talk') || e.repeat || e.metaKey || e.ctrlKey || e.altKey || e.isComposing) return;   // a held key does not skip beats
      const a = document.activeElement;
      if (a && (a.matches(box) || a.isContentEditable)) return;
      if (e.key !== 'Escape' && a?.closest('[data-rupaka]')) return;
      const name = /^[0-9]$/.test(e.key) ? e.key : (e.shiftKey ? 'Shift+' : '') + e.code, fn = Object.hasOwn(keys, name) && keys[name];
      if (typeof fn !== 'function' || fn(e) === false) return;
      e.preventDefault(); e.stopPropagation();   // so a focused button or link does not also click on Space
    };
    const clamp = v => Math.round(Math.min(1, Math.max(0, v)) * 1e4) / 1e4;
    const send = () => { frame = 0; if (laser && at) ch.send({t: 'point', x: at[0], y: at[1]}); };
    const move = e => {
      if (!laser) return;
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) return;
      at = [clamp((e.clientX - r.left) / r.width), clamp((e.clientY - r.top) / r.height)];
      frame ||= requestAnimationFrame(send);
    };
    const off = () => { cancelAnimationFrame(frame); frame = 0; at = null; };
    const leave = () => { off(); if (laser) ch.send({t: 'point', off: true}); };
    document.addEventListener('keydown', onKey, true);
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerleave', leave);
    return {
      laser(on = !laser) {
        if (laser && !on) leave();
        laser = !!on; el.classList.toggle('laser', laser);
        return laser;
      },
      stop() {
        if (laser) leave();
        laser = false; off(); el.classList.remove('laser');
        document.removeEventListener('keydown', onKey, true);
        el.removeEventListener('pointermove', move); el.removeEventListener('pointerleave', leave);
      },
    };
  }

  // The mirrored demo (spec 10): the same rupaka spec in the two windows. The presenter copy gives `snapshot` and `watch`, and the
  // talk page sends each snapshot as a `demo` message. The audience copy takes it with `apply`, and sends nothing back.
  // A snapshot has only the input keys (the keys of `spec.state`) and the gates that are done: never a pick or a verdict.
  // The one feature check: when rupaka has `Rupaka.set` and `Rupaka.settle` (the ask of Task 4), `apply` uses them.
  // Until then it uses the rupaka 0.0.3 store on `host.rupaka`, and the audience copy shows the blocks after a gate but no verdict.
  const ownSet = () => typeof globalThis.Rupaka?.set === 'function' && typeof Rupaka.settle === 'function';
  const same = (x, y) => JSON.stringify(x) === JSON.stringify(y);
  function mirror(host) {
    const store = () => host.rupaka, inputs = () => Object.keys(store().spec.state || {});
    function snapshot() {
      const st = store().st, state = {}, gates = {};
      for (const k of inputs()) state[k] = structuredClone(st[k]);
      for (const [id, g] of Object.entries(st.gate || {})) if (g === 'done') gates[id] = 'done';
      return {state, gates};
    }
    function apply(state = {}, gates = {}) {
      const s = store(), st = s.st, keys = inputs().filter(k => Object.hasOwn(state, k));
      // only a gate of this spec that is not done yet; an open or a pending gate in the presenter copy does not show here
      const fresh = Object.keys(gates).filter(id => gates[id] === 'done' && Object.hasOwn(st.gate, id) && st.gate[id] !== 'done');
      host.querySelectorAll('.rk-gate').forEach(n => { n.inert = true; });   // the room does not pick in the audience window
      if (ownSet()) {
        if (keys.length) Rupaka.set(host, Object.fromEntries(keys.map(k => [k, state[k]])));
        fresh.forEach(id => Rupaka.settle(host, id, null));
        return;
      }
      for (const k of keys) if (!same(st[k], state[k])) s.set(k, structuredClone(state[k]));
      if (!fresh.length) return;
      fresh.forEach(id => { st.gate[id] = 'done'; });
      s.set('_', (st._ || 0) + 1);   // one draw, so the blocks after the gates show
    }
    // `fn(snapshot())` on a change: the first change at once, then at most once each 50 ms, and never the same snapshot twice.
    function watch(fn) {
      let t = 0, due = false, last = null, live = true;
      const send = () => { const s = snapshot(), k = JSON.stringify(s); if (k !== last) { last = k; fn(s); } };
      const tick = () => { if (due && live) { due = false; send(); t = setTimeout(tick, 50); } else t = 0; };
      store().on(() => { if (!live) return; if (t) due = true; else { send(); t = setTimeout(tick, 50); } });
      return () => { live = false; clearTimeout(t); };
    }
    return {snapshot, apply, watch};
  }

  return {V, valid, isLocal, add, types: () => Object.keys(TYPES), channel, audience, presenter, mirror};
})();
if (typeof window !== 'undefined') window.abhyasaStage = abhyasaStage;
if (typeof module !== 'undefined' && module.exports) module.exports = abhyasaStage;
