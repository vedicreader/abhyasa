"The Speaking voice group of the Settings page: pick the engine, the model and the voice, look up and download a model, and play a sample. No test uses the network or the real cache."
import time, pytest
from abhyasa import voice
from abhyasa.settings import val, reset

@pytest.fixture(autouse=True)
def clean(monkeypatch):
    "The browser voice and no key before and after each test, and a fake voice: no model loads."
    monkeypatch.setattr(voice, 'speak', lambda text, *a, **kw: (voice.to_wav([0.] * 2400, 24000), voice.by_letters(text, .1)))
    def back():
        for k in ('voice.out', 'voice.out_model', 'voice.out_voice', 'voice.out_speed'): reset(k)
        voice.set_openai_key('')
        voice.save_settings(voice.settings() | dict(downloaded=[]))
    back(); yield; back()

def test_the_group_shows_the_engines_and_where_they_run(mk):
    t = mk().get('/settings').text
    assert 'id="g-voice"' in t and '>Speaking voice<' in t and 'id="ix-voice"' in t
    for s in ('The browser', 'Kokoro', 'OpenAI', 'A Hugging Face model', 'hosted · OpenAI', 'Play a sample', '>Speed<'): assert s in t, s
    assert 'Set a key first' in t   # OpenAI is off with no key

def test_pick_kokoro_and_a_voice(mk, monkeypatch):
    "Kokoro gets its default model and voice. A new voice saves, and the model stays."
    monkeypatch.setattr(voice, 'cached', lambda m: True)
    cl = mk(['settings'])
    t = cl.post('/settings/voice', data=dict(engine='kokoro')).text
    assert voice.out_current() == ('kokoro', voice.DFLT_KOKORO, 'af_heart', 1.) and 'on this Mac' in t and 'bm_george' in t
    cl.post('/settings/voice', data=dict(engine='kokoro', voice='bm_george'))
    assert voice.out_current()[:3] == ('kokoro', voice.DFLT_KOKORO, 'bm_george')
    cl.post('/settings/voice', data=dict(engine='browser'))
    assert voice.out_current() == ('browser', '', '', 1.) and val('voice.out_voice') == ''
    assert cl.post('/settings/voice', data=dict(engine='espeak')).status_code == 400

def test_openai_needs_a_key_and_keeps_its_voice(mk):
    cl = mk(['settings'])
    cl.post('/settings/voice', data=dict(engine='openai'))
    assert val('voice.out') == 'browser'
    voice.set_openai_key('sk-x-1111')
    t = cl.post('/settings/voice', data=dict(engine='openai', voice='coral')).text
    assert voice.out_current()[:3] == ('openai', voice.DFLT_SPEECH, 'coral') and 'tts-1-hd' in t
    cl.post('/settings/voice', data=dict(engine='openai', model='tts-1'))
    assert voice.out_current()[:3] == ('openai', 'tts-1', 'coral')

def test_the_speed_saves_in_its_range(mk):
    cl = mk(['settings'])
    cl.post('/settings/value', data=dict(name='voice.out_speed', value='3'))
    assert val('voice.out_speed') == 2.

def test_lookup_shows_only_text_to_speech(mk, monkeypatch):
    seen = {}
    def search(q, kind='stt', **kw): seen.update(q=q, kind=kind); return [dict(model='mlx-community/Kokoro-82M-8bit', downloads=5, size=2**20)]
    monkeypatch.setattr(voice, 'search_models', search)
    t = mk(['settings']).get('/settings/voice/search?q=kokoro').text
    assert seen == dict(q='kokoro', kind='tts') and 'Kokoro-82M-8bit' in t and 'Download' in t

def test_download_then_use(mk, monkeypatch):
    "Download fetches the model on the pool, saves it as the voice, and warms it. A downloaded voice model is not in the speech to text table."
    got = []
    monkeypatch.setattr(voice, 'model_size', lambda m: 100)
    def fetch(m):
        got.append(m); d = voice.settings(); d['downloaded'] = [m]; voice.save_settings(d)
    monkeypatch.setattr(voice, 'fetch', fetch)
    here = set()
    monkeypatch.setattr(voice, 'cached', lambda m: m in here or m in got)
    cl = mk(['settings'])
    m = 'mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit'
    assert 'Downloading' in cl.post('/settings/voice/get', data=dict(engine='hf', model=m)).text
    for _ in range(100):
        if 'is ready and in use' in (t := cl.get('/settings/jobs').text): break
        time.sleep(.02)
    assert 'is ready and in use' in t and 'id="voice-out"' in t
    assert got == [m] and voice.out_current()[:2] == ('hf', m)
    page = cl.get('/settings').text
    assert page.count(m) >= 1 and 'downloaded by this page' not in page

def test_play_a_sample(mk, monkeypatch):
    "The sample comes as base64 WAV with the time it took. The browser voice has no sample from the server."
    cl = mk(['settings'])
    assert cl.post('/settings/voice/sample').status_code == 409
    monkeypatch.setattr(voice, 'cached', lambda m: True)
    cl.post('/settings/voice', data=dict(engine='kokoro'))
    d = cl.post('/settings/voice/sample').json()
    assert d['audio'] and d['where'] == 'on this Mac' and d['ms'] >= 0 and len(d['words']) == 12
