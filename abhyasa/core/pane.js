// The side pane (core/pane.py draws it), after vedicreader's static/js/pane.js: a page of this app beside the page.
// On a screen of 1100 px or more, `abhyasaPane.open(url, title)` shows the local page `url` with `pane=1` in an iframe at the right.
// The page only gets `padding-right`, so it is not drawn again: its scroll, its forms and its drafts stay. The place of the pane is
// in the URL (`?rh=<local path>`): open pushes it, so browser Back closes the pane, and a reload draws it open again (Page in ui.py).
// Under 1100 px there is no split: the page opens in the same tab, with a link back.
// Messages from the pane page, taken only from this origin and from the pane's own frame:
//   rh:at {url, title, trail}  the pane is at `url`; `trail` is [[title, url], ...] from the main page to the parent of `url`
//   rh:open {url}              open `url` in the same pane (a nested side page)
//   rh:done {slug, outcome}    the side walk ended; sent on as the event 'abhyasa:rh-done' for the block that opened it
//   rh:close {level}           close the pane; with `level`, go back one level only (⌥Z)
// A pane page tells its trail with `data-rh-trail` (JSON) on any element.
(() => {
  const root = document.documentElement, WIDE = matchMedia('(min-width: 1100px)'), RHW = 'rh-w';
  const inPane = () => root.classList.contains('in-pane');
  const isLocal = u => typeof u === 'string' && u.startsWith('/') && !u.startsWith('//') && !/[\x00-\x1f\x7f\\]/.test(u);   // as is_local in pane.py
  const without = (search, k) => search.replace(/^\?/, '').split('&').filter(x => x && !x.startsWith(k + '='));
  const join = (path, q, hash = '') => path + (q.length ? '?' + q.join('&') : '') + hash;
  const paneURL = u => {   // as pane_url in pane.py
    const i = u.indexOf('#'), pq = i < 0 ? u : u.slice(0, i), j = pq.indexOf('?');
    return join(j < 0 ? pq : pq.slice(0, j), [...without(j < 0 ? '' : pq.slice(j), 'pane'), 'pane=1'], i < 0 ? '' : u.slice(i));
  };
  const withRh = u => join(location.pathname, [...without(location.search, 'rh'), ...(u ? ['rh=' + encodeURIComponent(u).replace(/%2F/g, '/')] : [])], location.hash);
  const rhNow = () => new URLSearchParams(location.search).get('rh');
  const toParent = m => { if (parent !== window) parent.postMessage(m, location.origin); };

  // In a pane page: no nav (Page in ui.py, and pane.css for a page that htmx swaps in), moves replace the frame's URL so the
  // history of the main page stays as it is, and each page tells the main page where it is.
  const here = () => join(location.pathname, without(location.search, 'pane'), location.hash);
  if (window.frameElement && window.frameElement.closest('#rh-pane') && !inPane()) location.replace(paneURL(here()));   // a full load lost `pane=1`
  document.addEventListener('htmx:beforeHistoryUpdate', e => {
    if (!inPane() || !e.detail.history) return;
    e.detail.history.type = 'replace'; e.detail.history.path = paneURL(e.detail.history.path);
  });
  const at = () => {
    let trail = [];
    try { trail = JSON.parse(document.querySelector('[data-rh-trail]').dataset.rhTrail); } catch {}
    toParent({type: 'rh:at', url: here(), title: document.title.replace(/ · abhyasa$/, ''), trail});
  };

  // The host. The pane is drawn by PaneHost on a reload, or here when it opens.
  let trail = [], shownKey = null;
  const pane = () => document.getElementById('rh-pane');
  const frame = () => pane()?.querySelector('iframe');
  const isOpen = () => root.classList.contains('rh-open') && !!pane();
  const build = () => {
    const p = document.createElement('aside');
    p.id = 'rh-pane'; p.setAttribute('aria-label', 'Side pane');
    p.innerHTML = '<div class="grip" role="separator" aria-orientation="vertical" aria-label="Resize the side pane" tabindex="0" title="Drag to resize. Double-click to reset."></div>'
      + '<header class="rh-bar"><div class="rh-top"><div class="rh-trail"></div><a class="rh-own" target="_blank" title="Open this page in a new tab">Its own session ↗</a>'
      + '<button type="button" class="rh-x" title="Close (Esc)" aria-label="Close the side pane">×</button></div></header><iframe></iframe>';
    document.body.appendChild(p);
    return p;
  };
  const bar = (url, title, parts) => {
    const p = pane(), t = p.querySelector('.rh-trail'), b = document.createElement('b');
    p.querySelector('.rh-own').setAttribute('href', url);
    t.replaceChildren();
    for (const [label, href] of parts) {
      const a = document.createElement(isLocal(href) ? 'a' : 'span'), s = document.createElement('span');
      a.textContent = label; if (isLocal(href)) a.setAttribute('href', href);
      s.className = 'sep'; s.textContent = '›'; t.append(a, s);
    }
    b.textContent = title || 'Side pane'; t.append(b);
    frame().title = b.textContent;
  };
  const load = (f, src) => {   // a new page in the frame with no new history entry, so browser Back still closes the pane
    let now = null;
    try { now = f.contentWindow.location.pathname + f.contentWindow.location.search; } catch {}
    if (!f.getAttribute('src')) f.setAttribute('src', src);
    else if (now !== src) f.contentWindow.location.replace(src);
  };

  // The width, as vedicreader: the grip drags it, arrow keys move it (24 px, Shift 96 px), a double-click resets it; kept in `rh-w`.
  const bounds = () => [380, Math.max(380, Math.min(innerWidth * .7, innerWidth - 520))];
  const setW = (w, keep) => {
    if (w == null) { root.style.removeProperty('--rh-w'); localStorage.removeItem(RHW); }
    else {
      const [lo, hi] = bounds();
      w = Math.round(Math.min(hi, Math.max(lo, w)));
      root.style.setProperty('--rh-w', `${w}px`);
      if (keep) localStorage.setItem(RHW, w);
    }
    const g = pane()?.querySelector('.grip'), [lo, hi] = bounds();
    if (g) Object.entries({'aria-valuemin': lo, 'aria-valuemax': Math.round(hi), 'aria-valuenow': Math.round(pane().getBoundingClientRect().width)}).forEach(([k, v]) => g.setAttribute(k, v));
  };
  const keptW = () => { const w = +localStorage.getItem(RHW); if (w) setW(w, false); };

  const show = (url, title) => {
    const p = pane() || build();
    if (title !== undefined) bar(url, title, trail); else p.querySelector('.rh-own').setAttribute('href', url);
    root.classList.add('rh-open'); keptW();
    load(p.querySelector('iframe'), paneURL(url));
  };
  const hide = () => {
    root.classList.remove('rh-open');
    const f = frame();
    if (f && f.getAttribute('src')) try { f.contentWindow.location.replace('about:blank'); } catch {}
  };
  const focusCheck = () => {
    const c = document.querySelector('#check textarea') || document.querySelector('#check');
    if (!c) return;
    if (!c.matches('textarea, input, button, a')) c.tabIndex = -1;
    c.focus();
  };
  const narrow = url => {
    sessionStorage.setItem('rh-back', JSON.stringify({from: withRh(null), to: url, title: document.title.replace(/ · abhyasa$/, '')}));
    location.assign(url);
  };
  const backLink = () => {   // under 1100 px: the side page in the same tab gets a link back to the page that opened it
    let b = null;
    try { b = JSON.parse(sessionStorage.getItem('rh-back')); } catch {}
    if (!b) return;
    if (b.to !== location.pathname + location.search) return sessionStorage.removeItem('rh-back');
    const m = document.querySelector('main');
    if (!m || !isLocal(b.from) || m.querySelector('a.rh-back')) return;
    const a = document.createElement('a');
    a.className = 'rh-back'; a.href = b.from; a.textContent = `← Back to ${b.title}`;
    m.prepend(a);
  };

  const open = (url, title) => {
    if (!isLocal(url)) return false;
    if (inPane()) { toParent({type: 'rh:open', url}); return true; }
    if (!WIDE.matches) { narrow(url); return true; }
    const was = isOpen();
    trail = []; show(url, title);
    if (was) history.replaceState(history.state, '', withRh(url));
    else history.pushState({rh: url}, '', withRh(url));
    shownKey = withRh(null);
    return true;
  };
  const close = () => {
    if (!isOpen()) return;
    if (history.state && history.state.rh) history.back();   // the entry that open pushed: Forward opens it again
    else { history.replaceState(history.state, '', withRh(null)); hide(); }
    focusCheck();
  };
  const back = () => trail.length > 1 ? open(trail[trail.length - 1][1]) : close();   // one level up, or back to the page
  window.abhyasaPane = {open, close, isOpen};

  // Back and Forward between the page and the page with its pane change only the pane. Before htmx's own handler (window.onpopstate),
  // which would fetch the page again; a move to another page is left to htmx.
  addEventListener('popstate', e => {
    if (inPane() || withRh(null) !== shownKey) return;
    e.stopImmediatePropagation();
    const rh = rhNow();
    if (isLocal(rh) && WIDE.matches) show(rh); else hide();
  }, true);

  addEventListener('message', e => {
    const f = frame();
    if (inPane() || !f || e.origin !== location.origin || e.source !== f.contentWindow) return;
    const d = e.data || {};
    if (d.type === 'rh:at' && isLocal(d.url)) {
      trail = (Array.isArray(d.trail) ? d.trail : []).filter(x => Array.isArray(x) && typeof x[0] === 'string').map(([l, h]) => [l, h]);
      bar(d.url, typeof d.title === 'string' ? d.title : '', trail);
      if (isOpen() && rhNow() !== d.url) history.replaceState(history.state, '', withRh(d.url));
    } else if (d.type === 'rh:open' && isLocal(d.url)) open(d.url);
    else if (d.type === 'rh:close') d.level ? back() : close();
    else if (d.type === 'rh:done') document.dispatchEvent(new CustomEvent('abhyasa:rh-done', {detail: {slug: d.slug, outcome: d.outcome}}));
  });

  document.addEventListener('click', e => {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;   // with a modifier key, a pane link opens a new tab
    const a = e.target.closest('a[data-pane]');
    if (a && open(a.getAttribute('href'), a.dataset.title || a.textContent.trim())) return e.preventDefault();
    if (e.target.closest('#rh-pane .rh-x')) return close();
    const t = e.target.closest('#rh-pane .rh-trail a');
    if (t) { e.preventDefault(); const h = t.getAttribute('href'); h.split('?')[0] === location.pathname ? close() : open(h); }
  });
  document.addEventListener('pointerdown', e => {
    const g = e.target.closest('#rh-pane .grip');
    if (!g || e.button !== 0) return;
    e.preventDefault(); g.setPointerCapture(e.pointerId); root.classList.add('rh-drag');
    const move = ev => setW(root.clientWidth - ev.clientX, false);
    const up = () => { g.removeEventListener('pointermove', move); root.classList.remove('rh-drag'); setW(pane().getBoundingClientRect().width, true); };
    g.addEventListener('pointermove', move);
    g.addEventListener('pointerup', up, {once: true}); g.addEventListener('pointercancel', up, {once: true});
  });
  document.addEventListener('dblclick', e => { if (e.target.closest('#rh-pane .grip')) setW(null); });
  document.addEventListener('keydown', e => {
    const d = e.target.closest && e.target.closest('#rh-pane .grip') && {ArrowLeft: 1, ArrowRight: -1}[e.key];
    if (d) { e.preventDefault(); setW(pane().getBoundingClientRect().width + d * (e.shiftKey ? 96 : 24), true); }
  });
  // ⌥Z: back to the paper. It closes one level of the pane and puts the focus on the check; in the pane, it asks the main page.
  document.addEventListener('keydown', e => {
    if (!e.altKey || e.metaKey || e.ctrlKey || e.code !== 'KeyZ') return;
    if (inPane()) { e.preventDefault(); toParent({type: 'rh:close', level: 1}); }
    else if (isOpen()) { e.preventDefault(); back(); }
  });
  addEventListener('resize', () => { const w = parseFloat(root.style.getPropertyValue('--rh-w')); if (w) setW(w, false); });

  // On each page, and after htmx puts in a new one: a pane page reports where it is; a host page opens the pane that it has.
  const sync = () => {
    if (inPane()) return at();
    backLink();
    root.classList.toggle('rh-open', !!pane() && isLocal(rhNow()));
    if (pane()) keptW();
    shownKey = withRh(null);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', sync); else sync();
  document.addEventListener('htmx:afterSettle', e => { if (e.detail.target === document.body || inPane()) sync(); });
})();
