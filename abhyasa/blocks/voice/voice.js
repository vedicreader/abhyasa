// Continuous dictation. One press starts it, and it listens until the next press, or until its text box closes.
// vad.js cuts the mic stream at your pauses. Each segment goes to the server as a 16 kHz WAV with its number.
// The server sends the text back in order over server-sent events, and it goes at the end of the box.
var abhyasaDict = window.abhyasaDict || null;   // var: htmx may load this file again with each page; a running dictation stays
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

// Voice anywhere. A box with `data-mic` (and each box in a demo) gets a small mic of its own. ⌥D speaks into the box in focus,
// on any page: with its own mic, or with the floating one. With no box in focus, ⌥D presses the main mic of the page.
// A second ⌥D stops the dictation.
var abhyasaBox = 'textarea, input[type=text], input[type=search], input:not([type])';
function abhyasaMics(root) {
  const tpl = document.getElementById('mic-float');
  if (!tpl) return;
  (root && root.querySelectorAll ? root : document).querySelectorAll('textarea[data-mic], input[data-mic], .demo-card textarea').forEach(box => {
    if (box.dataset.micDone) return;
    box.dataset.micDone = 1;
    if (!box.id) box.id = 'box-' + Math.random().toString(36).slice(2, 8);
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'mic mini'; b.title = 'Speak into this box. ⌥D does it too, when the box has focus.';
    for (const k of ['vad', 'start', 'seg', 'stop', 'events']) b.dataset[k] = tpl.dataset[k];
    b.dataset.into = box.id;
    b.innerHTML = '<span class="say">Speak</span><i class="lvl"></i>';
    b.addEventListener('click', () => abhyasaMic(b));
    const wrap = document.createElement('span');
    wrap.className = 'micbox';
    box.replaceWith(wrap); wrap.append(box, b);
  });
}
if (!window.abhyasaVoiceOn) {
  window.abhyasaVoiceOn = true;
  window.addEventListener('load', () => abhyasaMics());
  document.addEventListener('htmx:afterSettle', e => abhyasaMics());
  document.addEventListener('rupaka:ready', () => abhyasaMics());
  document.addEventListener('keydown', e => {
    if (!e.altKey || e.code !== 'KeyD') return;
    e.preventDefault();
    if (abhyasaDict) return abhyasaMic(abhyasaDict.btn);
    const a = document.activeElement, box = a && a.matches && a.matches(abhyasaBox) ? a : null;
    if (box) {
      const own = box.id && document.querySelector(`.mic[data-into="${box.id}"]`);
      if (own) return abhyasaMic(own);
      const f = document.getElementById('mic-float');
      if (!f) return;
      if (!box.id) box.id = 'box-' + Math.random().toString(36).slice(2, 8);
      f.dataset.into = box.id;
      return abhyasaMic(f);
    }
    const m = document.querySelector('#mic') || document.querySelector('.mic.mini');
    if (m) abhyasaMic(m);
  });
}
