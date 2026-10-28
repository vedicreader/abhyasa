"The Settings page: pick and get speech models, cut at pauses, the OpenAI key. No test uses the network or the real cache."
import os, time
from pathlib import Path
import pytest
from abhyasa import voice

@pytest.fixture(autouse=True)
def clean():
    voice.save_settings(voice.settings() | dict(stt=dict(engine='gemma', model='', segment=True), downloaded=[], prompts={}))
    voice.set_openai_key('')
    yield
    voice.set_openai_key('')

def test_page(mk):
    t = mk().get('/settings').text
    assert '>Settings<' in t and 'Gemma 4 E4B (LiteRT)' in t and 'In use' in t
    assert 'sends your audio off this machine' in t and 'There is no key' in t
    assert '>Models<' in t and 'Look up models' in t

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

def test_key_with_a_newline_is_refused(mk):
    cl = mk()
    t = cl.post('/settings/key', data=dict(key='sk-abc12345\nOTHER=1')).text
    assert 'only letters, digits' in t and 'There is no key' in t
    assert not (voice.cfg_dir()/'keys.env').exists() or 'OTHER' not in (voice.cfg_dir()/'keys.env').read_text()

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
    assert '>Models<' in cl.get('/settings').text
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

def test_tutor_model_test_uses_the_task_route(mk):
    "With a default that routes by task, as `RouteAsk` does, the Test button asks on its own job `test:<task>`, with the chosen model and the reply cap of the task. The job of the task does not change."
    seen = []
    class Routed:
        model = 'claude/sonnet'
        def __call__(self, p, sp=''): return ''
        def via(self, task, name='', max_tokens=None):
            seen.append((task, name, max_tokens))
            return lambda p, sp='': 'ready'
    cl = mk(['settings'])
    cl.app.state.svc['ask'].dflt = Routed()
    assert ' s: “ready”' in cl.post('/settings/model/test', data=dict(task='hint', model='claude/haiku')).text
    assert ' s: “ready”' in cl.post('/settings/model/test', data=dict(task='grade', model='')).text
    assert seen == [('test:hint', 'claude/haiku', llm.TOKENS['hint']), ('test:grade', '', llm.TOKENS['grade'])]

def test_reply_cap_saved_loaded_and_checked(mk, monkeypatch):
    "The reply cap of a task is a row of the table: saved in settings.json, shown under More in Models, and a value out of range is clamped."
    from abhyasa.llm import TOKENS, TOKENS_MAX
    monkeypatch.setattr(llm, 'catalog', lambda ttl=300.: [])
    cl = mk(['settings'])
    t = cl.get('/settings/catalog').text
    assert 'Reply cap: hints' in t and f'1 to {TOKENS_MAX:,} tokens · default {TOKENS["hint"]} tokens' in t
    r = cl.post('/settings/value', data=dict(name='tokens.hint', value='300'))
    assert r.status_code == 200 and 'Saved' in r.text and voice.settings()['tokens']['hint'] == 300
    assert cl.app.state.svc['ask'].cap('hint') == 300
    assert 'value="1"' in cl.post('/settings/value', data=dict(name='tokens.hint', value='0')).text and voice.settings()['tokens']['hint'] == 1
    assert 'Type a number' in cl.post('/settings/value', data=dict(name='tokens.hint', value='lots')).text
    cl.post('/settings/default', data=dict(name='tokens.hint'))
    assert cl.app.state.svc['ask'].cap('hint') == TOKENS['hint']

def test_catalog_gives_a_list_with_plain_names(mk, monkeypatch):
    "The list shows names that people know, grouped by provider. The value of each item is the model id."
    monkeypatch.setattr(llm, 'catalog', lambda ttl=300.: [dict(value='codex/gpt-6-astra', name='GPT-6 Astra', label='gpt-6-astra', provider='codex', source='login'),
                                                         dict(value='claude/sonnet', name='Claude Sonnet', label='sonnet', provider='claude', source='cli')])
    t = mk(['settings']).get('/settings/catalog').text
    assert t.count('<select') == len(llm.ALL_TASKS) + 1 and '<optgroup label="Codex">' in t and '<optgroup label="Claude">' in t
    assert '<option value="codex/gpt-6-astra" title="codex/gpt-6-astra">GPT-6 Astra</option>' in t
    assert 'Default: Claude Sonnet' in t and 'Type another model id' in t

def test_a_saved_id_that_is_not_in_the_list_stays(mk, monkeypatch):
    "A saved id that the list does not have shows as the selected item, so old settings keep working."
    monkeypatch.setattr(llm, 'catalog', lambda ttl=300.: [])
    voice.update_settings('models', grade='openai/gpt-5.4-mini')
    t = mk(['settings']).get('/settings/catalog').text
    assert '<optgroup label="Saved"><option value="openai/gpt-5.4-mini" selected title="openai/gpt-5.4-mini">GPT-5.4 Mini</option>' in t
    voice.update_settings('models', grade='')

def test_type_another_model_id(mk, monkeypatch):
    "The last item shows a text box and saves nothing. The typed id is saved and shows in the list."
    monkeypatch.setattr(llm, 'catalog', lambda ttl=300.: [])
    cl = mk(['settings'])
    t = cl.post('/settings/model', data=dict(task='hint', model='__other__')).text
    assert 'type="text"' in t and 'Back to the list' in t and voice.settings()['models'].get('hint', '') == ''
    t = cl.post('/settings/model', data=dict(task='hint', model=' my/model ')).text
    assert '<select' in t and 'value="my/model" selected' in t and voice.settings()['models']['hint'] == 'my/model'
    voice.update_settings('models', hint='')

def test_theme_on_html(mk):
    "Each page has the theme and the mode from the settings on <html>; the Settings page has the Theme section."
    voice.update_settings('look', theme='paper', mode='auto')
    cl = mk()
    t = cl.get('/settings').text
    assert '<html data-theme="paper" data-mode="auto">' in t and '>Look<' in t and 'value="sage"' in t
    assert '/assets/themes.css' in t

def test_theme_switch(mk):
    "The look route saves the theme and the mode; the next page has them. An unknown name changes nothing."
    cl = mk(['settings', 'today'])
    assert cl.post('/settings/look', data=dict(theme='ink', mode='dark')).status_code == 204
    assert voice.settings()['look'] == dict(theme='ink', mode='dark')
    assert 'data-theme="ink" data-mode="dark"' in cl.get('/').text
    assert cl.post('/settings/look', data=dict(theme='neon', mode='dark')).status_code == 400
    assert voice.settings()['look']['theme'] == 'ink'
    voice.update_settings('look', theme='paper', mode='auto')

def _lum(h, s, l):
    import colorsys
    rgb = colorsys.hls_to_rgb(h / 360, l / 100, s / 100)
    return sum(w * (c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4) for w, c in zip((.2126, .7152, .0722), rgb))

def contrast(a, b):
    la, lb = sorted((_lum(*a), _lum(*b)), reverse=True)
    return (la + .05) / (lb + .05)

def palettes():
    "From themes.css: theme -> {var: (light hsl, dark hsl)}."
    import re
    from abhyasa.core import THEMES
    css = (Path(voice.__file__).parent/'core'/'themes.css').read_text()
    hsl = r'hsl\((\d+) (\d+)% (\d+)%\)'
    out = {}
    for t in THEMES:
        body = re.search(r'\[data-theme=' + t + r'\] \{(.*?)\}', css, re.S)[1]
        out[t] = {k: (tuple(map(int, a)), tuple(map(int, b))) for k, *ab in re.findall(rf'--(\w+):\s*light-dark\({hsl},\s*{hsl}\)', body)
                  for a, b in [(ab[:3], ab[3:])]}
    return out

def test_theme_contrast():
    "Each text colour of each theme has a contrast of 4.5:1 or more on its bg, in light and in dark. acc is also the bg of the main button."
    low = []
    for t, p in palettes().items():
        assert set(p) >= {'bg', 'fg', 'ink2', 'mute', 'line', 'acc', 'ok', 'no', 'bad'}, t
        for i, mode in enumerate(('light', 'dark')):
            for k in ('fg', 'ink2', 'mute', 'acc', 'ok', 'no', 'bad'):
                if (c := contrast(p[k][i], p['bg'][i])) < 4.5: low.append((t, mode, k, round(c, 2)))
    assert not low, low


# prompts: the instruction text of the tutor, saved in the settings, used on the next call
from abhyasa.prompts import PROMPTS, prompt
from abhyasa.tutor import TUTOR_SP, HINTS, hints

def test_prompts_section(mk):
    "The page has one item for each prompt: its label, its note, and a box with the text in use."
    t = mk(['settings']).get('/settings').text
    assert '>Prompts<' in t and t.count('name="text"') == len(PROMPTS)
    for p in PROMPTS.values(): assert p.label in t and p.note.split("'")[0] in t
    assert 'Use the default' in t and 'You never think for them.' in t   # the default text of the tutor rules

def test_walk_prompts_in_settings(mk):
    "The path planner and the pick of the main ideas are on the Settings page of the app."
    t = mk().get('/settings').text
    for n in ('walk.plan', 'walk.pick', 'walk.note'): assert PROMPTS[n].label in t

def test_prompt_save_and_use_the_default(mk):
    "Save keeps the text and the tutor uses it. 'Use the default' and an empty save both clear it."
    cl = mk(['settings'])
    r = cl.post('/settings/prompt', data=dict(name='tutor', text='Be brief.'))
    assert r.status_code == 200 and 'Saved.' in r.text and 'Be brief.' in r.text and 'Your text' in r.text
    assert prompt('tutor') == 'Be brief.' and 'Be brief.' in cl.get('/settings').text
    r = cl.post('/settings/prompt/default', data=dict(name='tutor'))
    assert prompt('tutor') == TUTOR_SP and 'The default is in use.' in r.text
    cl.post('/settings/prompt', data=dict(name='tutor', text='Be brief.'))
    assert 'The default is in use.' in cl.post('/settings/prompt', data=dict(name='tutor', text=' \n ')).text
    assert prompt('tutor') == TUTOR_SP and voice.settings()['prompts'] == {}
    assert cl.post('/settings/prompt', data=dict(name='nope', text='x')).status_code == 400
    assert cl.post('/settings/prompt/default', data=dict(name='nope')).status_code == 400

def test_bad_hint_ladder_is_refused(mk):
    "A hint ladder without 6 lines is refused with a plain message. The box keeps what you typed, and the ladder does not change."
    t = mk(['settings']).post('/settings/prompt', data=dict(name='hints', text='One.\nTwo.')).text
    assert 'needs 6 lines' in t and 'role="alert"' in t and 'One.\nTwo.' in t
    assert hints() == HINTS and voice.settings()['prompts'] == {}
