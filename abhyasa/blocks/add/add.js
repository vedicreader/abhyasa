// Add: only the fields of the chosen kind show and send. A hidden fieldset is disabled, so its boxes do not go with the form.
// The cursor goes to the first box only after a pick with the pointer: the arrow keys move through the choice and keep the focus there.
(() => {
  const form = document.querySelector('.add-form'); if (!form) return;
  let pointer = false;
  form.querySelector('.modes-pick')?.addEventListener('pointerdown', () => { pointer = true; });
  const show = () => {
    const k = form.querySelector('input[name=kind]:checked')?.value || 'doc';
    form.querySelectorAll('fieldset').forEach(f => { const on = f.classList.contains('add-' + k); f.hidden = f.disabled = !on; });
    if (pointer) form.querySelector(`.add-${k} input, .add-${k} textarea`)?.focus({preventScroll: true});
    pointer = false;
  };
  form.addEventListener('change', e => { if (e.target.name === 'kind') show(); });
  // A paper (an arXiv id or address, or a PDF link) is read in full: the count of pages to read goes, and one muted line says so.
  // The server also ignores the count for a paper (is_paper in sources.py).
  const PAPER = /^\s*(?:arxiv:\s*)?(?:\d{4}\.\d{4,5}(?:v\d+)?|(?:https?:\/\/)?(?:www\.|export\.)?arxiv\.org\/(?:abs|pdf)\/\S+|https?:\/\/[^\s?#]+\.pdf(?:[?#]\S*)?)\s*$/i;
  const url = form.querySelector('input[name=url]'), pages = form.querySelector('.add-link .pages'), note = form.querySelector('.add-link .paper-note');
  const paper = () => {
    if (!url || !pages || !note) return;
    const on = PAPER.test(url.value);
    pages.hidden = on; pages.querySelector('input').disabled = on; note.hidden = !on;
  };
  url?.addEventListener('input', paper); paper();
})();
