// The shared editor list (core/edit.py): keys, the drag by the grip, one open row at a time, live fields, ⌘Z and the Undo bar.
// With the list in focus, and not a text box: W and S move the focus, ⇧W and ⇧S move the row, E opens it, Esc closes it, and a
// letter (A, Q, D, X, R, P, M) presses the button with that `data-key` in the row (A and Q: in the list). Each move posts `act=move&to=<index>`
// to the `data-post` of the row. Only the grip drags. A drop outside the list does nothing.
// ⌘Z presses Undo on the Undo bar, except in a text box, where it undoes the typing.
(() => {
  const BOX = 'textarea, input, select, [contenteditable]:not([contenteditable="false"])';
  const rows = list => [...list.querySelectorAll(':scope > li.edit-row')];
  const rowOf = el => el?.closest?.('ol[data-edit] > li.edit-row');
  const move = (li, to) => {
    const list = li.parentElement, n = rows(list).length;
    if (!li.dataset.post || to < 0 || to >= n || to === rows(list).indexOf(li)) return;
    abhyasaEdit.focus = {list: list.id, id: li.dataset.id};
    htmx.ajax('POST', li.dataset.post, {values: {act: 'move', to: String(to)}, source: li, target: list.id ? '#' + list.id : list, swap: 'outerHTML'});
  };
  const press = (scope, k) => {
    const b = scope?.querySelector(`[data-key="${k}"]`);
    if (b && !b.disabled) { b.click(); return true; }
    return false;
  };
  window.abhyasaEdit = {focus: null, move};

  document.addEventListener('keydown', e => {
    if (e.defaultPrevented || e.altKey) return;
    const t = e.target, inBox = t.matches?.(BOX);
    if (e.key.toLowerCase() === 'z' && (e.metaKey || e.ctrlKey) && !e.shiftKey) {
      if (inBox) return;   // the box undoes the typing
      const b = document.querySelector('#undo-bar button');
      if (b) { e.preventDefault(); b.click(); }
      return;
    }
    const li = rowOf(t);
    if (!li || e.metaKey || e.ctrlKey) return;
    if (inBox) {   // a box types; its first Esc gives the focus back to its row, so the next Esc closes the row
      if (e.key === 'Escape' && !e.shiftKey) { e.preventDefault(); t.blur(); li.focus(); }
      return;
    }
    const list = li.parentElement, all = rows(list), i = all.indexOf(li);
    if (e.key === 'Escape') {
      const d = li.querySelector(':scope > details[open]');
      if (d) { e.preventDefault(); d.open = false; li.focus(); }
      return;
    }
    const k = e.code.startsWith('Key') ? e.code.slice(3) : '';
    if (k === 'W' || k === 'S') {
      e.preventDefault();
      const to = i + (k === 'W' ? -1 : 1);
      if (e.shiftKey) move(li, to); else all[to]?.focus();
    } else if (k === 'E' && !e.shiftKey) {
      const d = li.querySelector(':scope > details');
      if (d) { e.preventDefault(); d.open = true; d.querySelector('.fields')?.querySelector(BOX)?.focus(); }
    } else if ((k === 'A' || k === 'Q') && !e.shiftKey) {
      if (press(list, k)) e.preventDefault();
    } else if ('DXRPM'.includes(k) && k && !e.shiftKey) {
      if (press(li, k)) e.preventDefault();
    }
  }, true);

  // One open row at a time. The open row has the class `open`.
  document.addEventListener('toggle', e => {
    const d = e.target, li = rowOf(d);
    if (!li || d.parentElement !== li) return;
    li.classList.toggle('open', d.open);
    if (d.open) rows(li.parentElement).forEach(r => { if (r !== li) { const o = r.querySelector(':scope > details[open]'); if (o) o.open = false; } });
  }, true);

  // Move up and Move down, the touch way to move.
  document.addEventListener('click', e => {
    const b = e.target.closest?.('[data-move]'), li = rowOf(b);
    if (b && li) { e.preventDefault(); move(li, +b.dataset.move); }
  });

  // A live field with no route of its own posts to the route of its row.
  document.addEventListener('htmx:configRequest', e => {
    const el = e.detail.elt;
    if (el?.dataset?.live && !el.getAttribute('hx-post')) {
      const li = rowOf(el);
      if (li?.dataset.post) e.detail.path = li.dataset.post; else e.preventDefault();
    }
  });

  // Drag by the grip: a line shows where the row goes. A drop outside the list, or in the same place, posts nothing.
  let drag = null;
  const clear = () => { drag?.list.querySelectorAll('.drop-before, .drop-after').forEach(r => r.classList.remove('drop-before', 'drop-after')); };
  const place = ev => {
    const r = drag.list.getBoundingClientRect();
    if (ev.clientX < r.left || ev.clientX > r.right || ev.clientY < r.top - 8 || ev.clientY > r.bottom + 8) return null;
    const all = rows(drag.list);
    let to = all.findIndex(x => ev.clientY < x.getBoundingClientRect().top + x.getBoundingClientRect().height / 2);
    if (to < 0) to = all.length;
    return to;
  };
  document.addEventListener('pointerdown', e => {
    const g = e.target.closest?.('ol[data-edit] > li.edit-row > .grip');
    if (!g || e.button !== 0) return;
    e.preventDefault(); g.setPointerCapture(e.pointerId);
    const li = g.parentElement;
    drag = {li, list: li.parentElement, from: rows(li.parentElement).indexOf(li), to: null};
    li.classList.add('dragging');
  });
  document.addEventListener('pointermove', e => {
    if (!drag) return;
    clear();
    drag.to = place(e);
    const all = rows(drag.list);
    if (drag.to === null) return;
    if (drag.to < all.length) all[drag.to].classList.add('drop-before'); else all.at(-1)?.classList.add('drop-after');
  });
  const end = (e, ok) => {
    if (!drag) return;
    const d = drag; clear(); d.li.classList.remove('dragging'); drag = null;
    if (!ok || d.to === null) return;
    const to = d.to > d.from ? d.to - 1 : d.to;   // the index after the row leaves its place
    move(d.li, to);
  };
  document.addEventListener('pointerup', e => end(e, true));
  document.addEventListener('pointercancel', e => end(e, false));

  // Undo (the button or ⌘Z) puts the focus back on the row that the change touched (`data-row` of the button), else on the bar.
  document.addEventListener('click', e => {
    const b = e.target.closest?.('#undo-bar button');
    if (b) abhyasaEdit.focus = {id: b.dataset.row || '', undo: true};
  }, true);
  // After a swap: the focus goes back to the moved row, and a new row gets the focus in its first field, with the text selected.
  const back = () => {
    const f = abhyasaEdit.focus;
    if (!f) return;
    const li = f.id && document.querySelector(`ol[data-edit] > li.edit-row[data-id="${CSS.escape(f.id)}"]`);
    if (li) li.focus();
    else if (f.undo) { const bar = document.getElementById('undo-bar'); (bar?.querySelector('button') || bar)?.focus(); }
    else return;   // the moved row is not back yet
    abhyasaEdit.focus = null;
  };
  document.addEventListener('htmx:afterSettle', () => {
    back();
    document.querySelectorAll('ol[data-edit] > li.edit-row[data-fresh]').forEach(li => {
      delete li.dataset.fresh;
      const box = li.querySelector('.fields')?.querySelector(BOX);
      if (box) { box.focus(); box.select?.(); } else li.focus();
    });
  });

  // The Undo bar is bright for `data-secs` seconds after a change, then quiet. Undo still works.
  let quiet = null;
  const fresh = () => {
    const bar = document.getElementById('undo-bar');
    if (!bar || !bar.children.length) return;
    bar.classList.add('fresh'); clearTimeout(quiet);
    quiet = setTimeout(() => bar.classList.remove('fresh'), 1000 * (+bar.dataset.secs || 8));
  };
  document.addEventListener('htmx:oobAfterSwap', e => { if (e.detail.target?.id === 'undo-bar') fresh(); });
  document.addEventListener('htmx:afterRequest', () => setTimeout(back, 50));   // an Undo answer can swap only out of band: then no settle comes
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fresh); else fresh();
})();
