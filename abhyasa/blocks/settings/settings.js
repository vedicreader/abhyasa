// The Settings page. The − and + buttons and the sliders of a setting row are in core.js, as the Profile page has rows too.
// The tabs: one tab shows at a time, and ?tab=voice keeps it in the URL. An old link such as #g-voice or #sr-walks-hands opens the tab
// that holds that group or row, and shows it. This part runs in the head, so the right tab draws first and the page does not jump.
// ←, →, Home and End move along the tab row. ⌥1 to ⌥7 pick a tab: core.js clicks the tab that `abhyasaKeys` names.
(() => {
  const map = window.abhyasaSettingTabs || {ids: {}, tabs: []}, html = document.documentElement;
  const key = () => decodeURIComponent(location.hash.slice(1));
  function wanted() {
    const h = key(), t = h.replace(/^t-/, '');
    if (map.ids[h]) return map.ids[h];
    if (map.tabs.includes(t)) return t;
    const q = new URLSearchParams(location.search).get('tab');
    return map.tabs.includes(q) ? q : '';
  }
  const first = wanted();
  if (first) html.dataset.stab = first;   // settings.css shows this tab until the page is ready

  function show(t, {url = false, focus = false} = {}) {
    document.querySelectorAll('.stabs [role=tab]').forEach(a => {
      const on = a.dataset.tab === t;
      a.setAttribute('aria-selected', on); a.tabIndex = on ? 0 : -1; a.classList.toggle('on', on);
      if (on && focus) a.focus();
    });
    document.querySelectorAll('.stab').forEach(p => { p.hidden = p.dataset.tab !== t; });
    delete html.dataset.stab;
    if (url) history.replaceState(history.state, '', `${location.pathname}?tab=${t}`);
  }
  function land() {
    // the tab of the link, then the row or the group of the link in view, with its More open; the focus stays where it is
    const t = wanted();
    if (t) show(t);
    const el = key() && document.getElementById(key());
    if (!el || !t) return;
    const d = el.closest('details.more'); if (d) d.open = true;
    el.scrollIntoView({block: el.matches('.sgroup, .stab') ? 'start' : 'center'});
  }
  const tab = i => `.stabs [role=tab]:nth-of-type(${i})`;
  document.addEventListener('DOMContentLoaded', () => {
    Object.assign(window.abhyasaKeys, {Digit1: tab(1), Digit2: tab(2), Digit3: tab(3), Digit4: tab(4), Digit5: tab(5), Digit6: tab(6), Digit7: tab(7)});   // after core.js
    land();
  });
  addEventListener('hashchange', land);
  document.addEventListener('click', e => {
    const a = e.target.closest && e.target.closest('.stabs [role=tab]');
    if (!a || e.metaKey || e.ctrlKey || e.shiftKey) return;
    e.preventDefault(); clear(); show(a.dataset.tab, {url: true});
  });
  document.addEventListener('keydown', e => {
    const a = e.target.closest && e.target.closest('.stabs [role=tab]');
    if (!a || e.altKey || e.metaKey || e.ctrlKey) return;
    const all = [...document.querySelectorAll('.stabs [role=tab]')], i = all.indexOf(a);
    const j = {ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: all.length - 1}[e.key];
    if (j === undefined) return;
    e.preventDefault();
    show(all[(j + all.length) % all.length].dataset.tab, {url: true, focus: true});
  });

  // "Find a setting" looks in all the tabs: it shows only the rows whose label or help has the words, and opens the "More" parts that hold them.
  const box = () => document.getElementById('sfind');
  function clear() { const b = box(); if (b && b.value) { b.value = ''; find(''); } }
  document.addEventListener('input', e => { if (e.target.id === 'sfind') find(e.target.value); });
  function find(q) {
    const ws = q.toLowerCase().split(/\s+/).filter(Boolean), all = document.querySelector('.sgroups');
    if (all) all.classList.toggle('finding', ws.length > 0);
    document.querySelectorAll('.sgroup').forEach(g => {
      let any = !ws.length;
      g.querySelectorAll('[data-find]').forEach(r => {
        const hit = ws.every(w => r.dataset.find.includes(w));
        r.hidden = ws.length > 0 && !hit;
        if (hit && ws.length) { any = true; const d = r.closest('details.more'); if (d) d.open = true; }
      });
      g.hidden = ws.length > 0 && !any;
    });
  }
})();

// "Play a sample" in Speaking voice: the browser voice speaks the line here; another engine gets the line from the server as a WAV,
// and the line under the button gives the time to the audio. It plays only after the click.
(() => {
  document.addEventListener('click', async e => {
    const b = e.target.closest && e.target.closest('button[data-sample]');
    if (!b) return;
    const said = b.parentElement.querySelector('.out-said'), tell = t => { if (said) said.textContent = t; };
    if (b.dataset.engine === 'browser') {
      if (!('speechSynthesis' in window)) return tell('This browser has no voice.');
      speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance(b.dataset.text));
      return tell('The browser voice speaks on this Mac.');
    }
    tell('Getting the sample…'); b.disabled = true;
    try {
      const r = await fetch(b.dataset.sample, {method: 'POST'}), d = await r.json().catch(() => ({}));
      if (!r.ok || !d.audio) return tell(d.error || 'The voice did not answer.');
      const url = URL.createObjectURL(new Blob([Uint8Array.from(atob(d.audio), c => c.charCodeAt(0))], {type: 'audio/wav'})), a = new Audio(url);
      a.addEventListener('ended', () => URL.revokeObjectURL(url), {once: true});
      await a.play();
      tell(`${(d.ms / 1000).toFixed(1)} s to the audio${d.cached ? ' (said before)' : ''} · ${d.where === 'hosted' ? 'hosted · OpenAI' : 'on this Mac'}`);
    } catch (err) { tell('The voice did not answer.'); }
    finally { b.disabled = false; }
  });
})();
