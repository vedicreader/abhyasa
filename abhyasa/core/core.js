// Markdown and maths for `.md` elements, and the left-hand keys: ⌥ + a letter clicks the element a block names.
function render(root) {
  (root || document).querySelectorAll('.md:not([data-done])').forEach(el => {
    if (window.marked) el.innerHTML = marked.parse(el.textContent);
    el.dataset.done = 1;
    if (window.renderMathInElement) renderMathInElement(el, {delimiters: [{left: '$$', right: '$$', display: true}, {left: '$', right: '$', display: false}]});
  });
}
window.addEventListener('load', () => render());
document.addEventListener('htmx:afterSwap', e => render(e.target));

// A block adds keys with `abhyasaKeys.KeyX = '#selector'`.
window.abhyasaKeys = window.abhyasaKeys || {};
document.addEventListener('keydown', e => {
  if (!e.altKey) return;
  const sel = abhyasaKeys[e.code], el = sel && document.querySelector(sel);
  if (el) { e.preventDefault(); el.click(); }
});
