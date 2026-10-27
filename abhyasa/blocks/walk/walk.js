// The walk keys, for the left hand: ⌥F goes to the next idea, ⌥W asks for a hint. ⌥S presses the main button (core.js), and ⌘↵ sends the answer.
Object.assign(abhyasaKeys, {KeyF: '#next', KeyW: '#hint'});

// After a check card loads or changes, the cursor goes to the answer box, or to Next idea when the check is closed.
if (!window.abhyasaWalk) {
  window.abhyasaWalk = true;
  document.addEventListener('htmx:afterSettle', e => {
    if (!e.detail.target || e.detail.target.id !== 'check') return;
    const f = document.querySelector('#check #ans, #check .go');
    if (f) f.focus({preventScroll: true});
  });
}
