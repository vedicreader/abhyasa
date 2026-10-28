// Add: only the fields of the chosen kind show and send. A hidden fieldset is disabled, so its boxes do not go with the form.
(() => {
  const form = document.querySelector('.add-form'); if (!form) return;
  const show = () => {
    const k = form.querySelector('input[name=kind]:checked')?.value || 'doc';
    form.querySelectorAll('fieldset').forEach(f => { const on = f.classList.contains('add-' + k); f.hidden = f.disabled = !on; });
    form.querySelector(`.add-${k} input, .add-${k} textarea`)?.focus({preventScroll: true});
  };
  form.addEventListener('change', e => { if (e.target.name === 'kind') show(); });
})();
