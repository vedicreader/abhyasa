// The talk editor keys ("Talk plan" in core/keys.py), for the left hand. They are plain keys, as on the Graph, and they work only
// when `html` has the class `talk` and the focus is not in a text box: W and S move the focus, ⇧W and ⇧S move the slide,
// E opens the form that changes the slide, X takes it out (press X again to be sure), Q adds a pause after it. ⌥S is Present (core.js).
if (!window.abhyasaTalk) {
  window.abhyasaTalk = true;
  const root = document.documentElement;
  const rows = () => [...document.querySelectorAll('#deck li.slide')];
  const here = () => document.activeElement?.closest?.('#deck li.slide');
  const inBox = t => t && t.matches && t.matches('textarea, input, select, [contenteditable], [contenteditable] *');
  const url = () => location.pathname.replace(/\/$/, '') + '/slide';
  let want = null, sure = null;   // the slide to focus after a change; the slide that X asks about

  const focus = li => { if (li) { li.focus({focusVisible: true}); li.scrollIntoView({block: 'nearest'}); } };
  const unsure = () => { document.querySelectorAll('#deck .sure').forEach(x => x.remove()); sure = null; };
  function post(li, act, extra = {}) {
    unsure();
    const all = rows(), i = all.indexOf(li);
    want = act === 'drop' ? {at: i} : {sid: li.dataset.sid};
    htmx.ajax('POST', url(), {source: li, values: {sid: li.dataset.sid, act, ...extra}, target: '#deck', swap: 'outerHTML'});
  }
  function move(by) {
    const all = rows(), li = here();
    if (!all.length) return;
    unsure();
    focus(li ? all[Math.max(0, Math.min(all.length - 1, all.indexOf(li) + by))] : all[by > 0 ? 0 : all.length - 1]);
  }
  function edit(li) {
    const d = li.querySelector('details.edit');
    d.open = !d.open;
    if (d.open) d.querySelector('textarea, input:not([type=hidden])')?.focus(); else focus(li);
  }
  function drop(li) {
    if (sure === li) return post(li, 'drop');
    unsure(); sure = li;
    const p = Object.assign(document.createElement('p'), {className: 'sure', textContent: 'Press X again to take out this slide. The walk does not change.'});
    li.appendChild(p);
  }
  const KEYS = {
    KeyW: (li, e) => e.shiftKey ? li && post(li, 'up') : move(-1),
    KeyS: (li, e) => e.shiftKey ? li && post(li, 'down') : move(1),
    KeyE: li => li && edit(li),
    KeyX: li => li && drop(li),
    KeyQ: li => li && post(li, 'pause', {prompt: 'Talk to your neighbour.', secs: 120}),
  };
  document.addEventListener('keydown', e => {
    if (!document.getElementById('deck') || !root.classList.contains('talk') || e.altKey || e.metaKey || e.ctrlKey || e.repeat || inBox(e.target)) return;
    const f = KEYS[e.code];
    if (!f) return;
    e.preventDefault();
    f(here(), e);
  });
  // Esc closes the open form or the X question first, in the capture phase, so it does not go up a level (core.js).
  addEventListener('keydown', e => {
    if (e.key !== 'Escape' || !root.classList.contains('talk')) return;
    const d = document.activeElement?.closest?.('details.edit[open]') || here()?.querySelector('details.edit[open]');
    if (!d && !sure) return;
    e.preventDefault(); e.stopImmediatePropagation();
    if (d) { d.open = false; focus(d.closest('li.slide')); } else unsure();
  }, true);

  // The form sends only the fields that you changed, so a change touches only them (the server keeps the rest).
  document.addEventListener('htmx:configRequest', e => {
    const f = e.detail.elt;
    if (!f.matches || !f.matches('form.slide-edit')) return;
    want = {sid: f.closest('li.slide')?.dataset.sid};
    const p = e.detail.parameters, changed = el => el.type === 'checkbox' || el.type === 'radio' ? el.checked !== el.defaultChecked
      : el.tagName === 'SELECT' ? [...el.options].some(o => o.selected !== o.defaultSelected) : el.value !== el.defaultValue;
    // the question is one group: when one of its fields changed, all of them go, so the options and the right one stay together
    const ask = f.querySelector('.ask-fields');
    if (ask && ![...ask.querySelectorAll('input, select')].some(changed)) ['kind', 'q', 'options', 'answer'].forEach(k => delete p[k]);
    for (const el of f.querySelectorAll('input:not([type=hidden]), textarea, select')) {
      if (el.closest('.ask-fields')) continue;
      if (!changed(el)) delete p[el.name];
      else if (el.type === 'checkbox') p[el.name] = el.checked ? 'on' : 'off';
    }
  });
  // A change that the talk cannot take: the server says why in plain text, and it shows under the slide (as text, never as HTML).
  document.addEventListener('htmx:afterRequest', e => {
    const elt = e.detail.elt, xhr = e.detail.xhr;
    if (xhr.status !== 400 || !elt.closest || !elt.closest('#deck, .talk-top')) return;
    document.querySelectorAll('.req-err').forEach(x => x.remove());
    const p = Object.assign(document.createElement('p'), {className: 'req-err', textContent: xhr.responseText || 'The talk cannot take this change.'});
    (elt.closest('form.slide-edit') || elt.closest('li.slide') || elt.closest('.talk-top') || elt).append(p);
  });
  document.addEventListener('htmx:afterSettle', () => {
    if (!want || !document.getElementById('deck')) return;
    const all = rows();
    focus(want.sid ? all.find(li => li.dataset.sid === want.sid) : all[Math.min(want.at, all.length - 1)]);
    want = null;
  });
}

// The talk windows (spec 9 to 11): the presenter view and the audience view, in step over the stage channel (core/stage.js).
// Both windows draw every slide of the talk, and show only the slide of the place. The presenter posts each move to the server
// first, and sends the stage messages from the reply, so the run log always has the place and a reload of either window finds it.
// In a talk window, ⌥T, ⌥C, ⌥G, ⌥D and / do nothing, so a stray key never leaves a live talk, and Esc never ends the talk.
(() => {
if (window.abhyasaTalkWindows) return;
window.abhyasaTalkWindows = true;
const root = document.documentElement;
if (!root.classList.contains('present') && !root.classList.contains('audience')) return;
addEventListener('keydown', e => {
  if ((e.altKey && ['KeyT', 'KeyC', 'KeyG', 'KeyD'].includes(e.code)) || (e.key === '/' && !e.metaKey && !e.ctrlKey && !e.altKey)) {
    e.preventDefault(); e.stopImmediatePropagation();
  }
}, true);

const LETTERS = 'ABCDEF';
const make = (tag, cls, text) => Object.assign(document.createElement(tag), cls ? {className: cls} : {}, text != null ? {textContent: text} : {});
const sectionsOf = st => [...st.querySelectorAll(':scope > section.stage[data-sid]')];
const sectionOf = (st, sid) => sectionsOf(st).find(s => s.dataset.sid === sid);

// A `lit:` beat: the first match of its words in the passage, in text nodes only, goes in `mark.lit`. `lit:#id` lights a part.
function light(sec, beat) {
  sec.querySelectorAll('mark.lit').forEach(m => m.replaceWith(...m.childNodes));
  sec.querySelectorAll('.lit').forEach(n => n.classList.remove('lit'));
  const p = sec.querySelector('.passage');
  p?.normalize();
  for (const [n, words] of JSON.parse(sec.dataset.lits || '[]')) {
    if (n > beat) continue;
    if (words.startsWith('#')) { sec.querySelectorAll(`[data-rk-id="${CSS.escape(words.slice(1))}"]`).forEach(x => x.classList.add('lit')); continue; }
    if (!p) continue;
    const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
    for (let t; (t = w.nextNode());) {
      const i = t.parentElement.closest('mark.lit') ? -1 : t.data.indexOf(words);
      if (i < 0) continue;
      const hit = t.splitText(i); hit.splitText(words.length);
      const m = make('mark', 'lit'); hit.replaceWith(m); m.append(hit);
      break;
    }
  }
}

// Show beat `beat` of slide `slide`: the parts with `data-at` up to the beat, and the lit words. A new slide closes the room parts.
function show(st, slide, beat) {
  const moved = st.dataset.slide !== slide;
  st.dataset.slide = slide; st.dataset.beat = beat;
  for (const sec of sectionsOf(st)) {
    sec.hidden = sec.dataset.sid !== slide;
    if (sec.hidden) continue;
    sec.querySelectorAll('[data-at]').forEach(p => { p.hidden = +p.dataset.at > beat; });
    light(sec, beat);
  }
  if (moved) { roomPart(st, 'stage-ask').hidden = true; roomPart(st, 'stage-pair').hidden = true; }
}

const roomPart = (st, cls) => st.querySelector(':scope > .' + cls);
const said = n => n.length < 2 ? n.join('') : n.slice(0, -1).join(', ') + ' or ' + n[n.length - 1];
const mark = (kind, k) => kind === 'scale' ? String(k + 1) : LETTERS[k];

// The question on the stage (shots/a4-hands.png), from an `ask` message. All text goes in as text.
function drawAsk(st, m) {
  const box = roomPart(st, 'stage-ask');
  if (!m.ask) { box.hidden = true; box.replaceChildren(); return; }
  const a = m.ask, opts = a.options || [], sec = sectionOf(st, m.slide), n = sectionsOf(st).indexOf(sec) + 1;
  const ol = make('ol', 'ask-opts');
  opts.forEach((o, k) => { const li = make('li'); li.dataset.k = k; li.append(make('span', 'L', mark(a.kind, k)), make('span', 't', o)); ol.append(li); });
  const hint = opts.length ? `Hands up for your answer: ${said(opts.map((_, k) => mark(a.kind, k)))}.` : 'Think of your answer. The presenter asks some of you to say it.';
  box.replaceChildren(make('p', 'crumb', `Ask the room · slide ${n}`), make('h2', 'ask-q', a.q), ...(opts.length ? [ol] : []), make('p', 'hint-line', hint));
  box.dataset.kind = a.kind; box.hidden = false;
}

// The result: the right answer, and the option that most hands chose. With hands there are no counts.
function drawResult(st, m) {
  const box = roomPart(st, 'stage-ask');
  if (box.hidden) return;
  const right = Array.isArray(m.right) ? null : m.right;
  box.querySelectorAll('.ask-opts li').forEach(li => {
    const k = +li.dataset.k;
    li.classList.toggle('right', k === right); li.classList.toggle('most', k === m.main);
    li.querySelector('.tag')?.remove();
    const tags = [k === right ? 'Right answer' : '', k === m.main ? 'Most hands' : ''].filter(Boolean);
    if (tags.length) li.querySelector('.t').append(make('span', 'tag', tags.join(' · ')));
  });
  if (Array.isArray(m.right)) {
    const items = [...box.querySelectorAll('.ask-opts li .t')].map(t => t.firstChild.textContent);
    const ol = make('ol', 'right-order');
    m.right.forEach(i => ol.append(make('li', '', items[i] ?? '')));
    box.querySelector('.right-order')?.remove();
    box.querySelector('.hint-line').replaceWith(make('p', 'hint-line', 'The right order:'), ol);
  } else box.querySelector('.hint-line').textContent = m.main == null ? 'The right answer is lit.' : 'The right answer and the answer of most hands are lit.';
}

function drawPair(st, m) {
  const box = roomPart(st, 'stage-pair');
  box.replaceChildren(make('p', 'pair-say', m.prompt || 'Talk to your neighbour.'));
  box.hidden = !m.on;
}

function drawEnd(st) {
  const box = roomPart(st, 'stage-pair');
  box.replaceChildren(make('h2', 'pair-say', 'Thank you'), make('p', 'crumb', st.dataset.title || ''));
  box.hidden = false;
}

// Wait until rupaka mounts the demo in `host` (its boot runs on load and after each swap).
function mounted(host, fn, left = 200) {
  if (host.rupaka) return fn(host);
  if (left > 0) setTimeout(() => mounted(host, fn, left - 1), 50);
}

// --- the presenter window ----------------------------------------------------------------------------------------------
function presenterView(st) {
  const box = document.getElementById('talk'), base = `/t/${box.dataset.tid}/`, ch = abhyasaStage.channel(box.dataset.channel);
  const $ = id => document.getElementById(id), sayLine = $('say');
  let at = JSON.parse(box.dataset.at), result = null, pair = null, seen = 0, opened = false, goWait = null;
  const slides = sectionsOf(st).map(s => ({sid: s.dataset.sid, n: +s.dataset.n, beats: JSON.parse(s.dataset.beats || '[]')}));
  const idx = () => slides.findIndex(s => s.sid === at.slide);
  const say = t => { sayLine.textContent = t || ''; };
  const app = /AppleWebKit/.test(navigator.userAgent) && !/Safari\//.test(navigator.userAgent);   // Abhyasa.app: one window only (spec 9.4)

  // Each message goes to the audience window and is drawn here too, so the presenter sees what the room sees.
  function send(m, here = true) {
    try { ch.send(m); }
    catch (e) { say(m.t === 'demo' ? 'The audience window cannot show this state of the demo. It is too large.' : 'The audience window did not get the last change.'); }
    if (here) draw(m);
  }
  function draw(m) {
    if (m.t === 'go') show(st, m.slide, m.beat);
    else if (m.t === 'blank') st.classList.toggle('blank', m.on);
    else if (m.t === 'ask') drawAsk(st, m);
    else if (m.t === 'result') drawResult(st, m);
    else if (m.t === 'pair') drawPair(st, m);
  }
  async function post(what, data) {
    const r = await fetch(base + what, {method: 'POST', body: new URLSearchParams(data)}).catch(() => null);
    if (!r) { say('abhyasa did not answer. Try again.'); return null; }
    if (!r.ok) { say(await r.text()); return null; }
    say('');
    return r.json();
  }
  let queue = Promise.resolve();
  const act = f => { queue = queue.then(f).catch(() => {}); return queue; };   // one change at a time, in the order of the keys

  // --- the place
  async function go(slide, beat, extra = {}) {
    const r = await post('at', {slide, beat, ...extra});
    if (!r) return;
    const moved = r.at.slide !== at.slide;
    at = r.at;
    if (moved) { result = null; pair = null; }
    r.msgs.forEach(m => send(m));
    paint();
    if (moved) sendDemo();
    const s = slides[idx()];
    if (s.beats[at.beat - 1] === 'ask' && !at.ask) await ask('open');
  }
  const next = () => act(() => { const i = idx(), s = slides[i]; if (at.beat < s.n) return go(s.sid, at.beat + 1); if (i + 1 < slides.length) return go(slides[i + 1].sid, 1); });
  const back = () => act(() => { const i = idx(); if (at.beat > 1) return go(at.slide, at.beat - 1); if (i > 0) return go(slides[i - 1].sid, slides[i - 1].n); });
  const goTo = n => act(() => slides[n - 1] && go(slides[n - 1].sid, 1));
  const blank = () => act(() => go(at.slide, at.beat, {blank: at.blank ? 0 : 1}));
  const closePane = () => act(() => go(at.slide, at.beat, {pane: ''}));

  // --- the question for the room
  const block = () => document.querySelector(`#ask-card .ask-q[data-sid="${CSS.escape(at.slide)}"]`);
  async function ask(what, extra = {}) {
    const r = await post('ask', {slide: at.slide, act: what, ...extra});
    if (!r) return;
    if (what === 'open') { at.ask = at.slide; result = null; }
    if (what === 'close') { at.ask = null; result = null; if (pair?.on) send(pair = {t: 'pair', on: false, prompt: pair.prompt}); }
    if (what === 'main') document.querySelectorAll('#ask-card [data-hand]').forEach(b => b.classList.toggle('on', +b.dataset.hand === r.main));
    else if (what === 'reveal') { result = r; send(r); const i = idx(); if (r.main != null && !Array.isArray(r.right) && r.right != null && r.main !== r.right) $('rail').children[i]?.classList.add('shaky'); }
    else if (what === 'pair') send(pair = r);
    else send(r);
    paint();
  }
  const askKey = () => act(() => at.ask ? ask('close') : ask('open'));
  const main = () => act(() => !at.ask ? ask('open') : !result ? ask('reveal') : ask('close'));
  const hand = d => {
    const b = block();
    if (!at.ask || !b || d > +b.dataset.n) return false;
    act(() => ask('main', {main: d - 1}));
  };

  // --- the demo: the presenter's copy runs here; the audience copy follows it. The presenter's own pick is not logged.
  st.addEventListener('rk-predict', e => { e.preventDefault(); e.detail.settle(true); });
  const demos = () => [...(sectionOf(st, at.slide)?.querySelectorAll('[data-rupaka][data-demo]') || [])];
  function sendDemo() { demos().forEach(h => h._mirror && send({t: 'demo', slug: h.dataset.demo, ...h._mirror.snapshot()}, false)); }
  st.querySelectorAll('[data-rupaka][data-demo]').forEach(h => mounted(h, () => {
    h._mirror = abhyasaStage.mirror(h);
    h._mirror.watch(s => { if (h.closest('section.stage')?.dataset.sid === at.slide) send({t: 'demo', slug: h.dataset.demo, ...s}, false); });
  }));
  const intoDemo = () => {
    const h = demos().find(x => !x.closest('[hidden]'));
    const c = h?.querySelector('input, button:not([disabled]), select, [tabindex]:not([tabindex="-1"])');
    if (c) c.focus(); else say('This slide has no demo to go into.');
  };
  const esc = () => {
    if (at.ask) return act(() => ask('close'));
    if (document.activeElement?.closest('[data-rupaka]')) { document.activeElement.blur(); return; }
    if (at.pane) return closePane();
  };

  // G, then one or two digits in 1 s: go to a slide by its number.
  function goKey() {
    clearTimeout(goWait?.t);
    goWait = {n: '', t: setTimeout(() => { goWait = null; say(''); }, 1000)};
    say('Go to slide…');
  }
  function digit(d) {
    if (!goWait) return hand(+d);
    goWait.n += d; clearTimeout(goWait.t);
    const done = () => { const n = +goWait.n; goWait = null; say(''); if (n) goTo(n); };
    if (goWait.n.length === 2) return done();
    goWait.t = setTimeout(done, 1000);
  }

  const p = abhyasaStage.presenter(st, ch, {keys: {
    KeyD: next, Space: next, PageDown: next, ArrowRight: next,
    KeyA: back, PageUp: back, ArrowLeft: back,
    KeyQ: askKey,
    KeyR: () => act(() => ask('reveal')),
    KeyE: intoDemo,
    KeyX: () => { const on = p.laser(); say(on ? 'The laser is on. Move the pointer over the slide.' : ''); },
    KeyB: blank,
    KeyG: goKey,
    Escape: esc,
    ...Object.fromEntries([...'123456789'].map(d => [d, () => digit(d)])),
  }});
  $('ask-go').addEventListener('click', main);
  $('pair-go').addEventListener('click', () => act(() => ask('pair', {on: pair?.on ? 0 : 1})));
  document.querySelectorAll('#ask-card [data-hand]').forEach(b => b.addEventListener('click', () => hand(+b.dataset.hand + 1)));

  // --- the audience window: it says hello when it loads, and here every 2 s
  function hello() {
    seen = Date.now(); paint();
    send({t: 'go', slide: at.slide, beat: at.beat}, false);
    send({t: 'blank', on: !!at.blank}, false);
    send({t: 'pane', url: at.pane ? at.pane + '?pane=1&talk=1' : null}, false);
    const b = block();
    if (at.ask && b) send({t: 'ask', ...JSON.parse(b.dataset.ask)}, false);
    if (result) send(result, false);
    if (pair) send(pair, false);
    sendDemo();
  }
  ch.on('hello', hello);
  ch.on('here', () => { seen = Date.now(); paint(); });
  function openAudience() {
    if (opened || seen || app) return;
    opened = true;
    const w = window.open(box.dataset.audience, box.dataset.window, 'popup,width=1280,height=720');
    if (!w) say('The browser did not open the audience window. Use the link at the top.');
  }
  addEventListener('keydown', openAudience, true);
  addEventListener('pointerdown', openAudience, true);

  // --- paint: the parts of the presenter view that follow the place
  function paint() {
    const i = idx(), s = slides[i], sec = sectionOf(st, at.slide);
    const crumb = sec.querySelector('.crumb')?.textContent;
    $('now').textContent = `Now · slide ${i + 1} of ${slides.length}` + (crumb ? ` · ${crumb}` : '');
    $('beats').replaceChildren(`Beat ${at.beat} of ${s.n} `, ...Array.from({length: s.n}, (_, k) => make('i', k < at.beat ? 'on' : '')));
    [...$('rail').children].forEach((r, k) => { r.classList.toggle('done', k < i); r.classList.toggle('now', k === i); });
    for (const id of ['notes', 'next']) [...$(id).children].forEach(n => { n.hidden = n.dataset.sid !== at.slide; });
    const card = $('ask-card'), b = block();
    card.querySelectorAll('.ask-q').forEach(q => { q.hidden = q !== b; });
    card.querySelector('.none').hidden = !!b;
    card.querySelector('.acts').hidden = !b;
    card.classList.toggle('open', !!at.ask); card.classList.toggle('shown', !!result);
    const go = $('ask-go');
    go.querySelector('.act').textContent = !at.ask ? 'Ask the room' : !result ? 'Show the answer' : 'Close the question';
    go.querySelector('kbd').textContent = !at.ask ? 'Q' : !result ? 'R' : 'Q';
    $('pair-go').hidden = !result;
    $('pair-go').textContent = pair?.on ? 'End the talk with a neighbour' : 'Talk to your neighbour';
    if (!at.ask) card.querySelectorAll('[data-hand]').forEach(h => h.classList.remove('on'));
    st.classList.toggle('blank', !!at.blank);
    const live = seen && Date.now() - seen < 5000;
    $('aud-live').hidden = !live; $('aud-gone').hidden = !seen || live || app; $('aud-open').hidden = !!seen || app; $('aud-app').hidden = !app;
  }
  if (app) { $('app-url').textContent = location.href; $('app-copy').addEventListener('click', () => navigator.clipboard?.writeText(location.href).then(() => say('Copied.'))); }
  // the clock: the time used of the slot, and the minutes of the slides that are left (this slide too)
  const clock = $('clock'), started = +clock.dataset.started;
  const tick = () => {
    const secs = Math.max(0, Math.floor(Date.now() / 1000 - started));
    clock.textContent = `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`;
    const left = [...$('rail').children].slice(idx()).reduce((a, r) => a + +r.dataset.mins, 0);
    $('left').textContent = `About ${left} min of slides left`;
    paint();
  };
  tick(); setInterval(tick, 1000);
  if (at.ask) { const b = block(); if (b) drawAsk(st, {t: 'ask', ...JSON.parse(b.dataset.ask)}); }
  show(st, at.slide, at.beat);
}

// --- the audience window -----------------------------------------------------------------------------------------------
function audienceView(st) {
  const ch = abhyasaStage.channel(st.dataset.channel), note = document.getElementById('keys-note');
  const mirrors = new Map();
  st.querySelectorAll('[data-rupaka][data-demo]').forEach(h => mounted(h, () => { const m = abhyasaStage.mirror(h); m.apply({}, {}); mirrors.set(h, m); }));
  function draw(m) {
    if (m.t === 'go') show(st, m.slide, m.beat);
    else if (m.t === 'ask') drawAsk(st, m);
    else if (m.t === 'result') drawResult(st, m);
    else if (m.t === 'pair') drawPair(st, m);
    else if (m.t === 'end') drawEnd(st);
    else if (m.t === 'demo') {
      const sec = sectionOf(st, st.dataset.slide);
      sec?.querySelectorAll(`[data-rupaka][data-demo="${CSS.escape(m.slug)}"]`).forEach(h => mirrors.get(h)?.apply(m.state, m.gates));
    }
  }
  abhyasaStage.audience(st, {ch, draw, fade: +st.dataset.fade || 1500, title: st.dataset.title});
  show(st, st.dataset.slide, +st.dataset.beat);
  // F fills the screen. Another key shows for 3 s that the keys work in the presenter window.
  let t = 0;
  const keys = {
    KeyF: () => document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen?.().catch(() => {}),
  };
  addEventListener('keydown', e => {
    if (e.repeat || ['Shift', 'Alt', 'Meta', 'Control', 'Escape'].includes(e.key)) return;
    if (!e.altKey && !e.metaKey && !e.ctrlKey && keys[e.code]) { e.preventDefault(); return keys[e.code](); }
    if (e.metaKey || e.ctrlKey) return;
    note.hidden = false; clearTimeout(t); t = setTimeout(() => { note.hidden = true; }, 3000);
  });
}
const start = () => (root.classList.contains('present') ? presenterView : audienceView)(document.getElementById('stage'));
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
