"The natural voice on the server: `/guide/say` gives the audio of one line with the time of each word, keeps the lines of the run, and guards a line for OpenAI."
import base64, io, wave, pytest
import numpy as np
import abhyasa.voice as V
from abhyasa.settings import update_settings, reset

class FakePocket:
    "A Pocket TTS with no download: 0.25 s of silence for each word."
    sample_rate = 24000
    def __init__(self): self.said = []
    def get_state_for_audio_prompt(self, v): return dict(voice=v)
    def generate_audio(self, st, text, normalize=False):
        self.said.append((st['voice'], text))
        return np.zeros(6000 * len(text.split()), np.float32)

@pytest.fixture
def voice_out(monkeypatch):
    "The setting voice.out, with a fake loader for Pocket TTS. `here` says if the model is on this Mac. The settings go back to the default after the test."
    loads = []
    monkeypatch.setattr(V, '_pocket_load', lambda: loads.append(1) or (FakePocket(), {}))
    monkeypatch.setattr(V, 'cached', lambda m: use.here)
    def use(engine, **kw): update_settings('voice', out=engine, **kw)
    use.loads, use.here = loads, True
    yield use
    for k in ('voice.out', 'voice.out_model', 'voice.out_voice', 'voice.out_speed'): reset(k)
    V.unload('tts')

def secs(b64) -> float:
    with wave.open(io.BytesIO(base64.b64decode(b64))) as w: return w.getnframes() / w.getframerate()

def test_the_browser_voice_has_no_audio_here(mk, voice_out):
    voice_out('browser')
    r = mk(['guide']).post('/guide/say', json=dict(text='Hello.'))
    assert r.status_code == 409 and 'browser' in r.json()['error']

def test_a_line_comes_with_its_word_times_and_then_from_the_cache(mk, voice_out):
    "Pocket TTS gives a WAV and a time for each word that goes up. The same line again comes from the cache: the model says it one time."
    voice_out('pocket')
    cl = mk(['guide'])
    d = cl.post('/guide/say', json=dict(text='Noise goes in   slowly.')).json()
    assert (d['engine'], d['model'], d['voice'], d['where'], d['cached']) == ('pocket', V.POCKET, 'caro_davy', 'on this Mac', False)
    assert secs(d['audio']) == 1. and d['words'] == V.by_letters('Noise goes in slowly.', 1.) and d['words'] == sorted(d['words'])
    assert cl.post('/guide/say', json=dict(text='Noise goes in slowly.')).json()['cached'] is True
    assert cl.post('/guide/say', json=dict(text='Noise goes in slowly.', voice='mary')).json()['cached'] is False   # a new voice is a new line
    assert voice_out.loads == [1]

def test_bad_requests(mk, voice_out):
    voice_out('pocket')
    cl = mk(['guide'])
    assert cl.post('/guide/say', json=dict(text='  ')).status_code == 400
    assert cl.post('/guide/say', content=b'not json').status_code == 400

def test_before_the_download_the_browser_speaks(mk, voice_out):
    "Pocket TTS that is not on this Mac is not downloaded for a line. The route says 409 with 'browser', as for the browser voice, so the page and the Mac app speak with their own voice."
    voice_out('pocket'); voice_out.here = False
    cl = mk()
    r = cl.post('/guide/say', json=dict(text='Hello.'))
    assert r.status_code == 409 and 'browser' in r.json()['error'] and voice_out.loads == []
    import json, re, html
    info = json.loads(html.unescape(re.search(r"data-info='([^']*)'", cl.get('/').text).group(1)))
    assert info['out']['engine'] == 'browser'

def test_an_old_kokoro_setting_speaks_with_pocket(mk, voice_out):
    "A settings file from before 0.0.16 with Kokoro and a Kokoro voice gets Pocket TTS and caro_davy. Nothing writes the file."
    voice_out('kokoro', out_model='mlx-community/Kokoro-82M-bf16', out_voice='bm_george')
    d = mk(['guide']).post('/guide/say', json=dict(text='Hello there.')).json()
    assert (d['engine'], d['voice']) == ('pocket', 'caro_davy') and V.settings()['voice']['out'] == 'kokoro'

def test_warm_loads_the_voice(mk, voice_out):
    "The guide warms, and the voice of the settings loads on the voice worker, with no line from the page."
    voice_out('pocket')
    cl = mk(['guide'])
    assert cl.post('/guide/warm').status_code == 204
    cl.app.state.svc['speaker'].ex.submit(lambda: None).result(5)   # the warm call ran before this one
    assert voice_out.loads == [1]

def test_openai_gets_the_guarded_line(mk, voice_out, monkeypatch):
    "A line for OpenAI passes the guard: a secret in it never leaves this Mac. With no key, the route says so."
    voice_out('openai')
    cl = mk(['guide'])
    r = cl.post('/guide/say', json=dict(text='Hello.'))
    assert r.status_code == 502
    V.set_openai_key('sk-test-1234')
    sent = []
    class W:
        content = V.to_wav([0.] * 12000, 24000)
        def raise_for_status(self): pass
    monkeypatch.setattr(V, 'http_post', lambda url, **kw: sent.append(kw) or W())
    try:
        secret = 'sk-test1234567890abcdefXYZ'
        d = cl.post('/guide/say', json=dict(text=f'The key is {secret} here.')).json()
        assert (d['where'], d['who'], secs(d['audio']), len(d['words'])) == ('hosted', 'OpenAI', .5, 5)
        assert secret not in sent[0]['json']['input'] and '[SECRET]' in sent[0]['json']['input']
        assert (sent[0]['json']['model'], sent[0]['json']['voice'], sent[0]['json']['response_format']) == (V.DFLT_SPEECH, 'marin', 'wav')
    finally: V.set_openai_key('')

def test_the_page_knows_the_voice(mk, voice_out):
    "The guide script on each page names the voice, where it runs, and the route."
    import json, re, html
    voice_out('pocket')
    t = mk().get('/').text
    info = json.loads(html.unescape(re.search(r"data-info='([^']*)'", t).group(1)))
    assert info['out'] == dict(engine='pocket', model='Pocket TTS', voice='caro_davy', where='on this Mac', who='') and info['say'] == '/guide/say'
