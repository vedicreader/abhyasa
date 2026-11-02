"The Speaking voice group of the Settings page: pick the engine and the voice, download Pocket TTS, and play a sample. No test uses the network or the real cache."
import re, threading, time, pytest
from abhyasa import models as voice
from abhyasa.learner import val, reset, update_settings

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
    "Four engines. Pocket TTS is the default, with its voices in a list. The speed row is only for OpenAI."
    monkeypatch.setattr(voice, 'cached', lambda m: True)
    t = mk().get('/settings').text
    assert 'id="g-voice"' in t and '>Speaking voice<' in t and 'id="ix-voice"' in t
    for s in ('Pocket TTS', 'Kokoro', 'The browser', 'OpenAI', 'hosted · OpenAI', 'Play a sample', '<option value="caro_davy" selected>Caro Davy</option>', '>Peter Yearsley<'): assert s in t, s
    assert 'Set a key first' in t and 'hidden' in re.search(r'<ul[^>]*id="out-speed"[^>]*>', t)[0] and 'Hugging Face model' not in t
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
    got, go = [], threading.Event()   # the download waits until the test has read its line: a fast machine ends it first
    monkeypatch.setattr(voice, 'model_size', lambda m: 100)
    def fetch(m):
        go.wait(10); got.append(m); d = voice.settings(); d['downloaded'] = [m]; voice.save_settings(d)
    monkeypatch.setattr(voice, 'fetch', fetch)
    monkeypatch.setattr(voice, 'cached', lambda m: m in got)
    cl = mk(['settings'])
    assert 'The voice is not on this Mac yet. Until you download it, the browser speaks.' in cl.get('/settings').text
    assert 'Downloading The voice (Pocket TTS)' in cl.post('/settings/voice/get', data=dict(engine='pocket')).text
    go.set()
    for _ in range(100):
        if 'is ready and in use' in (t := cl.get('/settings/jobs').text): break
        time.sleep(.02)
    assert 'The voice (Pocket TTS) is ready and in use' in t and 'id="voice-out"' in t
    assert got == [voice.POCKET] and voice.out_current()[:3] == ('pocket', voice.POCKET, 'caro_davy')
    page = cl.get('/settings').text
    assert 'not on this Mac yet. Until' not in page and 'downloaded by this page' not in page
    assert cl.post('/settings/voice/get', data=dict(engine='espeak')).status_code == 400

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

def test_a_missing_voice_says_so_one_time(mk, monkeypatch):
    "When Pocket TTS is not installed, the voice part says so in one plain line, with no `failed:` prefix, and Play a sample hides (settings.css)."
    def no_pocket(*a, **kw): raise RuntimeError(voice.POCKET_MISSING)
    monkeypatch.setattr(voice, 'speak', no_pocket); monkeypatch.setattr(voice, 'cached', lambda m: True)
    cl = mk(['settings'])
    cl.post('/settings/voice', data=dict(engine='pocket'))
    for _ in range(200):
        if 'loading' not in (s := cl.get('/settings/voice/status').text): break
        time.sleep(.02)
    assert voice.POCKET_MISSING == 'Pocket TTS is not installed. Install it with: pip install "abhyasa[voice]". Until then, the browser speaks.'
    assert 'out-failed' in s and 'failed:' not in s and 'on this Mac' not in s
    part = re.search(r'<div[^>]*id="voice-out".*', cl.get('/settings').text, re.S)[0]
    said = voice.POCKET_MISSING.replace('"', '&quot;')
    assert part.count(said) + part.count(voice.POCKET_MISSING) == 1 and 'failed:' not in part and 'class="out-line out-sample"' in part

def voices_in(t) -> list:
    "The values of the Voice list in a part of the page."
    return re.findall(r'<option value="([^"]+)"', t[t.index('name="voice"'):])

def test_the_voice_list_has_only_the_voices_of_the_model(mk):
    "tts-1 lists its 9 voices, with no Ballad. gpt-4o-mini-tts lists all 13."
    cl = mk(['settings']); voice.set_openai_key('sk-x-1111')
    t = cl.post('/settings/voice', data=dict(engine='openai', model='tts-1')).text
    assert voices_in(t) == list(voice.TTS1_VOICES) and 'ballad' not in voices_in(t)
    t = cl.post('/settings/voice', data=dict(engine='openai', model='gpt-4o-mini-tts')).text
    assert voices_in(t) == list(voice.OPENAI_VOICES) and 'ballad' in voices_in(t)

def test_a_model_change_keeps_a_voice_that_works(mk):
    "Ballad with gpt-4o-mini-tts, then tts-1-hd: the voice becomes Coral, and one line says so. A voice that works stays, with no line."
    cl = mk(['settings']); voice.set_openai_key('sk-x-1111')
    cl.post('/settings/voice', data=dict(engine='openai', voice='ballad'))
    t = cl.post('/settings/voice', data=dict(engine='openai', model='tts-1-hd')).text
    assert voice.out_current()[:3] == ('openai', 'tts-1-hd', 'coral') and val('voice.out_voice') == 'coral'
    assert 'Ballad does not work with tts-1-hd, so the voice is Coral now.' in t and 'value="coral" selected' in t
    cl.post('/settings/voice', data=dict(engine='openai', voice='nova'))
    assert 'does not work' not in cl.post('/settings/voice', data=dict(engine='openai', model='tts-1')).text
    update_settings('voice', out_model='tts-1-hd', out_voice='ballad')   # an old setting from before the check
    assert 'Ballad does not work with tts-1-hd, so the voice is Coral now.' in cl.get('/settings').text

def test_the_voice_saves_at_once_with_no_call_to_openai(mk, monkeypatch):
    "Pick OpenAI, a model and a voice: each save answers at once. No save calls OpenAI: only Play a sample and the guide do."
    calls = []
    def slow(url, **kw): calls.append(url); time.sleep(3)
    monkeypatch.setattr(voice, 'http_post', slow)
    cl = mk(['settings']); voice.set_openai_key('sk-x-1111')
    for d in (dict(engine='openai'), dict(engine='openai', model='tts-1-hd'), dict(engine='openai', voice='nova'), dict(engine='openai', model='gpt-4o-mini-tts')):
        t = time.time(); r = cl.post('/settings/voice', data=d)
        assert r.status_code == 200 and time.time() - t < .5, d
    assert calls == []

def test_kokoro_says_how_to_install_it(mk, monkeypatch):
    "Without the kokoro extra, the Kokoro choice is off, with one plain line that gives the install command. Nothing saves or downloads."
    monkeypatch.setattr(voice, 'kokoro_installed', lambda: False)
    cl = mk(['settings'])
    t = cl.post('/settings/voice', data=dict(engine='kokoro')).text
    assert val('voice.out') == 'pocket' and re.search(r'<input type="radio" name="engine" value="kokoro" disabled>', t)
    assert 'Install it first: pip install &quot;abhyasa[kokoro]&quot;, then start abhyasa again.' in t or 'Install it first: pip install "abhyasa[kokoro]", then start abhyasa again.' in t
    assert 'Downloading' not in cl.post('/settings/voice/get', data=dict(engine='kokoro')).text

def test_kokoro_downloads_then_speaks_with_its_voices(mk, monkeypatch):
    "With the extra: Kokoro lists its US and UK voices, says that the browser speaks until the download, and Download gets only its files."
    got, go = [], threading.Event()
    monkeypatch.setattr(voice, 'kokoro_installed', lambda: True)
    monkeypatch.setattr(voice, 'model_size', lambda m: 100)
    monkeypatch.setattr(voice, 'cached', lambda m: m in got)
    def fetch(m): go.wait(10); got.append(m)
    monkeypatch.setattr(voice, 'fetch', fetch)
    monkeypatch.setattr(voice, '_kokoro_say', lambda text, *a: voice.to_wav([0.] * 2400, 24000))
    monkeypatch.setitem(voice.SAY, 'kokoro', voice._kokoro_say)
    cl = mk(['settings'])
    t = cl.post('/settings/voice', data=dict(engine='kokoro', voice='bm_george')).text
    assert voice.out_current()[:3] == ('kokoro', voice.KOKORO, 'bm_george') and '>George (UK man)<' in t and '>Heart (US woman)<' in t
    assert 'The voice is not on this Mac yet' in t and '107 MB' in t
    assert 'Downloading The voice (Kokoro)' in cl.post('/settings/voice/get', data=dict(engine='kokoro')).text
    go.set()
    for _ in range(100):
        if 'is ready and in use' in (j := cl.get('/settings/jobs').text): break
        time.sleep(.02)
    assert got == [voice.KOKORO] and 'The voice (Kokoro) is ready and in use' in j
    assert cl.post('/settings/voice/sample').json()['where'] == 'on this Mac'

def test_an_old_kokoro_setting_gets_kokoro_when_it_is_installed(mk, monkeypatch):
    "A setting from before 0.0.16 said kokoro, with an mlx model and a Kokoro voice: with the extra it is Kokoro with that voice, else Pocket TTS."
    update_settings('voice', out='kokoro', out_model='mlx-community/Kokoro-82M-bf16', out_voice='af_bella')
    monkeypatch.setattr(voice, 'kokoro_installed', lambda: True)
    assert voice.out_current()[:3] == ('kokoro', voice.KOKORO, 'af_bella')
    monkeypatch.setattr(voice, 'kokoro_installed', lambda: False)
    assert voice.out_current()[:3] == ('pocket', voice.POCKET, 'caro_davy')
