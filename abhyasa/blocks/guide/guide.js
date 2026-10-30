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

  // --- asking ----------------------------------------------------------------------------------------------------------
  const form = () => document.getElementById('guide-form'), box = () => document.getElementById('guide-box');
  const heard = t => { const h = form() && form().querySelector('.guide-heard'); if (h) h.textContent = t; };
  const say = t => window.abhyasaBoard && abhyasaBoard.note(t);
  function open(text) {
    const f = form(), b = box();
    if (!f || !b) return;
    const sel = cut(String(getSelection() || ''), 80);
    f.hidden = false; heard('');
    b.value = text != null ? text : sel ? `I don't get "${sel}"` : '';
    b.focus(); b.setSelectionRange(b.value.length, b.value.length);
  }
  function close() { if (form()) form().hidden = true; }

  // Ask the tutor: read the page, post the question with it, and play the board that comes back. The times go into
  // `abhyasaGuideLast`: from the press of Explain to the board, and to the first mark.
  async function ask(said) {
    said = cut(said, 300);
    if (!said) return;
    close();
    const t0 = performance.now(), last = window.abhyasaGuideLast = {said, t0};
    say('The tutor reads the page.');
    try {
      const ctx = await capture();
      last.capture_ms = Math.round(performance.now() - t0);
      const labels = Object.fromEntries(ctx.anchors.filter(a => a.labels).map(a => [a.id, a.labels]));
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
          if (m.wait) say(m.wait);
          if (m.error) say(m.error);
          if (m.board) {
            last.board_ms = Math.round(performance.now() - t0); last.server_ms = m.board.ms; last.tier = m.board.tier;
            document.addEventListener('board:first', () => { last.first_ms = Math.round(performance.now() - t0); }, {once: true});
            await abhyasaBoard.play(m.board, {labels, quiet: !!window.abhyasaGuideQuiet});
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

  window.abhyasaGuide = {capture, texParts: (...a) => abhyasaTex.texParts(...a), labelsOf, ask, open};
})();
