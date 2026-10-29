// The grip: the edge of a panel at the right that you drag to make it wider or narrower (the side pane and the Graph tools).
// `abhyasaGrip(grip, {box, key, bounds, apply, quick})` gives the grip a pointer drag, the arrow keys (24 px, Shift 96 px), a double-click that
// resets, and a width kept in localStorage under `key`. `box` is the panel, `bounds()` is [min, max] in px, `apply(px)` sets the width
// (`apply(null)` takes the width back to the default). With `quick`, 1, 2 and 3 on the grip set one third, one half and two thirds of the window.
// It returns {set, reset, restore}. The grip sends `abhyasa:grip` when you move it.
window.abhyasaGrip = (grip, o) => {
  if (grip.abhyasaGrip) return grip.abhyasaGrip;
  const root = document.documentElement, width = () => o.box.getBoundingClientRect().width;
  const set = (w, keep = true) => {
    const [lo, hi] = o.bounds();
    w = Math.round(Math.min(hi, Math.max(lo, w)));
    o.apply(w);
    if (keep) localStorage.setItem(o.key, w);
    Object.entries({'aria-valuemin': lo, 'aria-valuemax': Math.round(hi), 'aria-valuenow': Math.round(width())}).forEach(([k, v]) => grip.setAttribute(k, v));
    return w;
  };
  const reset = () => { o.apply(null); localStorage.removeItem(o.key); grip.setAttribute('aria-valuenow', Math.round(width())); };
  const restore = () => { const w = +localStorage.getItem(o.key); if (w) set(w, false); };
  const moved = () => grip.dispatchEvent(new CustomEvent('abhyasa:grip', {bubbles: true}));
  grip.addEventListener('pointerdown', e => {
    if (e.button !== 0) return;
    e.preventDefault(); grip.setPointerCapture(e.pointerId); root.classList.add('grip-drag');
    const right = o.box.getBoundingClientRect().right;
    const move = ev => set(right - ev.clientX, false);
    const up = () => { grip.removeEventListener('pointermove', move); root.classList.remove('grip-drag'); set(width(), true); moved(); };
    grip.addEventListener('pointermove', move);
    grip.addEventListener('pointerup', up, {once: true}); grip.addEventListener('pointercancel', up, {once: true});
  });
  grip.addEventListener('dblclick', () => { reset(); moved(); });
  grip.addEventListener('keydown', e => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const d = {ArrowLeft: 1, ArrowRight: -1}[e.key], f = o.quick && {1: 1 / 3, 2: 1 / 2, 3: 2 / 3}[e.key];
    if (!d && !f) return;
    e.preventDefault(); e.stopPropagation();
    set(f ? innerWidth * f : width() + d * (e.shiftKey ? 96 : 24), true); moved();
  });
  return grip.abhyasaGrip = {set, reset, restore};
};
