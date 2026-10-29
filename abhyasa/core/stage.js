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
  const GATE_PICK = either(int(0, 63), list(64, int(0, 63)));   // the same at a demo gate, which can have more options
  // The public part of a question: never its `answer` (spec 7.7).
  const ASK = shape({kind: v => ['choice', 'order', 'words', 'scale'].includes(v), q: str(500), options: list(6, str(200)), most: int(1, 500)}, ['kind', 'q']);
  const ANSWER = v => str(200, /^[A-Za-z0-9_.]{1,200}$/)(v) || (isObj(v) && Object.keys(v).length === 1 && Object.hasOwn(v, 'is') && JSON.stringify(v).length <= 2000);
  const ROUND = shape({counts: list(6, N), n: N}, ['n']);

  // One row for each `t`: {fields, need, ok}. `ok` is a check of the whole message, after the fields pass.
  const TYPES = {
    go: {fields: {slide: SLIDE, beat: int(0, 50)}},
    point: {fields: {x: part, y: part, id: ID, off: v => v === true}, need: [['x', 'y'], ['id'], ['off']]},
    // `pick`: the presenter's pick at each done gate, for the verdict in the audience copy only. It is never logged or filed.
    demo: {fields: {slug: str(80, /^[a-z0-9-]{1,80}$/), state: isObj, gates: v => isObj(v) && Object.entries(v).every(([k, x]) => ID(k) && x === 'done'),
                    pick: v => isObj(v) && Object.keys(v).length <= 64 && Object.entries(v).every(([k, x]) => ID(k) && GATE_PICK(x))},
           need: ['slug', 'state', 'gates'], ok: m => !m.pick || Object.keys(m.pick).every(k => Object.hasOwn(m.gates, k))},
    ask: {fields: {slide: SLIDE, ask: orNull(ASK)}},
    result: {fields: {slide: SLIDE, kind: str(8, /^(choice|order|words|scale)$/), rounds: list(2, ROUND), right: orNull(PICK), main: orNull(PICK)}},
    pair: {fields: {on: bool, prompt: str(200)}, need: ['on']},
    // `page`: the page of the primer beside the slide; each window shows that page at its own size (core/talktype.js)
    pane: {fields: {url: orNull(v => str(2048)(v) && isLocal(v)), page: int(0, 19)}, need: ['url']},
    blank: {fields: {on: bool}},
    end: {fields: {}},
    hello: {fields: {}},
    here: {fields: {}},
    join: {fields: {url: orNull(JOIN), code: orNull(CODE)}, ok: m => m.url === null ? m.code === null : m.url.endsWith('/j/' + m.code)},
    room: {fields: {joined: N, answered: N}},
    question: {fields: {text: orNull(str(280))}},
    // The answers of the done gates of one demo of a slide, after R shows the answer of the slide. The slug and the gate id name
    // each gate, so two demos on one slide with the same gate id do not mix. Each is the `answer` of the gate in the spec:
    // `{is: value}`, or a path in the state. Before R no message has an answer, and the room copy of the spec has none.
    answers: {fields: {slide: SLIDE, slug: str(80, /^[a-z0-9-]{1,80}$/), gates: v => isObj(v) && Object.keys(v).length <= 16 && Object.entries(v).every(([k, x]) => ID(k) && ANSWER(x))}},
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

  const DRAWN = ['go', 'ask', 'result', 'pair', 'join', 'room', 'question', 'demo', 'end', 'answers'];
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
  // A snapshot has the input keys (`Rupaka.state`), the gates that are done, and the presenter's pick at each of them, as the index
  // of the option. The audience copy draws the verdict from the pick with `Rupaka.settle`. The pick is for the display only: no
  // window logs it or files it, and `Rupaka.set` and `Rupaka.settle` fire no gate, no rk-predict and no log.
  const same = (x, y) => JSON.stringify(x) === JSON.stringify(y);
  const HOST_API = () => ['state', 'set', 'settle'].every(f => typeof globalThis.Rupaka?.[f] === 'function');
  // The options of gate `id`, from the spec and the state. `Rupaka.settle` takes the option itself, and the host API of rupaka 0.0.4
  // does not give the options of a gate, so this is the one read of the store of the demo.
  // A gate with no `answer` (the copy of a talk's audience window, see room_spec) gives no options, so it shows no verdict:
  // a verdict with no answer would read "It is ." to the room.
  // `gate` gives the block of gate `id` in the spec; `reveal` puts an answer into it, as the gate reads `answer` from its block.
  function gate(host, id) {
    const find = bs => { for (const b of bs || []) { if (b?.type === 'gate' && b.id === id) return b; const g = find(b?.blocks); if (g) return g; } };
    return find(host.rupaka?.spec?.blocks);
  }
  function options(host, id) {
    const s = host.rupaka, g = gate(host, id);
    const os = !g || g.answer == null ? null : Array.isArray(g.options) ? g.options : s.get(g.options?.from);
    return Array.isArray(os) ? os : [];
  }
  function mirror(host) {
    if (!HOST_API()) throw Error('a mirrored demo needs rupaka 0.0.4 or newer: Rupaka.state, Rupaka.set and Rupaka.settle are not there');
    const gates = {}, pick = {}, shown = {}, picked = {}, pokes = [], told = new Set();
    const poke = () => pokes.forEach(f => f());
    // The presenter copy: a gate is done when the page settles its prediction as saved, or when no page catches it.
    host.addEventListener('rk-predict', e => {
      const d = e.detail, id = d?.gate, i = options(host, id).findIndex(o => same(o, d.picked));
      if (typeof id !== 'string') return;
      const done = () => { gates[id] = 'done'; if (i >= 0 && i < 64) pick[id] = i; else delete pick[id]; poke(); };
      const settle = d.settle;
      if (typeof settle === 'function') d.settle = (saved, message) => { settle(saved, message); if (saved) done(); };
      queueMicrotask(() => { if (!e.defaultPrevented) done(); });
    });
    // The presenter copy: a gate that opens again ("Try another") is not done any more, so the audience copy opens it too.
    const prune = () => { for (const id of Object.keys(gates)) if (host.rupaka?.get?.(`gate.${id}`) === 'open') { delete gates[id]; delete pick[id]; } };
    const snapshot = () => { prune(); return {state: Rupaka.state(host), gates: {...gates}, pick: structuredClone(pick)}; };
    function apply(state = {}, done = {}, picks = {}) {
      host.querySelectorAll('.rk-gate').forEach(n => { n.inert = true; });   // the room does not pick in the audience window
      const now = Rupaka.state(host), keys = Object.keys(now).filter(k => Object.hasOwn(state, k) && !same(now[k], state[k]));
      if (keys.length) Rupaka.set(host, Object.fromEntries(keys.map(k => [k, state[k]])));
      // a gate that is not done in the presenter copy now opens again here, with no pick and no answer
      for (const id of Object.keys(shown)) if (done?.[id] !== 'done') reopen(id);
      // only a gate that is done in the presenter copy; an open or a pending gate there does not show here
      for (const id of Object.keys(done || {})) {
        const p = picks?.[id] ?? null, k = JSON.stringify(p);
        if (done[id] !== 'done' || shown[id] === k) continue;
        if (Rupaka.settle(host, id, value(id, p))) { shown[id] = k; picked[id] = p; }
      }
    }
    // rupaka 0.0.4 has no host call that opens a gate, so this does what the gate's own "Try another" does: it marks the gate
    // open in the store and draws the demo again. The blocks after the gate hide, and the verdict goes.
    function reopen(id) {
      const s = host.rupaka;
      if (told.has(id)) { const g = gate(host, id); if (g) delete g.answer; told.delete(id); }
      delete shown[id]; delete picked[id];
      if (s?.st?.gate) { s.st.gate[id] = 'open'; s.set('_', (s.st._ || 0) + 1); }
    }
    // The option of the pick `p` at gate `id`, or null (no verdict) when the copy has no answer or no such option.
    function value(id, p) {
      const os = options(host, id), at = i => Number.isInteger(i) && i >= 0 && i < os.length ? os[i] : undefined;
      const v = Array.isArray(p) ? p.map(at) : at(p);
      return v === undefined || (Array.isArray(v) && v.includes(undefined)) ? null : v;
    }
    // The presenter copy: the answer of each gate that is done, for the `answers` message after R.
    function answers() {
      prune();
      const out = {};
      for (const id of Object.keys(gates)) { const a = gate(host, id)?.answer; if (a != null) out[id] = structuredClone(a); }
      return out;
    }
    // The audience copy: an answer goes into the gate only when the gate is done here; then the verdict of the pick shows.
    function reveal(got = {}) {
      for (const [id, a] of Object.entries(got || {})) {
        const g = gate(host, id);
        if (!g || !Object.hasOwn(shown, id)) continue;
        g.answer = structuredClone(a); told.add(id);
        Rupaka.settle(host, id, value(id, picked[id]));
      }
    }
    // The audience copy, on a move to a new slide: the answers that `reveal` put in go out again, and their verdicts close.
    // A move back gets them again from the presenter, after R.
    function forget() {
      for (const id of told) { const g = gate(host, id); if (g) delete g.answer; Rupaka.settle(host, id, null); }
      told.clear();
    }
    // `fn(snapshot())` on a change: the first change at once, then at most once each 50 ms, and never the same snapshot twice.
    // A change comes from the input events in the demo (the save of mount is the page's own), and from a gate that closes.
    function watch(fn) {
      let t = 0, due = false, last = null, live = true;
      const send = () => { const s = snapshot(), k = JSON.stringify(s); if (k !== last) { last = k; fn(s); } };
      const tick = () => { if (due && live) { due = false; send(); t = setTimeout(tick, 50); } else t = 0; };
      // the check after 50 ms also takes a change that a listener of the demo made after this one
      const on = () => { if (!live) return; if (t) due = true; else { send(); due = true; t = setTimeout(tick, 50); } };
      const EVENTS = ['input', 'change', 'click', 'keyup', 'pointerup', 'pointermove'];
      EVENTS.forEach(n => host.addEventListener(n, on)); document.addEventListener('pointerup', on); pokes.push(on);
      return () => { live = false; clearTimeout(t); EVENTS.forEach(n => host.removeEventListener(n, on)); document.removeEventListener('pointerup', on); };
    }
    return {snapshot, apply, watch, answers, reveal, forget};
  }

  return {V, valid, isLocal, add, types: () => Object.keys(TYPES), channel, audience, presenter, mirror};
})();
if (typeof window !== 'undefined') window.abhyasaStage = abhyasaStage;
if (typeof module !== 'undefined' && module.exports) module.exports = abhyasaStage;
