"The Settings page: pick and get speech models, cut at pauses, the OpenAI key. No test uses the network or the real cache."
import os, time
import pytest
from abhyasa import voice

@pytest.fixture(autouse=True)
def clean():
    voice.save_settings(voice.settings() | dict(stt=dict(engine='gemma', model='', segment=True), downloaded=[]))
    voice.set_openai_key('')
    yield
    voice.set_openai_key('')

def test_page(mk):
    t = mk().get('/settings').text
    assert '>Settings<' in t and 'Gemma 4 E4B (LiteRT)' in t and 'In use' in t
    assert 'sends your audio off this machine' in t and 'There is no key' in t
    assert 'Tutor models' in t and 'Look up models' in t

def test_use_switches_and_warms(mk):
    cl = mk(['voice', 'settings'])
    t = cl.post('/settings/use', data=dict(engine='mlx', model=voice.DFLT_PARAKEET)).text
    assert voice.current() == ('mlx', voice.DFLT_PARAKEET)
    assert 'Parakeet TDT 0.6B v3' in t
    for _ in range(50):
        if 'ready' in cl.get('/settings/status').text: break
        time.sleep(.02)
    assert 'ready' in cl.get('/settings/status').text

def test_segment_toggle(mk):
    cl = mk(['voice', 'settings'])
    cl.post('/settings/segment', data=dict(on=0))
    assert voice.settings()['stt']['segment'] is False
    assert cl.post('/voice/start').json()['segment'] is False

def test_key_masked_and_private(mk):
    cl = mk(['settings'])
    t = cl.post('/settings/key', data=dict(key='sk-secret-value-9876')).text
    assert '…9876' in t and 'sk-secret-value' not in t and 'Remove key' in t
    p = voice.cfg_dir()/'keys.env'
    assert oct(p.stat().st_mode & 0o777) == '0o600'
    assert 'sk-secret-value' not in cl.get('/settings').text
    assert 'There is no key' in cl.post('/settings/key', data=dict(key='')).text

def test_openai_needs_a_key(mk):
    cl = mk(['settings'])
    cl.post('/settings/use', data=dict(engine='openai', model='gpt-4o-transcribe'))
    assert voice.current()[0] == 'gemma'
    voice.set_openai_key('sk-x-1111')
    cl.post('/settings/use', data=dict(engine='openai', model='gpt-4o-transcribe'))
    assert voice.current() == ('openai', 'gpt-4o-transcribe')

def test_openai_engine_with_fake_http(monkeypatch):
    sent = {}
    class R:
        def raise_for_status(self): pass
        def json(self): return dict(text=' pratyakṣa ')
    monkeypatch.setattr(voice, 'http_post', lambda url, **kw: sent.update(url=url, **kw) or R())
    voice.set_openai_key('sk-x-2222')
    assert voice.transcribe(voice.silence(), 'openai', hint='Nyāya') == 'pratyakṣa'
    assert sent['url'] == voice.OPENAI_URL and sent['data']['prompt'] == 'Nyāya' and sent['headers']['Authorization'] == 'Bearer sk-x-2222'

def test_lookup(mk, monkeypatch):
    monkeypatch.setattr(voice, 'search_models', lambda q: [dict(model='mlx-community/whisper-tiny-asr-fp16', downloads=1200, size=80 * 2**20)])
    t = mk(['settings']).get('/settings/search?q=whisper').text
    assert 'whisper-tiny-asr-fp16' in t and '80 MB' in t and '1,200' in t

def test_get_downloads_then_uses(mk, monkeypatch):
    got = []
    m = 'mlx-community/whisper-tiny-asr-fp16'
    monkeypatch.setattr(voice, 'cached', lambda model: model in got)
    monkeypatch.setattr(voice, 'model_size', lambda model: 2**20)
    monkeypatch.setattr(voice, 'fetch', got.append)
    cl = mk(['voice', 'settings'])
    t = cl.post('/settings/get', data=dict(engine='mlx', model=m)).text
    assert 'id="jobs"' in t
    for _ in range(100):
        if 'ready and in use' in (j := cl.get('/settings/jobs').text): break
        time.sleep(.02)
    assert 'ready and in use' in j and 'id="speech"' in j   # the speech section comes too, once
    assert got == [m] and voice.current() == ('mlx', m)

def test_remove_only_own_downloads(mk):
    cl = mk(['settings'])
    cl.post('/settings/remove', data=dict(model=voice.DFLT_PARAKEET))   # not downloaded by abhyasa: nothing happens
    with pytest.raises(ValueError): voice.remove(voice.DFLT_PARAKEET)

def test_own_download_listed_with_remove(mk, monkeypatch):
    removed = []
    m = 'mlx-community/whisper-tiny-asr-fp16'
    voice.save_settings(voice.settings() | dict(downloaded=[m]))
    monkeypatch.setattr(voice, 'remove', removed.append)
    cl = mk(['settings'])
    t = cl.get('/settings').text
    assert 'whisper-tiny-asr-fp16' in t and 'downloaded by this page' in t and 'Remove' in t
    cl.post('/settings/remove', data=dict(model=m))
    assert removed == [m]


# tutor models: a model for each task, saved in the settings, used at once, with a test and a catalogue
import abhyasa.llm as llm

def test_tutor_model_saved_and_routed(mk, fake):
    cl = mk(['settings'])
    assert 'Tutor models' in cl.get('/settings').text
    fast = llm.Fake(dflt='quick'); fast.model = 'fast/model'
    llm._asks['fast/model'] = fast
    r = cl.post('/settings/model', data=dict(task='grade', model='fast/model'))
    assert r.status_code == 200 and 'value="fast/model"' in r.text
    router = cl.app.state.svc['ask']
    assert router.for_('grade') is fast and router.for_('question') is router.dflt
    assert cl.post('/settings/model', data=dict(task='nope', model='x')).status_code == 400

def test_tutor_model_test_reports_time_and_failures(mk):
    cl = mk(['settings'])
    ok = llm.Fake(dflt='ready'); ok.model = 'ok/model'; llm._asks['ok/model'] = ok
    def boom(p, sp=''): raise RuntimeError('model does not exist')
    llm._asks['bad/model'] = boom
    assert ' s: “ready”' in cl.post('/settings/model/test', data=dict(task='grade', model='ok/model')).text
    assert 'Failed: model does not exist' in cl.post('/settings/model/test', data=dict(task='grade', model='bad/model')).text

def test_catalog_lists_models_for_the_pickers(mk, monkeypatch):
    monkeypatch.setattr(llm, 'catalog', lambda ttl=300.: [dict(value='codex/gpt-x', label='gpt-x', provider='codex', source='login')])
    t = mk(['settings']).get('/settings/catalog').text
    assert 'id="models-list"' in t and 'codex/gpt-x' in t
