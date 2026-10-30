"The natural voice on the server: `/guide/say` gives the audio of one line with the time of each word, keeps the lines of the run, and guards a line for OpenAI."
import base64, io, wave, pytest
import abhyasa.voice as V
from abhyasa.settings import update_settings, reset

class FakeKokoro:
    "A Kokoro with no download: its pipeline gives 0.25 s of silence for each word, with a token that starts 0.05 s into it."
    sample_rate = 24000
    def __init__(self): self.said = []
    def _get_pipeline(self, lang):
        def run(text, voice, speed, split_pattern):
            self.said.append(text)
            for w in text.split(): yield dict2(audio=[0.] * 6000, tokens=[dict2(text=w, start_ts=.05)])
        return run

class dict2(dict): __getattr__ = dict.get

@pytest.fixture
def voice_out(monkeypatch):
    "The setting voice.out, with a fake loader for the mlx models. The settings go back to the browser voice after the test."
    loads = []
    monkeypatch.setattr(V, '_tts_load', lambda m: loads.append(m) or FakeKokoro())
    monkeypatch.setattr(V, 'spacy_ready', lambda: None)
    monkeypatch.setattr(V, 'cached', lambda m: m != 'mlx-community/not-here')
    def use(engine, **kw): update_settings('voice', out=engine, **kw)
    use.loads = loads
    yield use
    for k in ('voice.out', 'voice.out_model', 'voice.out_voice', 'voice.out_speed'): reset(k)
    V.unload('tts')

def secs(b64) -> float:
    with wave.open(io.BytesIO(base64.b64decode(b64))) as w: return w.getnframes() / w.getframerate()

def test_the_browser_voice_has_no_audio_here(mk):
    r = mk(['guide']).post('/guide/say', json=dict(text='Hello.'))
    assert r.status_code == 409 and 'browser' in r.json()['error']

def test_a_line_comes_with_its_word_times_and_then_from_the_cache(mk, voice_out):
    "Kokoro gives a WAV and a time for each word that goes up. The same line again comes from the cache: the model says it one time."
    voice_out('kokoro')
    cl = mk(['guide'])
    d = cl.post('/guide/say', json=dict(text='Noise goes in   slowly.')).json()
    assert (d['engine'], d['model'], d['voice'], d['where'], d['cached']) == ('kokoro', V.DFLT_KOKORO, 'af_heart', 'on this Mac', False)
    assert secs(d['audio']) == 1. and d['words'] == [.05, .3, .55, .8]
    assert cl.post('/guide/say', json=dict(text='Noise goes in slowly.')).json()['cached'] is True
    assert cl.post('/guide/say', json=dict(text='Noise goes in slowly.', speed=1.5)).json()['cached'] is False   # a new speed is a new line
    assert voice_out.loads == [V.DFLT_KOKORO]

def test_bad_requests(mk, voice_out):
    voice_out('kokoro')
    cl = mk(['guide'])
    assert cl.post('/guide/say', json=dict(text='  ')).status_code == 400
    assert cl.post('/guide/say', content=b'not json').status_code == 400

def test_a_model_that_is_not_here_is_not_downloaded_for_a_line(mk, voice_out):
    voice_out('hf', out_model='mlx-community/not-here')
    r = mk(['guide']).post('/guide/say', json=dict(text='Hello.'))
    assert r.status_code == 400 and 'not on this Mac' in r.json()['error'] and voice_out.loads == []

def test_warm_loads_the_voice(mk, voice_out):
    "The guide warms, and the voice of the settings loads on the voice worker, with no line from the page."
    voice_out('kokoro')
    cl = mk(['guide'])
    assert cl.post('/guide/warm').status_code == 204
    cl.app.state.svc['speaker'].ex.submit(lambda: None).result(5)   # the warm call ran before this one
    assert voice_out.loads == [V.DFLT_KOKORO]

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
    voice_out('kokoro')
    t = mk().get('/').text
    info = json.loads(html.unescape(re.search(r"data-info='([^']*)'", t).group(1)))
    assert info['out'] == dict(engine='kokoro', model='Kokoro', voice='af_heart', where='on this Mac', who='') and info['say'] == '/guide/say'
