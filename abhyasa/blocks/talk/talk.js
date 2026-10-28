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
    if (!root.classList.contains('talk') || e.altKey || e.metaKey || e.ctrlKey || e.repeat || inBox(e.target)) return;
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
