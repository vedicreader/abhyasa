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
})();
