// The Settings page. The − and + buttons and the sliders of a setting row are in core.js, as the Profile page has rows too.
// "Find a setting" shows only the rows whose label or help has the words, and opens the "More" parts that hold them.
(() => {
  document.addEventListener('input', e => { if (e.target.id === 'sfind') find(e.target.value); });
  function find(q) {
    const ws = q.toLowerCase().split(/\s+/).filter(Boolean);
    document.querySelectorAll('.sgroup').forEach(g => {
      let any = !ws.length;
      g.querySelectorAll('[data-find]').forEach(r => {
        const hit = ws.every(w => r.dataset.find.includes(w));
        r.hidden = ws.length > 0 && !hit;
        if (hit && ws.length) { any = true; const d = r.closest('details.more'); if (d) d.open = true; }
      });
      g.hidden = ws.length > 0 && !any;
      const ix = document.getElementById('ix-' + g.id.slice(2));
      if (ix) ix.hidden = g.hidden;
    });
  }
})();

// "Play a sample" in Speaking voice: the browser voice speaks the line here; another engine gets the line from the server as a WAV,
// and the line under the button gives the time to the audio. It plays only after the click.
(() => {
  document.addEventListener('click', async e => {
    const b = e.target.closest && e.target.closest('button[data-sample]');
    if (!b) return;
    const said = b.parentElement.querySelector('.out-said'), tell = t => { if (said) said.textContent = t; };
    if (b.dataset.engine === 'browser') {
      if (!('speechSynthesis' in window)) return tell('This browser has no voice.');
      speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance(b.dataset.text));
      return tell('The browser voice speaks on this Mac.');
    }
    tell('Getting the sample…'); b.disabled = true;
    try {
      const r = await fetch(b.dataset.sample, {method: 'POST'}), d = await r.json().catch(() => ({}));
      if (!r.ok || !d.audio) return tell(d.error || 'The voice did not answer.');
      const url = URL.createObjectURL(new Blob([Uint8Array.from(atob(d.audio), c => c.charCodeAt(0))], {type: 'audio/wav'})), a = new Audio(url);
      a.addEventListener('ended', () => URL.revokeObjectURL(url), {once: true});
      await a.play();
      tell(`${(d.ms / 1000).toFixed(1)} s to the audio${d.cached ? ' (said before)' : ''} · ${d.where === 'hosted' ? 'hosted · OpenAI' : 'on this Mac'}`);
    } catch (err) { tell('The voice did not answer.'); }
    finally { b.disabled = false; }
  });
})();
