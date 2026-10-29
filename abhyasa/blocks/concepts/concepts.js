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
