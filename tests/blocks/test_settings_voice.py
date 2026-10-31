"The Speaking voice group of the Settings page: pick the engine and the voice, download Pocket TTS, and play a sample. No test uses the network or the real cache."
import re, time, pytest
from abhyasa import voice
from abhyasa.settings import val, reset, update_settings

@pytest.fixture(autouse=True)
def clean(monkeypatch):
    "The default voice and no key before and after each test, and a fake voice: no model loads."
    monkeypatch.setattr(voice, 'speak', lambda text, *a, **kw: (voice.to_wav([0.] * 2400, 24000), voice.by_letters(text, .1)))
    def back():
        for k in ('voice.out', 'voice.out_model', 'voice.out_voice', 'voice.out_speed'): reset(k)
        voice.set_openai_key('')
        voice.save_settings(voice.settings() | dict(downloaded=[]))
    back(); yield; back()

def test_the_group_shows_the_engines_and_where_they_run(mk, monkeypatch):
    "Three engines. Pocket TTS is the default, with its voices in a list. The speed row is only for OpenAI."
    monkeypatch.setattr(voice, 'cached', lambda m: True)
    t = mk().get('/settings').text
    assert 'id="g-voice"' in t and '>Speaking voice<' in t and 'id="ix-voice"' in t
    for s in ('Pocket TTS', 'The browser', 'OpenAI', 'hosted · OpenAI', 'Play a sample', '<option value="caro_davy" selected>Caro Davy</option>', '>Peter Yearsley<'): assert s in t, s
    assert 'Set a key first' in t and 'hidden' in re.search(r'<ul[^>]*id="out-speed"[^>]*>', t)[0] and 'Kokoro' not in t and 'Hugging Face model' not in t
    assert t.count('<option value=', t.index('name="voice"')) >= len(voice.POCKET_VOICES)

def test_pick_a_voice_and_the_browser(mk, monkeypatch):
    "A new voice saves. The browser has no voice. An old Kokoro setting shows as Pocket TTS with caro_davy."
    monkeypatch.setattr(voice, 'cached', lambda m: True)
    cl = mk(['settings'])
    t = cl.post('/settings/voice', data=dict(engine='pocket', voice='mary')).text
    assert voice.out_current() == ('pocket', voice.POCKET, 'mary', 1.) and 'on this Mac' in t and 'value="mary" selected' in t
    cl.post('/settings/voice', data=dict(engine='browser'))
    assert voice.out_current() == ('browser', '', '', 1.) and val('voice.out_voice') == ''
    assert cl.post('/settings/voice', data=dict(engine='espeak')).status_code == 400
    update_settings('voice', out='kokoro', out_model='mlx-community/Kokoro-82M-bf16', out_voice='af_heart')
    assert 'value="caro_davy" selected' in cl.get('/settings').text

def test_openai_needs_a_key_and_keeps_its_voice(mk):
    "OpenAI needs a key. With a key, its voice and model save, and its speed row shows."
    cl = mk(['settings'])
    cl.post('/settings/voice', data=dict(engine='openai'))
    assert val('voice.out') == 'pocket'
    voice.set_openai_key('sk-x-1111')
    t = cl.post('/settings/voice', data=dict(engine='openai', voice='coral')).text
    assert voice.out_current()[:3] == ('openai', voice.DFLT_SPEECH, 'coral') and 'tts-1-hd' in t and 'hidden' not in re.search(r'<ul[^>]*id="out-speed"[^>]*>', t)[0]
    cl.post('/settings/voice', data=dict(engine='openai', model='tts-1'))
    assert voice.out_current()[:3] == ('openai', 'tts-1', 'coral')

def test_the_speed_saves_in_its_range(mk):
    cl = mk(['settings'])
    cl.post('/settings/value', data=dict(name='voice.out_speed', value='3'))
    assert val('voice.out_speed') == 2.

def test_first_use_download_then_use(mk, monkeypatch):
    "Before the download, the voice part says that the browser speaks, with Download. Download gets Pocket TTS on the pool, and warms it. It is not in the speech to text table."
    got = []
    monkeypatch.setattr(voice, 'model_size', lambda m: 100)
    def fetch(m):
        got.append(m); d = voice.settings(); d['downloaded'] = [m]; voice.save_settings(d)
    monkeypatch.setattr(voice, 'fetch', fetch)
    monkeypatch.setattr(voice, 'cached', lambda m: m in got)
    cl = mk(['settings'])
    assert 'The voice is not on this Mac yet. Until you download it, the browser speaks.' in cl.get('/settings').text
    assert 'Downloading The voice (Pocket TTS)' in cl.post('/settings/voice/get', data=dict(engine='pocket')).text
    for _ in range(100):
        if 'is ready and in use' in (t := cl.get('/settings/jobs').text): break
        time.sleep(.02)
    assert 'The voice (Pocket TTS) is ready and in use' in t and 'id="voice-out"' in t
    assert got == [voice.POCKET] and voice.out_current()[:3] == ('pocket', voice.POCKET, 'caro_davy')
    page = cl.get('/settings').text
    assert 'not on this Mac yet. Until' not in page and 'downloaded by this page' not in page
    assert cl.post('/settings/voice/get', data=dict(engine='kokoro')).status_code == 400

def test_play_a_sample(mk, monkeypatch):
    "The sample comes as base64 WAV with the time it took. The browser voice, and Pocket before its download, have no sample from the server."
    cl = mk(['settings'])
    monkeypatch.setattr(voice, 'cached', lambda m: False)
    assert cl.post('/settings/voice/sample').status_code == 409
    cl.post('/settings/voice', data=dict(engine='browser'))
    assert cl.post('/settings/voice/sample').status_code == 409
    monkeypatch.setattr(voice, 'cached', lambda m: True)
    cl.post('/settings/voice', data=dict(engine='pocket'))
    d = cl.post('/settings/voice/sample').json()
    assert d['audio'] and d['where'] == 'on this Mac' and d['ms'] >= 0 and len(d['words']) == 12
