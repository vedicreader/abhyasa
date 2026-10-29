// The Start box. After 250 ms with no typing, the server reads the box (/learn/read) and says what it will do; it makes no
// network call. A dropped PDF goes to the vault; a dropped .md or .txt goes into the box as text. Bound one time, on the
// document, so it works after an hx-boost page change too.
if (!window.abhyasaStart) {
  window.abhyasaStart = true;
  let timer = null;
  const form = () => document.getElementById('start-form');
  const read = () => {
    const f = form(); if (!f) return;
    const p = new URLSearchParams();
    for (const [k, v] of new FormData(f)) if (k !== 'pick') p.append(k, v);
    htmx.ajax('GET', f.dataset.read + '?' + p, {source: '#start-read', target: '#start-read', swap: 'innerHTML'});
  };
  const later = () => { clearTimeout(timer); timer = setTimeout(read, 250); };
  document.addEventListener('input', e => {
    if (e.target.id === 'start-q') { const fl = document.getElementById('start-file'); if (fl) fl.value = ''; later(); }   // your words, not the dropped file
    else if (e.target.closest && e.target.closest('#start-read .opts') && e.target.type === 'number') later();          // the page count is in the line
  });
  const box = e => e.target.closest && e.target.closest('#start-form');
  document.addEventListener('dragover', e => { const f = box(e); if (f && e.dataTransfer.types.includes('Files')) { e.preventDefault(); f.classList.add('drag'); } });
  document.addEventListener('dragleave', e => { const f = box(e); if (f && !f.contains(e.relatedTarget)) f.classList.remove('drag'); });
  const say = text => { const w = document.getElementById('start-will'); if (w) { w.textContent = text; w.classList.add('req-err'); } };
  document.addEventListener('drop', async e => {
    const f = box(e); if (!f) return;
    e.preventDefault(); f.classList.remove('drag');
    const file = e.dataTransfer.files[0]; if (!file) return;
    const name = file.name.toLowerCase(), q = document.getElementById('start-q'), fl = document.getElementById('start-file');
    if (/\.(md|txt)$/.test(name)) {
      q.value = await file.text(); q.dispatchEvent(new Event('input', {bubbles: true}));
      fl.value = file.name; clearTimeout(timer); read();
    } else if (name.endsWith('.pdf')) {
      const body = new FormData(); body.append('f', file);
      say('Reading the PDF…');
      const r = await fetch(f.dataset.drop, {method: 'POST', body, headers: {'HX-Request': 'true'}});
      const html = await r.text();
      if (html.trim().startsWith('<form')) { f.outerHTML = html; htmx.process(form()); form()?.querySelector('#start-q')?.focus(); }
      else say(new DOMParser().parseFromString(html, 'text/html').body.textContent.trim() || 'abhyasa could not read this PDF.');
    } else say('Drop a PDF, a .md or a .txt file.');
  });
  // /add opens Learn with the cursor in the box
  const focus = () => { if (location.hash === '#start') document.getElementById('start-q')?.focus({preventScroll: false}); };
  if (document.readyState === 'complete') focus(); else addEventListener('load', () => setTimeout(focus));   // after voice.js adds the mic
  document.addEventListener('htmx:afterSettle', e => { if (e.detail.target === document.body) focus(); });
}
