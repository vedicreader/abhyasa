// The talk type (`pane=1&talk=1`, Page in ui.py): a page in the side pane of a talk, for a room to read from far away.
// The page fits its window. First the type gets smaller, down to a floor of 22 px for the passage. When it still does not fit,
// the passage shows one page at a time, with a fade at the foot while more pages come. The talk tells the page number (the
// `page` of the `pane` stage message), never pixels, so the presenter window and the audience window each show the same page
// at their own size. The talk calls `abhyasaTalkPage.set(n)`; `abhyasaTalkPage.pages` is the number of pages here.
(() => {
  if (window.abhyasaTalkPage) return;
  const root = document.documentElement, FLOOR = 22;
  let page = 0, pages = 1, step = 0;
  const box = () => document.querySelector('.talk-step #passage');
  const over = () => document.scrollingElement.scrollHeight > innerHeight + 1;
  function show() {
    const p = box(), label = document.querySelector('.talk-step .talk-page');
    const n = Math.max(0, Math.min(page, pages - 1));
    if (p) { p.scrollTop = n * step; p.classList.toggle('more', n < pages - 1); }
    if (label) { label.hidden = pages < 2; label.textContent = ` · page ${n + 1} of ${pages}`; }
  }
  function fit() {
    const p = box();
    if (!p) return;
    root.style.setProperty('--tt', '1'); p.classList.remove('paged', 'more'); p.style.height = ''; pages = 1; step = 0;
    const base = parseFloat(getComputedStyle(p).fontSize);
    for (let s = 1; over() && base * s > FLOOR + .01;) { s = Math.max(FLOOR / base, s - .05); root.style.setProperty('--tt', String(s)); }
    if (over()) {   // pages: the passage box ends at the foot of the window, in whole lines
      const lh = parseFloat(getComputedStyle(p).lineHeight) || base * 1.5;
      const h = Math.max(2 * lh, Math.floor((p.clientHeight - (document.scrollingElement.scrollHeight - innerHeight)) / lh) * lh);
      p.style.height = h + 'px'; p.classList.add('paged');
      step = h; pages = Math.min(20, Math.max(1, Math.ceil((p.scrollHeight - 1) / h)));
    }
    show();
  }
  window.abhyasaTalkPage = {set(n) { page = Number.isInteger(n) && n >= 0 ? n : 0; show(); }, get pages() { return pages; }, get page() { return page; }, fit};
  const later = () => requestAnimationFrame(fit);
  addEventListener('resize', later); addEventListener('load', later);
  document.fonts?.ready.then(later);
  document.querySelectorAll('.talk-step img').forEach(i => { i.addEventListener('load', later); i.addEventListener('error', later); });
  later();
})();
