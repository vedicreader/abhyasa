// The talk editor. The keys, the drag, the live fields and ⌘Z are in core/edit.js ("Talk plan" in core/keys.py). Here: Add a slide and
// Add a pause go after the slide that had the focus last, W or S with the focus on no row goes into the list, R opens the row and puts the focus in "Rewrite this slide",
// the beats keep the focus when they change, words selected in the passage go in the Light box, the title of a row follows its box,
// and a change that the talk cannot take shows its problem under the row.
if (!window.abhyasaTalk) {
  window.abhyasaTalk = true;
  const rowOf = el => el?.closest?.('#deck > li.edit-row');
  let last = null;   // the id of the slide that had the focus last
  document.addEventListener('focusin', e => { const li = rowOf(e.target); if (li) last = li.dataset.id; });
  document.addEventListener('htmx:configRequest', e => {
    const el = e.detail.elt;
    if (el?.dataset?.after) {
      const all = [...document.querySelectorAll('#deck > li.edit-row')];
      const sid = e.detail.parameters.sid = (all.find(li => li.dataset.id === last) || all.at(-1))?.dataset.id || '';
      if (sid) el._focus = {list: 'deck', id: sid};   // a new slide takes the focus in its title (edit.js)
      return;
    }
    // `el._focus` names the row that gets the focus after the answer (edit.js)
    // a change to a beat keeps the focus on the beats: a removed beat gives it to the beat after it, or to the slide when none is left
    const chip = el?.closest?.('ol.beats > li.edit-row');
    if (chip) {   // a move of the beat itself (edit.js) keeps its own focus
      if (el === chip) return;
      const next = chip.nextElementSibling || chip.previousElementSibling;
      el._focus = {id: next?.dataset?.id || rowOf(chip)?.dataset.id || ''};
      return;
    }
    // a change in a row puts the focus back on that row after the swap; a removed row gives it to the row after it
    const li = rowOf(el);
    if (li && el !== li && !el.dataset?.live && el.getAttribute('hx-swap') !== 'none') {
      const act = e.detail.parameters.act, next = li.nextElementSibling?.matches('li.edit-row') ? li.nextElementSibling : li.previousElementSibling;
      el._focus = {list: 'deck', id: act === 'drop' ? next?.dataset?.id || '' : li.dataset.id};
    }
  });
  // With the focus on no row (as when the page opens), S goes to the first slide and W to the last, so the keys of the list work at once.
  document.addEventListener('keydown', e => {
    const a = document.activeElement;
    if (e.defaultPrevented || e.altKey || e.metaKey || e.ctrlKey || e.shiftKey || (a && a !== document.body)) return;
    if (e.code !== 'KeyW' && e.code !== 'KeyS') return;
    const all = document.querySelectorAll('#deck > li.edit-row');
    if (!all.length) return;
    e.preventDefault(); all[e.code === 'KeyS' ? 0 : all.length - 1].focus();
  });
  document.addEventListener('click', e => {
    const b = e.target.closest?.('[data-rewrite]'), li = rowOf(b);
    if (!li) return;
    const d = li.querySelector(':scope > details');
    if (d) d.open = true;
    li.querySelector('form.rewrite input[name=text]')?.focus();
  });
  // Esc on a beat gives the focus back to its slide, so it never goes up a level (core.js).
  document.addEventListener('keydown', e => {
    const chip = e.target?.closest?.('ol.beats > li.edit-row');
    if (e.key !== 'Escape' || e.defaultPrevented || !chip || e.target !== chip) return;
    e.preventDefault(); rowOf(chip)?.focus();
  }, true);
  // Words that you select in the passage of an open row go in its Light box, so a Light beat lights exactly them.
  document.addEventListener('selectionchange', () => {
    const sel = getSelection(), node = sel?.anchorNode, q = (node?.nodeType === 3 ? node.parentElement : node)?.closest?.('#deck blockquote[data-pick]');
    const words = sel?.toString().trim(), box = rowOf(q)?.querySelector('input[data-light]');
    if (q && words && box && q.contains(sel.focusNode)) { box.value = words; rowOf(q).querySelector('details.add-beat').open = true; }
  });
  document.addEventListener('input', e => {
    const box = e.target, li = rowOf(box);
    if (li && box.matches?.('input[name=title][data-live]')) { const t = li.querySelector(':scope > .head .ttl'); if (t) t.textContent = box.value; }
  });
  // A change that the talk cannot take: the server says why in plain text, and it shows under the row (as text, never as HTML).
  document.addEventListener('htmx:afterRequest', e => {
    const elt = e.detail.elt, xhr = e.detail.xhr;
    if (!elt.closest || !elt.closest('#deck, .talk-top')) return;
    if (xhr.status !== 400) { if (xhr.status < 300) rowOf(elt)?.querySelectorAll('.req-err').forEach(x => x.remove()); return; }
    document.querySelectorAll('.req-err').forEach(x => x.remove());
    const p = Object.assign(document.createElement('p'), {className: 'req-err', role: 'alert', textContent: xhr.responseText || 'The talk cannot take this change.'});
    (rowOf(elt)?.querySelector('.fields') || rowOf(elt) || elt.closest('.talk-top') || elt).append(p);
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
  const typing = e.target?.matches?.('textarea, input, select, [contenteditable]:not([contenteditable="false"])');
  if ((e.altKey && ['KeyT', 'KeyQ', 'KeyR', 'KeyG', 'KeyC', 'KeyD', 'Digit1', 'Digit2', 'Digit3'].includes(e.code)) || (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey && !e.altKey)) {
    e.preventDefault(); e.stopImmediatePropagation();
  }
}, true);

const LETTERS = 'ABCDEF';
const PANE = /^\/w\/[a-z0-9-]{1,48}\/[0-9]{1,3}$/;   // the only page that the side pane of a talk opens: a walk step (spec 9.2)
const PANE_URL = /^\/w\/[a-z0-9-]{1,48}\/[0-9]{1,3}\?pane=1&talk=1$/;   // the same step, in the talk type, and nothing more
const paneOK = u => u === null || (typeof u === 'string' && PANE_URL.test(u));
const make = (tag, cls, text) => Object.assign(document.createElement(tag), cls ? {className: cls} : {}, text != null ? {textContent: text} : {});
const maths = (tag, cls, text) => abhyasaMath(make(tag, cls), text);   // text with its maths drawn (core.js), never as HTML
const sectionsOf = st => [...st.querySelectorAll(':scope > section.stage[data-sid]')];
const sectionOf = (st, sid) => sectionsOf(st).find(s => s.dataset.sid === sid);

// A `lit:` beat: the first match of its words in the passage, in text nodes only and not in maths, goes in `mark.lit`. `lit:#id` lights a part.
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
      const i = t.parentElement.closest('mark.lit, .math, .katex') ? -1 : t.data.indexOf(words);   // never inside drawn maths
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
    fitPoints(sec);
  }
  if (moved) { roomPart(st, 'stage-ask').hidden = true; roomPart(st, 'stage-pair').hidden = true; }
}

// The points fit the slide, as a passage does in the talk type (core/talktype.js): when they do not fit, their type gets smaller,
// down to 22/28 of its size. Each window does this at its own size.
const POINTS_FLOOR = 22 / 28;
function fitPoints(sec) {
  const p = sec.querySelector('.body > .points'), body = p?.parentElement;
  if (!p || p.hidden) return;
  p.style.removeProperty('--pts');
  for (let s = 1; body.scrollHeight > body.clientHeight + 1 && s > POINTS_FLOOR + .001;) { s = Math.max(POINTS_FLOOR, s - .05); p.style.setProperty('--pts', String(s)); }
}
addEventListener('resize', () => document.querySelectorAll('#stage > section.stage:not([hidden])').forEach(fitPoints));

const roomPart = (st, cls) => st.querySelector(':scope > .' + cls);
const said = n => n.length < 2 ? n.join('') : n.slice(0, -1).join(', ') + ' or ' + n[n.length - 1];
const mark = (kind, k) => kind === 'scale' ? String(k + 1) : LETTERS[k];

// The question on the stage (shots/a4-hands.png), from an `ask` message. All text goes in as text.
function drawAsk(st, m) {
  const box = roomPart(st, 'stage-ask');
  if (!m.ask) { box.hidden = true; box.replaceChildren(); return; }
  const a = m.ask, opts = a.options || [], sec = sectionOf(st, m.slide), n = sectionsOf(st).indexOf(sec) + 1;
  const ol = make('ol', 'ask-opts');
  opts.forEach((o, k) => { const li = make('li'); li.dataset.k = k; li.dataset.o = o; li.append(make('span', 'L', mark(a.kind, k)), maths('span', 't', o)); ol.append(li); });
  const hint = opts.length ? `Hands up for your answer: ${said(opts.map((_, k) => mark(a.kind, k)))}.` : 'Think of your answer. The presenter asks some of you to say it.';
  box.replaceChildren(make('p', 'crumb', `Ask the room · slide ${n}`), maths('h2', 'ask-q', a.q), ...(opts.length ? [ol] : []), make('p', 'hint-line', hint));
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
    const items = [...box.querySelectorAll('.ask-opts li')].map(li => li.dataset.o);
    const ol = make('ol', 'right-order');
    m.right.forEach(i => ol.append(maths('li', '', items[i] ?? '')));
    box.querySelector('.right-order')?.remove();
    box.querySelector('.hint-line').replaceWith(make('p', 'hint-line', 'The right order:'), ol);
  } else box.querySelector('.hint-line').textContent = m.main == null ? 'The right answer is lit.' : 'The right answer and the answer of most hands are lit.';
}

function drawPair(st, m) {
  const box = roomPart(st, 'stage-pair');
  box.replaceChildren(maths('p', 'pair-say', m.prompt || 'Talk to your neighbour.'));
  box.hidden = !m.on;
}

function drawEnd(st) {
  const box = roomPart(st, 'stage-pair');
  box.replaceChildren(make('h2', 'pair-say', 'Thank you'), maths('p', 'crumb', st.dataset.title || ''));
  box.hidden = false;
}

// The audience window tells how many pages its primer has (`pages`), so a presenter window with no pane (a narrow one) stops at the real last page.
// The presenter tells how far the demo box scrolls (`demoscroll`, 0 to 1), when the demo is in a taller box.
const stageTypes = () => {
  abhyasaStage.add('pages', {n: v => Number.isInteger(v) && v >= 1 && v <= 20}, ['n']);
  abhyasaStage.add('demoscroll', {y: v => typeof v === 'number' && v >= 0 && v <= 1}, ['y']);
};
const tallBox = st => st.querySelector('section.stage:not([hidden]) .demo.tall');

// Page `n` of the primer in the pane frame `f` (core/talktype.js), now and each time the frame loads.
function framePage(f, n) {
  if (!f) return;
  f._page = n;
  const set = () => f.contentWindow?.abhyasaTalkPage?.set(f._page);
  if (!f._paged) { f._paged = true; f.addEventListener('load', set); }
  set();
}

// Wait until rupaka mounts the demo in `host` (its boot runs on load and after each swap).
function mounted(host, fn, left = 200) {
  if (host.rupaka) return fn(host);
  if (left > 0) setTimeout(() => mounted(host, fn, left - 1), 50);
}

// The demo fits the free space of its part as one picture, with no scroll. rupaka lays it out at the width in talk.css, and `zoom`
// scales it to min(box width / its width, box height / its height). Both windows do the same, so the laser points at the same place.
// The zoom has a floor, as a share of a slide 1280 px wide, so the text of the demo stays readable from the room (rupaka's 18 px
// text shows at about 10 px). When the demo is smaller than the floor beside the other parts, the slide shows the demo alone
// (`demo-alone`: the crumb, the title, the passage and the figure go). When its text is still under 14 px alone, it keeps 14 px
// in a taller box (`tall`) that scrolls, and the presenter's scroll shows in the room (`demoscroll`), rather than shrink further.
const DEMO_FLOOR = .55, DEMO_TEXT = 14;
function fit(host) {
  const box = host.parentElement, sec = host.closest('section.stage');
  const size = () => {
    const bw = box.clientWidth, bh = box.clientHeight;
    if (!bw || !bh) return 0;
    host.style.zoom = '1';
    // 2% less: text at a small zoom does not scale in a straight line, so the demo stays inside its box
    return .98 * Math.min(bw / Math.max(1, host.offsetWidth), bh / Math.max(1, host.offsetHeight));
  };
  const go = () => {
    sec?.classList.remove('demo-alone'); box.classList.remove('tall');
    let z = size();
    if (!z) return;   // a part that does not show yet: the observer calls again when it shows
    const floor = DEMO_FLOOR * (sec?.parentElement?.clientWidth || 1280) / 1280;
    if (z < floor && sec?.querySelector('.body')) {
      sec.classList.add('demo-alone'); z = size() || z;
      const least = Math.min(DEMO_TEXT / (parseFloat(getComputedStyle(host).fontSize) || 18), .98 * box.clientWidth / Math.max(1, host.offsetWidth));
      if (z < least) { z = least; box.classList.add('tall'); }
    }
    host.style.zoom = String(Math.floor(z * 1000) / 1000);
  };
  const ro = new ResizeObserver(go);
  ro.observe(box);
  if (host.firstElementChild) ro.observe(host.firstElementChild);   // the blocks after a gate show: the demo gets taller
  go();
}

// --- the presenter window ----------------------------------------------------------------------------------------------
function presenterView(st) {
  stageTypes();
  const box = document.getElementById('talk'), base = `/t/${box.dataset.tid}/`, ch = abhyasaStage.channel(box.dataset.channel);
  const $ = id => document.getElementById(id), sayLine = $('say');
  // the result and the pair prompt that show now come from the run log, so a reload of this window can give them to a hello again
  let at = JSON.parse(box.dataset.at), result = JSON.parse(box.dataset.result || 'null'), pair = JSON.parse(box.dataset.pair || 'null');
  let seen = 0, opened = false, goWait = null;
  // the primer beside the slide ({slug, slide, url, title, ask, main, open}), from the run log; `open` is true while its question is open
  let side = JSON.parse(box.dataset.side || 'null');
  // the slides whose answer the room saw (R), from the run log: only then do the answers of their demo gates go to the room
  const revealed = new Set(JSON.parse(box.dataset.revealed || '[]'));
  const slides = sectionsOf(st).map(s => ({sid: s.dataset.sid, n: +s.dataset.n, beats: JSON.parse(s.dataset.beats || '[]')}));
  const idx = () => slides.findIndex(s => s.sid === at.slide);
  const say = t => { sayLine.textContent = t || ''; };
  // Abhyasa.app opens a second window in the same view (spec 9.4). The app puts `Abhyasa/<version>` in its user agent; an older app
  // is WebKit with no `Safari/`.
  const ua = navigator.userAgent, app = /\bAbhyasa\//.test(ua) || (/AppleWebKit/.test(ua) && !/Safari\//.test(ua));

  // Each message goes to the audience window and is drawn here too, so the presenter sees what the room sees.
  st.addEventListener('scroll', e => {
    const d = e.target;
    if (d.classList?.contains('tall') && d === tallBox(st) && d.scrollHeight > d.clientHeight) send({t: 'demoscroll', y: Math.round(d.scrollTop / (d.scrollHeight - d.clientHeight) * 1e3) / 1e3}, false);
  }, true);
  let roomPages = null, roomUrl = null;   // the pages of the primer in the audience window, when this window has no pane
  function send(m, here = true) {
    if (m.t === 'pane' && m.url !== roomUrl) { roomUrl = m.url; roomPages = null; }
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
    else if (m.t === 'pane' && m.url) framePage(document.querySelector('#rh-pane iframe'), m.page || 0);
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
    if (!at.pane && side) { side = null; drawSide(); if (abhyasaPane.isOpen()) abhyasaPane.close(); }   // the server closed the primer
    r.msgs.forEach(m => send(m));
    paint();
    if (moved) sendDemo();
    const s = slides[idx()];
    if (s.beats[at.beat - 1] === 'ask' && !at.ask) await ask('open');
  }
  // With the primer beside the slide, D and A turn its pages. The pages of this window's pane give the last page; with no pane
  // here (a narrow window), the audience window tells the count, and until it does, the limit of 20 pages does.
  ch.on('pages', m => { roomPages = m.n; });
  const paneFrame = () => document.querySelector('#rh-pane iframe');
  const lastPage = () => { const n = paneFrame()?.contentWindow?.abhyasaTalkPage?.pages ?? roomPages; return (n || 20) - 1; };
  const turn = by => act(async () => {
    const n = (side.page || 0) + by;
    if (n < 0) return;
    if (n > lastPage()) return say('This is the last page of the primer. ⌥Z goes back to the slide.');
    const r = await post('at', {slide: at.slide, beat: at.beat, page: n});
    if (!r) return;
    side.page = n; at = r.at;
    r.msgs.forEach(m => send(m));
  });
  const next = () => side && at.pane ? turn(1) : act(() => { const i = idx(), s = slides[i]; if (at.beat < s.n) return go(s.sid, at.beat + 1); if (i + 1 < slides.length) return go(slides[i + 1].sid, 1); });
  const back = () => side && at.pane ? turn(-1) : act(() => { const i = idx(); if (at.beat > 1) return go(at.slide, at.beat - 1); if (i > 0) return go(slides[i - 1].sid, slides[i - 1].n); });
  const goTo = n => act(() => slides[n - 1] && go(slides[n - 1].sid, 1));
  const blank = () => act(() => go(at.slide, at.beat, {blank: at.blank ? 0 : 1}));
  // --- the side pane (spec 12): ⌥B shows the offer here only; 1 or 2 opens the primer beside the slide in both windows
  const offerBox = $('beside-offer'), wide = matchMedia('(min-width: 1100px)');
  const offerOpen = () => !!offerBox.querySelector('.bs-offer');
  const shutOffer = () => offerBox.replaceChildren();
  async function offer(need) {
    if (at.pane || side) return say('Close the side pane first (⌥Z).');
    const r = await fetch(base + 'beside', {method: 'POST', body: new URLSearchParams({slide: at.slide, ...(need ? {need} : {})})}).catch(() => null);
    if (!r) return say('abhyasa did not answer. Try again.');
    if (!r.ok) return say(await r.text());
    say('');
    // the HTML of this app (FT, with each name escaped on the server), never text from the room
    offerBox.replaceChildren(...new DOMParser().parseFromString(await r.text(), 'text/html').body.childNodes);
  }
  const openPane = () => {
    if (!side) return;
    if (wide.matches) { abhyasaPane.open(side.url + '?pane=1&talk=1', side.title); framePage(paneFrame(), side.page || 0); }
    else say('The primer shows beside the slide in the audience window. Make this window wider to see it here too.');
  };
  const choose = w => act(async () => {
    offerBox.querySelectorAll('.bs-way').forEach(b => { b.disabled = true; });
    say('Making the primer…');
    const r = await fetch(base + 'beside', {method: 'POST', body: new URLSearchParams({slide: at.slide, slug: w.dataset.slug, how: w.dataset.how})}).catch(() => null);
    if (!r || !r.ok) { offerBox.querySelectorAll('.bs-way').forEach(b => { b.disabled = false; }); return say(r ? await r.text() : 'abhyasa did not answer. Try again.'); }
    const d = await r.json();
    if (!PANE.test(d.url) || d.pane !== d.url + '?pane=1&talk=1') return say('abhyasa gave a page that the side pane does not open.');
    shutOffer();
    side = {slug: w.dataset.slug, slide: at.slide, url: d.url, title: d.title, ask: null, main: null, open: false, page: 0};
    await go(at.slide, at.beat, {pane: d.url});   // the reply sends {t: 'pane'} to the audience window, with ?pane=1&talk=1
    openPane();
  });
  offerBox.addEventListener('click', e => {
    const w = e.target.closest('.bs-way'), n = e.target.closest('.bs-need');
    if (w && !w.disabled) choose(w); else if (n) offer(n.dataset.need);
  });
  // The pane closed (⌥Z, Esc, × or browser Back): keep the primer in the run log, and close it in the audience window.
  const closeSide = () => act(async () => {
    if (!side && !at.pane) return;
    if (side?.open) await ask('close');
    const r = await post('beside', {close: 1});
    if (!r) return;
    at = r.at; side = null; drawSide();
    r.msgs.forEach(m => send(m));
    paint();
  });
  const closePane = () => abhyasaPane.isOpen() ? abhyasaPane.close() : closeSide();
  let paneWas = root.classList.contains('rh-open');
  new MutationObserver(() => { const now = root.classList.contains('rh-open'); if (paneWas && !now) closeSide(); paneWas = now; })
    .observe(root, {attributes: true, attributeFilter: ['class']});

  // --- the question for the room
  const block = () => side?.open ? $('ask-side') : document.querySelector(`#ask-card .ask-q[data-sid="${CSS.escape(at.slide)}"]`);
  // The question on the idea of the primer (Q with the pane open), drawn as text in its own block of the card.
  function drawSide() {
    const card = $('ask-card');
    card.querySelector('#ask-side')?.remove();
    const a = side?.open && side.ask;
    if (!a) return;
    const opts = a.options || [], b = make('div', 'ask-q side');
    b.id = 'ask-side'; b.dataset.n = opts.length; b.dataset.kind = a.kind;
    b.dataset.ask = JSON.stringify({slide: at.slide, ask: Object.fromEntries(['kind', 'q', 'options', 'most'].filter(k => k in a).map(k => [k, a[k]]))});
    const ol = make('ol', 'opts');
    opts.forEach((o, k) => { const li = make('li', a.kind === 'choice' && k === a.answer ? 'right' : ''); li.append(make('span', 'L', mark(a.kind, k)), maths('span', '', o)); ol.append(li); });
    const hands = make('div', 'hands row');
    opts.forEach((_, k) => {
      const h = make('button', side.main === k ? 'on' : '', mark(a.kind, k)); h.type = 'button'; h.dataset.hand = k;
      h.append(make('kbd', '', String(k + 1))); h.addEventListener('click', () => hand(k + 1)); hands.append(h);
    });
    b.append(maths('span', 'lbl', `Ask the room · on the primer: ${side.title}`), maths('p', 'q', a.q), ...(opts.length ? [ol, hands] : []));
    card.insertBefore(b, card.querySelector('.none'));
  }
  async function ask(what, extra = {}) {
    const onSide = what === 'open' ? !!side && !at.ask : !!side?.open;
    let r = await post('ask', {slide: at.slide, act: what, ...extra, ...(onSide ? {pane: 1} : {})});
    if (!r) return;
    if (onSide && what === 'open') { side.ask = r.ask; side.open = true; side.main = null; r = r.msg; drawSide(); }
    else if (what === 'open' && side) side.open = false;
    if (onSide && what === 'main') side.main = r.main;
    if (what === 'close' && side?.open) { side.open = false; drawSide(); }
    if (what === 'open') { at.ask = at.slide; result = null; }
    if (what === 'close') { at.ask = null; result = null; if (pair?.on) send(pair = {t: 'pair', on: false, prompt: pair.prompt}); }
    if (what === 'main') document.querySelectorAll('#ask-card [data-hand]').forEach(b => b.classList.toggle('on', +b.dataset.hand === r.main));
    else if (what === 'reveal') { result = r; send(r); if (!onSide) { revealed.add(at.slide); sendAnswers(); } const i = idx(); if (!onSide && r.main != null && !Array.isArray(r.right) && r.right != null && r.main !== r.right) $('rail').children[i]?.classList.add('shaky'); }
    else if (what === 'pair') send(pair = r);
    else send(r);
    paint();
  }
  const askKey = () => act(() => at.ask ? ask('close') : ask('open'));
  const last = () => idx() === slides.length - 1 && !side && !block();
  const main = () => last() ? endTalk() : act(() => !at.ask ? ask('open') : !result ? ask('reveal') : ask('close'));
  const hand = d => {
    const b = block();
    if (!at.ask || !b || d > +b.dataset.n) return false;
    act(() => ask('main', {main: d - 1}));
  };

  // --- the demo: the presenter's copy runs here; the audience copy follows it. The presenter's own pick is not logged.
  st.addEventListener('rk-predict', e => { e.preventDefault(); e.detail.settle(true); });
  const demos = () => [...(sectionOf(st, at.slide)?.querySelectorAll('[data-rupaka][data-demo]') || [])];
  function sendDemo() { demos().forEach(h => h._mirror && send({t: 'demo', slug: h.dataset.demo, ...h._mirror.snapshot()}, false)); sendAnswers(); }
  // After R, the answers of the done gates of the slide, so the audience copy can draw the verdict of the presenter's pick.
  function sendAnswers() {
    if (!revealed.has(at.slide)) return;
    for (const h of demos()) {   // one message for each demo, so the slug and the gate id name a gate
      const gates = h._mirror?.answers() || {};
      if (Object.keys(gates).length) send({t: 'answers', slide: at.slide, slug: h.dataset.demo, gates}, false);
    }
  }
  st.querySelectorAll('[data-rupaka][data-demo]').forEach(h => mounted(h, () => {
    fit(h);
    h._mirror = abhyasaStage.mirror(h);
    h._mirror.watch(s => { if (h.closest('section.stage')?.dataset.sid === at.slide) { send({t: 'demo', slug: h.dataset.demo, ...s}, false); sendAnswers(); } });
  }));
  const intoDemo = () => {
    const h = demos().find(x => !x.closest('[hidden]'));
    const c = h?.querySelector('input, button:not([disabled]), select, [tabindex]:not([tabindex="-1"])');
    if (c) c.focus(); else say('This slide has no demo to go into.');
  };
  const esc = () => {
    if (offerOpen()) return shutOffer();
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
    if (!goWait && offerOpen()) { const w = offerBox.querySelectorAll('.bs-way')[+d - 1]; if (!w) return false; if (!w.disabled) choose(w); return; }
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
  // ⌥B and ⌥Z keep their app meanings (spec 11): learn beside, and back to the slide. pane.js takes ⌥Z while its pane shows.
  addEventListener('keydown', e => {
    if (!e.altKey || e.metaKey || e.ctrlKey || e.repeat || !root.classList.contains('talk')) return;
    if (e.code === 'KeyB') { e.preventDefault(); e.stopImmediatePropagation(); act(() => offer()); }
    else if (e.code === 'KeyZ' && !abhyasaPane.isOpen() && (side || at.pane)) { e.preventDefault(); e.stopImmediatePropagation(); closeSide(); }
  }, true);
  // End the talk: the run ends on the server, the audience window shows the end, and this window opens After the talk.
  const endTalk = () => act(async () => {
    const r = await fetch(base + 'end', {method: 'POST'}).catch(() => null);
    if (!r || !r.ok) return say(r ? await r.text() : 'abhyasa did not answer. Try again.');
    send({t: 'end'}, false);
    location.assign(r.url);
  });
  $('end-form').addEventListener('submit', e => { e.preventDefault(); endTalk(); });
  $('pair-go').addEventListener('click', () => act(() => ask('pair', {on: pair?.on ? 0 : 1})));
  document.querySelectorAll('#ask-card [data-hand]').forEach(b => b.addEventListener('click', () => hand(+b.dataset.hand + 1)));

  // --- the audience window: it says hello when it loads, and here every 2 s
  function hello() {
    seen = Date.now(); paint();
    send({t: 'go', slide: at.slide, beat: at.beat}, false);
    send({t: 'blank', on: !!at.blank}, false);
    send({t: 'pane', url: at.pane && PANE.test(at.pane) ? at.pane + '?pane=1&talk=1' : null, page: at.pane && side?.page || 0}, false);
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
    const crumb = sec.querySelector('.crumb');   // a copy of the drawn crumb, so its maths shows as on the slide
    $('now').replaceChildren(`Now · slide ${i + 1} of ${slides.length}`, ...(crumb ? [' · ', ...crumb.cloneNode(true).childNodes] : []));
    $('beats').replaceChildren(`Beat ${at.beat} of ${s.n} `, ...Array.from({length: s.n}, (_, k) => make('i', k < at.beat ? 'on' : '')));
    [...$('rail').children].forEach((r, k) => { r.classList.toggle('done', k < i); r.classList.toggle('now', k === i); });
    for (const id of ['notes', 'next']) [...$(id).children].forEach(n => { n.hidden = n.dataset.sid !== at.slide; });
    const card = $('ask-card'), b = block();
    card.querySelectorAll('.ask-q').forEach(q => { q.hidden = q !== b; });
    card.querySelector('.none').hidden = !!b;
    const end = last();
    card.querySelector('.acts').hidden = !b && !end;
    card.classList.toggle('open', !!at.ask); card.classList.toggle('shown', !!result);
    const go = $('ask-go');
    go.querySelector('.act').textContent = end ? 'End the talk' : !at.ask ? 'Ask the room' : !result ? 'Show the answer' : 'Close the question';
    go.querySelector('kbd').textContent = end ? '⌥S' : !at.ask ? 'Q' : !result ? 'R' : 'Q';
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
  if (side && !(side.open && at.ask === at.slide)) side.open = false;
  drawSide();
  if (side && at.pane) openPane();   // a reload: the primer is still beside the slide
  if (at.ask) { const b = block(); if (b) drawAsk(st, {t: 'ask', ...JSON.parse(b.dataset.ask)}); }
  if (result) drawResult(st, result);
  if (pair) drawPair(st, pair);
  show(st, at.slide, at.beat);
  paint();
}

// --- the audience window -----------------------------------------------------------------------------------------------
function audienceView(st) {
  stageTypes();
  const ch = abhyasaStage.channel(st.dataset.channel), note = document.getElementById('keys-note');
  ch.on('demoscroll', m => { const d = tallBox(st); if (d) d.scrollTop = m.y * (d.scrollHeight - d.clientHeight); });
  setInterval(() => { const n = st.querySelector(':scope > iframe.stage-pane')?.contentWindow?.abhyasaTalkPage?.pages; if (n) ch.send({t: 'pages', n}); }, 700);
  const mirrors = new Map();
  st.querySelectorAll('[data-rupaka][data-demo]').forEach(h => mounted(h, () => { fit(h); const m = abhyasaStage.mirror(h); m.apply({}, {}); mirrors.set(h, m); }));
  function draw(m) {
    if (m.t === 'go') {   // the answers of the old slide's gates go out on a new slide
      if (m.slide !== st.dataset.slide) mirrors.forEach((x, h) => { if (h.closest('section.stage')?.dataset.sid !== m.slide) x.forget(); });
      show(st, m.slide, m.beat);
    }
    else if (m.t === 'ask') drawAsk(st, m);
    else if (m.t === 'result') drawResult(st, m);
    else if (m.t === 'pair') drawPair(st, m);
    else if (m.t === 'end') drawEnd(st);
    else if (m.t === 'demo') {
      const sec = sectionOf(st, st.dataset.slide);
      sec?.querySelectorAll(`[data-rupaka][data-demo="${CSS.escape(m.slug)}"]`).forEach(h => mirrors.get(h)?.apply(m.state, m.gates, m.pick));
    }
    else if (m.t === 'answers' && m.slide === st.dataset.slide)
      sectionOf(st, m.slide)?.querySelectorAll(`[data-rupaka][data-demo="${CSS.escape(m.slug)}"]`).forEach(h => mirrors.get(h)?.reveal(m.gates));
  }
  // the side pane shows only a walk step in the talk type, over the checked channel
  const only = {...ch, on: (t, fn) => ch.on(t, t === 'pane' ? m => { if (!paneOK(m.url)) return; fn(m); if (m.url) framePage(st.querySelector(':scope > iframe.stage-pane'), m.page || 0); } : fn)};
  abhyasaStage.audience(st, {ch: only, draw, fade: +st.dataset.fade || 1500, title: st.dataset.title});
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
