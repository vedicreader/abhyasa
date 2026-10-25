// Record 16 kHz mono WAV in the browser, post it, and append the transcript to a text box.
abhyasaKeys.KeyD = '#mic';
var abhyasaRec = null;   // var: htmx may load this file again with each card
async function abhyasaMic(btn) {
  if (abhyasaRec) return abhyasaRec.stop();
  const stream = await navigator.mediaDevices.getUserMedia({audio: true});
  const ctx = new AudioContext(), src = ctx.createMediaStreamSource(stream), node = ctx.createScriptProcessor(4096, 1, 1), bufs = [];
  node.onaudioprocess = e => bufs.push(new Float32Array(e.inputBuffer.getChannelData(0)));
  src.connect(node); node.connect(ctx.destination);
  const label = btn.firstChild;
  btn.classList.add('on'); label.textContent = 'Stop ';
  abhyasaRec = { stop: async () => {
    node.disconnect(); src.disconnect(); stream.getTracks().forEach(t => t.stop());
    btn.classList.remove('on'); label.textContent = 'Listening… '; abhyasaRec = null;
    const wav = abhyasaWav(bufs, ctx.sampleRate); ctx.close();
    try {
      const r = await fetch(btn.dataset.url + '?hint=' + encodeURIComponent(btn.dataset.hint || ''), {method: 'POST', body: wav});
      const t = (await r.json()).text || '';
      const box = document.getElementById(btn.dataset.into);
      box.value = (box.value ? box.value.trimEnd() + ' ' : '') + t; box.focus();
    } finally { label.textContent = 'Speak '; }
  }};
}
function abhyasaWav(bufs, rate) {
  const n = bufs.reduce((a, b) => a + b.length, 0), ratio = rate / 16000, m = Math.floor(n / ratio), pcm = new Int16Array(m);
  const all = new Float32Array(n); let o = 0; bufs.forEach(b => { all.set(b, o); o += b.length; });
  for (let i = 0; i < m; i++) { const s = Math.max(-1, Math.min(1, all[Math.floor(i * ratio)])); pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff; }
  const h = new DataView(new ArrayBuffer(44)), w = (p, s) => [...s].forEach((c, i) => h.setUint8(p + i, c.charCodeAt(0)));
  w(0, 'RIFF'); h.setUint32(4, 36 + m * 2, true); w(8, 'WAVEfmt '); h.setUint32(16, 16, true); h.setUint16(20, 1, true); h.setUint16(22, 1, true);
  h.setUint32(24, 16000, true); h.setUint32(28, 32000, true); h.setUint16(32, 2, true); h.setUint16(34, 16, true); w(36, 'data'); h.setUint32(40, m * 2, true);
  return new Blob([h, pcm], {type: 'audio/wav'});
}
