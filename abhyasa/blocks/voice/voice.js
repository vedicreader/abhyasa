// Continuous dictation. One press starts it, and it listens until the next press, or until its text box closes.
// vad.js cuts the mic stream at your pauses. Each segment goes to the server as a 16 kHz WAV with its number.
// The server sends the text back in order over server-sent events, and it goes at the end of the box.
abhyasaKeys.KeyD = '#mic';
var abhyasaDict = null;   // var: htmx may load this file again with each card
async function abhyasaMic(btn) {
  if (abhyasaDict) { const same = abhyasaDict.btn === btn; await abhyasaDict.stop(!same); if (same) return; }
  const box = document.getElementById(btn.dataset.into), d = abhyasaDict = {btn, sent: 0, got: 0, sends: [], ended: false};
  const state = () => {
    if (abhyasaDict && abhyasaDict !== d) return;   // a newer dictation owns the button
    const busy = d.sent > d.got, say = btn.querySelector('.say');
    btn.classList.toggle('on', !d.ended); btn.classList.toggle('busy', busy);
    say.textContent = !d.ended ? (busy ? 'Listening · transcribing' : 'Listening') : busy ? 'Transcribing' : 'Speak';
  };
  d.stop = async (now) => {
    if (d.ended) return;
    d.ended = true; state();
    if (d.node) { d.node.port.postMessage('flush'); await d.flushed; }
    d.stream && d.stream.getTracks().forEach(t => t.stop()); d.ac && d.ac.close();
    btn.style.setProperty('--lvl', 0);
    if (abhyasaDict === d) abhyasaDict = null;
    await Promise.all(d.sends);
    if (d.id) fetch(btn.dataset.stop + d.id + '?n=' + d.sent, {method: 'POST'});
    if (now || !document.body.contains(box)) d.es && d.es.close();
  };
  state();
  try {
    d.stream = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true}});
    const r = await (await fetch(btn.dataset.start + '?concept=' + encodeURIComponent(btn.dataset.concept || ''), {method: 'POST'})).json();
    d.id = r.id;
    if (d.ended) { d.stream.getTracks().forEach(t => t.stop()); return fetch(btn.dataset.stop + d.id + '?n=0', {method: 'POST'}); }
    d.es = new EventSource(btn.dataset.events + d.id);
    d.es.onmessage = e => {
      const m = JSON.parse(e.data);
      if (m.done) { d.es.close(); return state(); }
      d.got++;
      if (m.text && document.body.contains(box)) abhyasaAppend(box, m.text);
      if (m.error) btn.title = 'Speech to text failed: ' + m.error;
      state();
    };
    d.ac = new AudioContext();
    await d.ac.audioWorklet.addModule(btn.dataset.vad);
    if (d.ended) return d.stream.getTracks().forEach(t => t.stop());   // stopped while the mic started
    d.node = new AudioWorkletNode(d.ac, 'abhyasa-vad', {processorOptions: {pauses: r.segment}});
    d.flushed = new Promise(ok => d.onflush = ok);
    const mute = d.ac.createGain(); mute.gain.value = 0;
    d.ac.createMediaStreamSource(d.stream).connect(d.node); d.node.connect(mute).connect(d.ac.destination);
    d.node.port.onmessage = e => {
      const m = e.data;
      if (m.flushed) return d.onflush();
      if (m.segment) return d.sends.push(abhyasaSend(btn, d, m.segment, state));
      btn.style.setProperty('--lvl', m.level.toFixed(2)); btn.classList.toggle('talk', m.speech);
      if (!document.body.contains(box)) d.stop(true);   // the question closed
    };
  } catch (e) { btn.title = 'The microphone did not start: ' + e.message; d.node = null; d.stop(true); }
}
async function abhyasaSend(btn, d, pcm, state) {
  const seq = d.sent++, wav = abhyasaWav(pcm);
  state();
  for (let i = 0; i < 6; i++) {   // try again, so that no segment is lost
    try { if ((await fetch(btn.dataset.seg + d.id + '?seq=' + seq, {method: 'POST', body: wav})).ok) return; } catch (e) {}
    await new Promise(ok => setTimeout(ok, 400 * (i + 1)));
  }
}
function abhyasaAppend(box, t) {
  // Text the learner typed stays. The new text goes at the end; the caret follows only when it was at the end.
  const end = box.value.length, atEnd = document.activeElement !== box || (box.selectionStart === end && box.selectionEnd === end);
  box.setRangeText((box.value && !/\s$/.test(box.value) ? ' ' : '') + t, end, end, atEnd ? 'end' : 'preserve');
  box.dispatchEvent(new Event('input', {bubbles: true}));
}
function abhyasaWav(pcm) {
  const m = pcm.length, h = new DataView(new ArrayBuffer(44 + m * 2)), w = (p, s) => [...s].forEach((c, i) => h.setUint8(p + i, c.charCodeAt(0)));
  w(0, 'RIFF'); h.setUint32(4, 36 + m * 2, true); w(8, 'WAVEfmt '); h.setUint32(16, 16, true); h.setUint16(20, 1, true); h.setUint16(22, 1, true);
  h.setUint32(24, 16000, true); h.setUint32(28, 32000, true); h.setUint16(32, 2, true); h.setUint16(34, 16, true); w(36, 'data'); h.setUint32(40, m * 2, true);
  for (let i = 0; i < m; i++) { const s = Math.max(-1, Math.min(1, pcm[i])); h.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true); }
  return new Blob([h], {type: 'audio/wav'});
}
