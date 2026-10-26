// The session keys, all for the left hand: ⌥S sends (or goes to the next question), ⌥W asks for a hint, ⌥X is "I don't know"
// (or "Teach me"), ⌥1 to ⌥5 set how sure you are, ⌥Q ⌥W ⌥E ⌥R pick an option. ⌘↵ sends from either box.
Object.assign(abhyasaKeys, {KeyW: '#hint, #o1', KeyX: '#idk', KeyQ: '#o0', KeyE: '#o2', KeyR: '#o3',   // ⌥↑ ⌥↓ step through the earlier questions
                            Digit1: '#c1', Digit2: '#c2', Digit3: '#c3', Digit4: '#c4', Digit5: '#c5'});

// A boosted page loads this file again, so the listeners go on once.
if (!window.abhyasaSession) {
  window.abhyasaSession = true;
  const motion = () => abhyasaMotion() ? 'smooth' : 'auto';
  const composer = () => document.getElementById('composer');

  // The chat keeps room for the composer under its last message.
  const fit = () => { const c = composer(); document.documentElement.style.setProperty('--composer-h', (c ? c.offsetHeight : 0) + 'px'); };
  const ro = new ResizeObserver(fit);
  const watch = () => { ro.disconnect(); const c = composer(); if (c) ro.observe(c); fit(); };
  window.addEventListener('load', watch);
  document.addEventListener('htmx:afterSettle', watch);

  // While the tutor reads your message, the boxes stay as they are; when it answers, they empty, as the message is now in the chat.
  document.addEventListener('htmx:beforeRequest', e => {
    const c = composer();
    if (c && (e.detail.elt === c || c.contains(e.detail.elt) || e.detail.elt.matches('.opt'))) c.querySelectorAll('textarea').forEach(t => t.readOnly = true);
  });
  document.addEventListener('htmx:afterRequest', e => {
    const c = composer();
    if (!c) return;
    c.querySelectorAll('textarea').forEach(t => t.readOnly = false);
    const sent = e.detail.successful && e.detail.xhr.status === 200 && /\/(answer|giveup)$/.test(e.detail.requestConfig.path);
    if (sent) c.querySelectorAll('textarea').forEach(t => { t.value = ''; t.dispatchEvent(new Event('input', {bubbles: true})); });
  });

  // After each reply: bring its top into view, then put the cursor where the next move is.
  document.addEventListener('htmx:afterSettle', e => {
    const t = e.detail.target;
    if (!t || !t.matches || !(t.matches('.thread, .qa') || t.id === 'chat')) return;
    const last = t.matches('.thread') ? t.lastElementChild : document.querySelector('#chat > .qa:last-child');
    if (last) {
      const top = last.getBoundingClientRect().top, room = innerHeight - (composer() ? composer().offsetHeight : 0);
      if (top < 60 || top > room * .7) window.scrollBy({top: top - 70, behavior: motion()});
    }
    const f = document.querySelector('div#composer #send, #composer #ans, #chat .qa:last-child .opt:not(:disabled), #composer #think');
    if (f) f.focus({preventScroll: true});
  });

  // ⌘↵ (or Ctrl+↵) sends from either box; in the closed state it goes to the next question.
  document.addEventListener('keydown', e => {
    if (e.key !== 'Enter' || !(e.metaKey || e.ctrlKey)) return;
    const s = document.querySelector('#composer #send');
    if (s) { e.preventDefault(); s.click(); }
  });
}

// The list of earlier questions: folded on a narrow window, and ⌥↑ ⌥↓ open the one above or below the question in view.
if (!window.abhyasaRail) {
  window.abhyasaRail = true;
  const fold = () => { const r = document.getElementById('rail'); if (r && innerWidth < 1040 && !r.dataset.touched) r.open = false; };
  window.addEventListener('load', fold); document.addEventListener('htmx:afterSettle', fold);
  // only a click counts as the learner's choice: an open <details> also fires `toggle` when the page loads
  document.addEventListener('click', e => { const r = e.target.closest('#rail > summary'); if (r) r.parentElement.dataset.touched = 1; });
  document.addEventListener('keydown', e => {
    if (!e.altKey || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown')) return;
    const items = [...document.querySelectorAll('#rail .rail-list li')]; if (!items.length) return;
    const i = Math.max(0, items.findIndex(li => li.classList.contains('on')));
    const to = items[Math.min(items.length - 1, Math.max(0, i + (e.key === 'ArrowUp' ? -1 : 1)))];
    const a = to && to.querySelector('a');
    if (a && to !== items[i]) { e.preventDefault(); a.click(); }
  });
}
