"The natural voice on the server: `/guide/say` gives the audio of one line with the time of each word, keeps the lines of the run, and guards a line for OpenAI."
import base64, io, wave, pytest
import numpy as np
import abhyasa.models as V
from abhyasa.learner import update_settings, reset

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
    assert round(secs(d['audio']), 3) == 1. + V.PAD.lead + V.PAD.tail   # the words, and the gap around them
    assert d['words'] == [round(V.PAD.lead + t, 3) for t in V.by_letters('Noise goes in slowly.', 1.)] and d['words'] == sorted(d['words'])
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
    class W: status_code, content = 200, V.to_wav([0.] * 12000, 24000)
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

class Bad:
    "A fake OpenAI reply that failed: a status and the JSON `error` body of OpenAI."
    def __init__(self, status, message, code=None): self.status_code, self.body = status, dict(error=dict(message=message, code=code))
    def json(self): return self.body

@pytest.mark.parametrize('reply,said', [
    (Bad(400, "Invalid voice 'verse' for this model.", None), 'OpenAI: the voice Verse does not work with gpt-4o-mini-tts. Pick another voice or the model gpt-4o-mini-tts.'),
    (Bad(401, 'Incorrect API key provided: sk-te****1234.', 'invalid_api_key'), 'OpenAI: the key does not work. Set a new key on the Settings page, under More in Speech to text.'),
    (Bad(429, 'You exceeded your current quota.', 'insufficient_quota'), 'OpenAI: your account has no credit. Add credit at platform.openai.com, or pick another voice.'),
    (Bad(429, 'Rate limit reached for requests.', 'rate_limit_exceeded'), 'OpenAI: too many requests. Wait one minute, then try again.')])
def test_a_failed_openai_call_says_why_in_one_plain_line(mk, voice_out, monkeypatch, reply, said):
    "OpenAI fails: `/guide/say` and Play a sample give one plain line from OpenAI's error, with no raw HTTP text and no link."
    voice_out('openai', out_voice='verse')
    V.set_openai_key('sk-test-1234')
    monkeypatch.setattr(V, 'http_post', lambda url, **kw: reply)
    try:
        cl = mk(['guide', 'settings'])
        r = cl.post('/guide/say', json=dict(text='Hello.'))
        assert r.status_code == 502 and r.json()['error'] == said
        s = cl.post('/settings/voice/sample').json()['error']
        assert s == said and 'Client error' not in s and 'mozilla' not in s
    finally: V.set_openai_key('')

def test_the_settings_page_shows_why_the_voice_failed(mk, voice_out, monkeypatch):
    "A line fails for the guide: Settings shows the reason under the choice. A sample that plays takes it away."
    voice_out('openai'); V.set_openai_key('sk-test-1234')
    monkeypatch.setattr(V, 'http_post', lambda url, **kw: Bad(401, 'Incorrect API key provided.', 'invalid_api_key'))
    try:
        cl = mk(['guide', 'settings'])
        assert cl.post('/guide/say', json=dict(text='Hello.')).status_code == 502
        t = cl.get('/settings').text
        assert 'The voice failed on the last line. OpenAI: the key does not work.' in t and 'class="out-error warn"' in t
        class W: status_code, content = 200, V.to_wav([0.] * 2400, 24000)
        monkeypatch.setattr(V, 'http_post', lambda url, **kw: W())
        assert cl.post('/settings/voice/sample').json()['audio']
        assert 'out-error' not in cl.get('/settings').text
    finally: V.set_openai_key('')

def test_a_local_line_ends_with_a_silent_gap(mk, voice_out):
    "Pocket TTS: the WAV ends with PAD.tail seconds of silence after a fade, and starts after PAD.lead. The board's timeout uses the WAV length, so it counts the gap."
    voice_out('pocket')
    d = mk(['guide']).post('/guide/say', json=dict(text='Two words.')).json()
    with wave.open(io.BytesIO(base64.b64decode(d['audio']))) as w: r, s = w.getframerate(), np.frombuffer(w.readframes(w.getnframes()), '<i2')
    assert len(s) / r == pytest.approx(.5 + V.PAD.lead + V.PAD.tail, abs=1e-3) and not s[-int(r * V.PAD.tail):].any() and not s[:int(r * V.PAD.lead)].any()
    assert d['words'][0] == V.PAD.lead and d['words'][-1] < .5 + V.PAD.lead   # the words fall on the sound, not on the gap

def test_the_voice_says_maths_as_words_and_times_the_parts_of_the_line(mk, voice_out):
    "Pocket TTS gets the maths in words. The times are for the parts of the line as the board shows them: `$y_m$` is one part."
    voice_out('pocket')
    cl = mk(['guide'])
    d = cl.post('/guide/say', json=dict(text='So $y_m$ and $ym$ stay, with rhythm.')).json()
    pk = V._slots['tts'][0].obj[0]
    assert pk.said[-1] == ('caro_davy', 'So y sub m and y m stay, with rhythm.')
    assert len(d['words']) == 7 and d['words'] == sorted(d['words'])
    assert cl.post('/guide/spoken', json=dict(text=r'Then $\alpha^2$ and $\frac{a}{b}$.')).json() == dict(say='Then alpha squared and a over b.', at=[0, 1, 1, 2, 3, 3, 3])
