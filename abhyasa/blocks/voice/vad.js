// A voice activity detector in an AudioWorklet. It cuts the mic stream into speech segments at pauses.
// Each 20 ms frame is speech when its energy is well above a noise floor that follows the room. Very noisy frames
// (many zero crossings, as in hiss) must be louder. A segment starts after 3 speech frames, with 300 ms of audio
// from before the start, so the first sound is not cut. It ends after 700 ms of silence (250 ms after 8 s), or at 12 s.
// Segments go to the page as 16 kHz mono Float32Array. With `pauses` off, the cut is every 10 s.
const F = 0.02, PRE = 15, ONSET = 3, HANG = 35, HANG_LONG = 12, LONG = 400, CAP = 600, FIXED = 500, MIN_VOICED = 8;
class AbhyasaVad extends AudioWorkletProcessor {
  constructor(o) {
    super();
    this.pauses = (o.processorOptions || {}).pauses !== false;
    this.frame = Math.round(sampleRate * F); this.buf = new Float32Array(this.frame); this.n = 0;
    this.floor = 0.002; this.run = 0; this.hang = 0; this.speech = false; this.pre = []; this.seg = []; this.voiced = 0; this.tick = 0;
    this.port.onmessage = e => { if (e.data === 'flush') { this.emit(); this.port.postMessage({flushed: true}); } };
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      this.buf[this.n++] = ch[i];
      if (this.n === this.frame) { this.step(this.buf.slice()); this.n = 0; }
    }
    return true;
  }
  step(f) {
    let e = 0, z = 0;
    for (let i = 0; i < f.length; i++) { e += f[i] * f[i]; if (i && (f[i] >= 0) !== (f[i - 1] >= 0)) z++; }
    const rms = Math.sqrt(e / f.length), zcr = z / f.length * (sampleRate / 16000);   // crossings per 16 kHz sample
    if (!this.speech) this.floor = Math.max(1e-4, rms < this.floor ? 0.8 * this.floor + 0.2 * rms : 0.995 * this.floor + 0.005 * rms);
    const thr = Math.max(this.floor * (zcr > 0.45 ? 6 : 3), 0.004), isSp = rms > thr;
    this.run = isSp ? this.run + 1 : 0;
    if (++this.tick % 3 === 0) this.port.postMessage({level: Math.min(1, Math.sqrt(rms) * 2.5), speech: this.speech});
    if (!this.pauses) {
      this.seg.push(f); if (isSp) this.voiced++;
      if (this.seg.length >= FIXED) this.emit();
      return;
    }
    if (!this.speech) {
      this.pre.push(f); if (this.pre.length > PRE) this.pre.shift();
      if (this.run >= ONSET) { this.speech = true; this.seg = this.pre; this.pre = []; this.voiced = ONSET; this.hang = 0; }
      return;
    }
    this.seg.push(f);
    if (isSp) { this.voiced++; this.hang = 0; } else this.hang++;
    if (this.hang >= (this.seg.length > LONG ? HANG_LONG : HANG) || this.seg.length >= CAP) this.emit();
  }
  emit() {
    const keep = this.seg.length - Math.max(0, this.hang - 10);   // keep 200 ms of the silence at the end
    const seg = this.seg.slice(0, keep), voiced = this.voiced;
    this.seg = []; this.voiced = 0; this.hang = 0; this.speech = false; this.run = 0;
    if (voiced < MIN_VOICED || !seg.length) return;   // a click or a cough, not words
    const n = seg.length * this.frame, all = new Float32Array(n);
    seg.forEach((s, i) => all.set(s, i * this.frame));
    const r = sampleRate / 16000, m = Math.floor(n / r), out = new Float32Array(m);
    for (let i = 0; i < m; i++) {   // the mean over each input window: a simple low-pass before the rate falls
      const a = Math.floor(i * r), b = Math.max(a + 1, Math.floor((i + 1) * r));
      let s = 0; for (let j = a; j < b; j++) s += all[j];
      out[i] = s / (b - a);
    }
    this.port.postMessage({segment: out}, [out.buffer]);
  }
}
registerProcessor('abhyasa-vad', AbhyasaVad);
