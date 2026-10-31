"One real check of the speech on this Mac: Pocket TTS says a line with caro_davy, and Qwen3-ASR writes it down. The first run downloads about 1.2 GB, so the test runs only with ABHYASA_REAL_SPEECH=1 and the extras `voice` and `whisper`."
import io, os, re, time, wave, pytest
from abhyasa import voice

pytestmark = pytest.mark.skipif(not os.getenv('ABHYASA_REAL_SPEECH'), reason='set ABHYASA_REAL_SPEECH=1 to run the real speech models')
LINE = 'A prime number has exactly two divisors: one and itself.'

def words(s): return re.findall(r"[a-z']+", s.lower())

def test_pocket_says_a_line_and_qwen3_writes_it_down():
    "The voice gives 24 kHz audio with one time for each word, and the speech model gets back at least 9 of the 10 words."
    t = time.time(); wav, ts = voice.speak(LINE, 'pocket', voice='caro_davy'); say = time.time() - t
    t = time.time(); wav2, _ = voice.speak('The guide reads each step aloud.', 'pocket', voice='caro_davy'); say2 = time.time() - t
    t = time.time(); text = voice.transcribe(wav, 'mlx', hint='prime number, divisors'); hear = time.time() - t
    t = time.time(); voice.transcribe(wav2, 'mlx'); hear2 = time.time() - t
    print(f'\nPocket TTS: first line {say:.2f} s for {voice.wav_seconds(wav):.2f} s of audio (with the load), second line {say2:.2f} s for {voice.wav_seconds(wav2):.2f} s.'
          f'\nQwen3-ASR: first clip {hear:.2f} s (with the load), second clip {hear2:.2f} s. It wrote: {text!r}')
    assert voice.wav_seconds(wav) > 2 and len(ts) == len(LINE.split()) and ts == sorted(ts)
    with wave.open(io.BytesIO(wav)) as w: assert w.getframerate() == 24000
    got = set(words(text))
    assert sum(w in got for w in words(LINE)) >= 9, text
    voice.unload(); voice.unload('tts')
