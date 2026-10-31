"The Settings page: pick and get speech models, cut at pauses, the OpenAI key. No test uses the network or the real cache."
import os, time
from pathlib import Path
import pytest
from abhyasa import voice
from abhyasa.settings import set_val

@pytest.fixture(autouse=True)
def clean():
    voice.save_settings(voice.settings() | dict(stt=dict(engine='gemma', model='', segment=True), downloaded=[], prompts={}))
    voice.set_openai_key('')
    yield
    voice.set_openai_key('')

def test_page(mk):
    t = mk().get('/settings').text
    assert '>Settings<' in t and 'Gemma 4 E4B (LiteRT)' in t and 'In use' in t
    assert 'sends your audio off this Mac' in t and 'There is no key' in t
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
    "Cut at pauses is a row of the settings table; the mic gets its value."
    cl = mk(['voice', 'settings'])
    set_val('stt.segment', False)
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

def test_no_test_reads_the_real_ramabana_config():
    setup = pytest.importorskip('ramabana.setup')
    assert setup.config_path() != Path(setup.CONFIG).expanduser() and not setup.config_path().exists()

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

class ViaFake(llm.Fake):
    "A `Fake` that routes as `RouteAsk` does: `via(job, name)` gives an ask that names its model and keeps its job."
    model, jobs = 'claude/sonnet', []
    def via(self, job, name='', cap=None, prepare=None):
        def ask(p, sp=''): self.jobs.append((job, ask.model)); return self(p, sp)
        ask.model = name or self.model
        return ask

def test_the_guide_rows_show_and_save(mk, monkeypatch):
    "Models has a Screen guide row and a Figure labels row. Each uses the model for hints until you pick one, and saves its own model."
    monkeypatch.setattr(llm, 'catalog', lambda ttl=300.: [dict(value='claude/opus', name='Claude Opus', provider='claude')])
    voice.update_settings('models', hint='claude/haiku')
    cl = mk(['settings'])
    t = cl.get('/settings/catalog').text
    assert '>Screen guide<' in t and '>Figure labels<' in t and t.count('Same as hints: Claude Haiku') >= 3   # walk notes, the guide and figure labels
    t = cl.post('/settings/model', data=dict(task='guide', model='claude/opus')).text
    assert 'value="claude/opus" selected' in t and voice.settings()['models']['guide'] == 'claude/opus'
    assert cl.app.state.svc['ask'].name('guide') == 'claude/opus' and cl.app.state.svc['ask'].name('guide_vision') == 'claude/haiku'
    voice.update_settings('models', hint='', guide='')

def test_a_saved_guide_model_routes_the_guide_job(lr):
    "guide_ask goes to the job guide, on the saved model of the screen guide; the warm route starts the same model."
    from abhyasa.guide import guide_ask
    r = llm.Router(ViaFake(dflt='ok'), models=lambda: dict(hint='claude/haiku', guide='claude/opus'))
    ask = guide_ask(r)
    assert ask.model == 'claude/opus' and ask('hi') == 'ok' and r.dflt.jobs[-1] == ('guide', 'claude/opus')
    warmed = []
    r.dflt.warm = lambda names: warmed.append(names)
    r.warm(['guide']).join()
    assert warmed == [dict(guide='claude/opus')]

def test_the_guide_events_name_the_saved_model(lr):
    "The first state event of the guide names the model that Settings saved for the screen guide, and where it runs."
    import json
    from starlette.testclient import TestClient
    from abhyasa.app import mk_app
    voice.update_settings('models', guide='claude/opus')
    f = ViaFake({'Tier: tutor': '\n'.join(json.dumps(o) for o in [dict(op='v', n=1, sure=0.9), dict(op='step', say='One.'), dict(op='box', at='passage')])})
    cl = TestClient(mk_app(lr, f, names=['guide'], hosts=('testserver',)))
    evs = [json.loads(l[6:]) for l in cl.post('/guide/ask', json=dict(said='what', ctx=dict(anchors=[dict(id='passage', kind='passage', text='x')]))).text.splitlines()
           if l.startswith('data: ')]
    assert evs[0]['model'] == 'Claude Opus' and evs[0]['where'] == 'hosted' and evs[0]['who'] == 'Anthropic'
    voice.update_settings('models', guide='')

def test_where_names_a_local_and_a_hosted_model(mk, monkeypatch):
    "Each model row says where its text goes: on this Mac for a local model, hosted and the company for the others. No network."
    monkeypatch.setattr(llm, 'catalog', lambda ttl=300.: [])
    monkeypatch.setattr(llm, '_on_mac', lambda value, provider='': value.startswith('mlx/'))
    voice.update_settings('models', hint='mlx/gemma-4-e4b-it', grade='claude/haiku')
    t = mk(['settings']).get('/settings/catalog').text
    assert '<span class="where" title="Where the text goes for this task.">on this Mac</span>' in t
    assert '<span class="where hosted" title="Where the text goes for this task.">hosted · Anthropic</span>' in t
    assert llm.where_chip('mlx/gemma-4-e4b-it') == 'on this Mac' and llm.where_chip('openai/gpt-6-sol') == 'hosted · OpenAI'
    voice.update_settings('models', hint='', grade='')

def test_a_model_from_two_providers_shows_once(mk, monkeypatch):
    "Claude Haiku 5.5 through Claude Code and through Copilot is one item: the Claude Code route, with the other route in its title."
    import re
    monkeypatch.setattr(llm, 'catalog', lambda ttl=300.: [
        dict(value='claude/claude-haiku-5-5', name='Claude Haiku 5.5', provider='claude'), dict(value='copilot/claude-haiku-5.5', name='Claude Haiku 5.5', provider='copilot'),
        dict(value='copilot/gpt-6.1-sol', name='GPT-6.1 Sol', provider='copilot'), dict(value='openai/gpt-6.1-sol', name='GPT-6.1 Sol', provider='openai'),
        dict(value='codex/gpt-6.1-sol', name='GPT-6.1 Sol', provider='codex')])
    t = mk(['settings']).get('/settings/catalog').text
    sel = re.search(r'<select[^>]*models-hint[^>]*>(.*?)</select>', t, re.S) or re.search(r'aria-label="The model for hints"[^>]*>(.*?)</select>', t, re.S)
    vals = re.findall(r'<option value="([^"]+)"', sel.group(1))
    names = re.findall(r'>([^<]+)</option>', sel.group(1))
    assert len(vals) == len(set(vals)) and len(names) == len(set(names))
    assert 'claude/claude-haiku-5-5' in vals and 'copilot/claude-haiku-5.5' not in vals and 'codex/gpt-6.1-sol' in vals
    assert 'title="codex/gpt-6.1-sol (also: copilot/gpt-6.1-sol, openai/gpt-6.1-sol)"' in sel.group(1)

def test_theme_switch(mk):
    "The look route saves the theme and the mode; the next page has them. An unknown name changes nothing."
    cl = mk(['settings', 'today'])
    assert cl.post('/settings/look', data=dict(theme='ink', mode='dark')).status_code == 204
    assert voice.settings()['look'] == dict(theme='ink', mode='dark', keys_float=True)
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
    "The look is the feature: text must be readable, so each text colour of each theme has a contrast of 4.5:1 or more on its bg, in light and in dark. acc is also the bg of the main button."
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

def test_prompt_list_does_not_need_the_blocks():
    "The prompt list loads each module that registers a prompt, so it does not depend on which blocks loaded."
    from abhyasa.blocks.settings.ui import registry
    assert {'primer', 'walk.note', 'profile.onboard'} <= set(registry())

def test_the_point_look_row_shows_each_look_and_saves(mk):
    "The Screen guide group has the Point mark row: one pill for each look, each with its own small picture. A pick saves it."
    from abhyasa.settings import val, set_val
    cl = mk(['settings'])
    t = cl.get('/settings').text
    row = t[t.index('id="sr-guide-point"'):]; row = row[:row.index('</li>')]
    assert row.count('<svg') == 3 and all(f'value="{k}"' in row for k in ('tick', 'dot', 'ring')) and 'value="tick" checked' in row
    assert 'http' not in row.replace('http://www.w3.org/2000/svg', '')   # the pictures are inline: no file from the web
    assert 'Saved' in cl.post('/settings/value', data=dict(name='guide.point', value='ring')).text and val('guide.point') == 'ring'
    set_val('guide.point', 'tick')

def test_the_figure_labels_test_sends_a_known_picture(mk, fake):
    "Test on the Figure labels row sends the test picture and says whether the model read its two labels."
    from pathlib import Path
    import abhyasa.blocks.settings as S
    img, seen = (Path(S.__file__).parent/'figure-test.png').read_bytes(), []
    assert img.startswith(b'\x89PNG')
    fake.rules['You find the text labels'] = lambda p, sp: seen.append(p) or dict(labels=[dict(text='Encoder', box=[50, 290, 420, 710]), dict(text='Decoder', box=[580, 290, 950, 710])])
    cl = mk(['settings'])
    t = cl.post('/settings/model/test', data=dict(task='guide_vision')).text
    assert 'passed. It read Encoder and Decoder.' in t and 'class="ok"' in t and seen
    fake.rules['You find the text labels'] = dict(labels=[])
    t = cl.post('/settings/model/test', data=dict(task='guide_vision')).text
    assert 'failed. It did not read Encoder and Decoder.' in t and 'class="no"' in t
