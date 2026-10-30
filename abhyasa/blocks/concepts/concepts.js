// The find box on the Concepts page: as you type, only the concepts that match show, and each branch above them opens.
// It folds case and marks as the server does (`ui.fold`), so "magha" finds "Maghā". An empty box gives the tree as it was.
(() => {
  const fold = s => s.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
  function filter(box) {
    const view = document.getElementById('concepts-view'), q = fold(box.value);
    if (!view) return;
    const tree = view.querySelector('.concept-tree');
    if (!tree) return;
    tree.querySelectorAll('details.tree').forEach(d => { if (!('was' in d.dataset)) d.dataset.was = d.open ? '1' : ''; });
    tree.querySelectorAll('li[data-find]').forEach(li => { li.hidden = !!q && !li.dataset.find.includes(q); });
    [...tree.querySelectorAll('details.tree')].reverse().forEach(d => {
      const hit = !!d.querySelector('li[data-find]:not([hidden])');
      d.hidden = !!q && !hit;
      d.open = q ? hit : d.dataset.was === '1';
    });
    let none = view.querySelector('.find-none');
    const any = !!tree.querySelector('li[data-find]:not([hidden])');
    if (q && !any) {
      if (!none) { none = document.createElement('p'); none.className = 'mute empty find-none'; tree.before(none); }
      none.textContent = 'No concept matches. Press Return to search everything.';
    } else if (none) none.remove();
  }
  document.addEventListener('input', e => { if (e.target.id === 'find') filter(e.target); });
})();

// Sort by hand on the tree. Drag a concept by its handle onto a group head, or onto "Not sorted yet", of the same subject: the drop
// posts the move as "Move to…" does. A press on the handle with no drag opens "Move to…", which is also the keyboard way.
// A small form ("Move to…", "Rename", "New group") opens in the `.slot` after its button: its group opens, and Esc or Cancel closes it.
// ⌘Z presses Undo on the Undo bar, except in a text box, where it undoes the typing.
(() => {
  let drag = null;
  const view = () => document.getElementById('concepts-view');
  const target = (e, li) => {
    const s = document.elementFromPoint(e.clientX, e.clientY)?.closest('summary[data-drop]');
    return s && s.dataset.subject === li.dataset.subject ? s : null;
  };
  const end = () => {
    if (!drag) return;
    drag.li.classList.remove('dragging'); drag.over?.classList.remove('drop-on');
    document.documentElement.classList.remove('tree-drag'); drag = null;
  };
  document.addEventListener('pointerdown', e => {
    const g = e.target.closest?.('#concepts-view li[data-slug] > .handle');
    if (!g || e.button !== 0) return;
    e.preventDefault(); g.setPointerCapture(e.pointerId);
    drag = {li: g.closest('li'), x: e.clientX, y: e.clientY, on: false, over: null};
  });
  document.addEventListener('pointermove', e => {
    if (!drag) return;
    if (!drag.on && Math.hypot(e.clientX - drag.x, e.clientY - drag.y) > 4) {
      drag.on = true; drag.li.classList.add('dragging'); document.documentElement.classList.add('tree-drag');
    }
    if (!drag.on) return;
    const t = target(e, drag.li);
    if (t !== drag.over) { drag.over?.classList.remove('drop-on'); t?.classList.add('drop-on'); drag.over = t; }
  });
  document.addEventListener('pointerup', e => {
    if (!drag) return;
    const {li, on, over} = drag;
    end();
    if (!on) { li.querySelector('.move-to')?.click(); return; }
    if (over && window.htmx) htmx.ajax('POST', li.dataset.post, {target: '#concepts-view', swap: 'innerHTML',
      values: {group: over.dataset.drop || '', back: 'tree', at: view()?.dataset.at || ''}});
  });
  document.addEventListener('pointercancel', end);
  const close = slot => { slot.innerHTML = ''; (slot.closest('li')?.querySelector('.move-to') || slot.parentElement.querySelector(':scope > summary .act'))?.focus(); };
  document.addEventListener('click', e => { const c = e.target.closest?.('.slot .slot-close'); if (c) close(c.closest('.slot')); });
  document.addEventListener('htmx:afterSwap', e => {
    const t = e.detail.target;
    if (t.classList?.contains('slot')) { const d = t.closest('details'); if (d) d.open = true; t.querySelector('[autofocus]')?.focus(); }
  });
  window.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !e.metaKey && !e.ctrlKey && !e.altKey) {
      const s = e.target.closest?.('.slot');
      if (s && s.firstChild) { e.preventDefault(); e.stopPropagation(); close(s); }
      return;
    }
    if (e.key.toLowerCase() !== 'z' || !(e.metaKey || e.ctrlKey) || e.shiftKey || e.altKey) return;
    if (e.target.matches?.('textarea, input, select, [contenteditable]')) return;
    const b = document.querySelector('.undo-bar button');
    if (b) { e.preventDefault(); b.click(); }
  }, true);
})();
