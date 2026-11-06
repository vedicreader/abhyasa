"The model chips: the model of a task on the page where it works, with the list of Settings. A pick saves the setting of Settings."
from talk_data import *
import pytest
from fastcore.basics import AttrDict
from abhyasa import models as llm
import abhyasa.blocks.build.app as build_app

CAT = [dict(value='claude/opus', name='Claude Opus', provider='claude'), dict(value='claude/haiku', name='Claude Haiku', provider='claude')]

@pytest.fixture(autouse=True)
def clean(monkeypatch):
    "No saved task models, no override, and a list of two models."
    monkeypatch.delenv('ABHYASA_MODEL', raising=False)
    monkeypatch.setattr(llm, 'catalog', lambda ttl=300.: CAT)
    llm.update_settings('models', **{t: '' for t in ('default', *llm.ALL_TASKS)})
    yield
    llm.update_settings('models', **{t: '' for t in ('default', *llm.ALL_TASKS)})

def test_chip_shows_and_saves_the_settings_value(mk):
    "The chip names the model in use and where it runs. A pick saves `models.<task>`, so the Settings row shows the same model; Use the default clears it."
    cl = mk(['settings'])
    t = cl.get('/settings/chip?task=talk').text
    assert '<select' in t and 'value="claude/opus"' in t and 'Type another model id' in t and 'All models in Settings' in t and 'Use the default' not in t
    t = cl.post('/settings/chip', data=dict(task='talk', model='claude/opus')).text
    assert 'id="mchip-talk"' in t and 'Claude Opus' in t and 'hosted' in t and llm.settings()['models']['talk'] == 'claude/opus'
    assert cl.app.state.svc['ask'].uses('talk') == 'claude/opus'
    assert 'value="claude/opus" selected' in cl.get('/settings/catalog').text   # the Settings row agrees
    assert 'Use the default' in cl.get('/settings/chip?task=talk').text
    cl.post('/settings/chip', data=dict(task='talk', model=''))
    assert llm.settings()['models']['talk'] == ''

def test_chip_types_another_id_and_refuses_an_unknown_task(mk):
    "Type another model id opens a box and saves nothing. An unknown task is refused."
    cl = mk(['settings'])
    t = cl.post('/settings/chip', data=dict(task='hint', model='__other__')).text
    assert 'type="text"' in t and 'open' in t and llm.settings()['models'].get('hint', '') == ''
    assert cl.post('/settings/chip', data=dict(task='nope', model='x')).status_code == 400
    assert cl.get('/settings/chip?task=default').status_code == 400   # the default model is set on the Settings page only

def test_chip_says_when_the_override_sets_the_model(mk, monkeypatch):
    "With $ABHYASA_MODEL set, a task with no model of its own shows the override and why. A task with its own model does not."
    monkeypatch.setenv('ABHYASA_MODEL', 'claude/haiku')
    cl = mk(['settings'])
    t = cl.get('/settings/chip?task=build').text
    assert '$ABHYASA_MODEL sets the default model now' in t
    t = cl.post('/settings/chip', data=dict(task='build', model='claude/opus')).text
    assert 'Claude Opus' in t and 'mchip-lock' not in t

def test_chips_on_the_pages(mk, lr, talk_fake):
    "The walk step has the chips of questions and hints, the talk editor the chip of talk questions, and each page the chips of the guide in its box."
    cl = mk()
    jid = talk_walk(lr)
    step = cl.get(f'/w/{jid}/1').text
    assert 'id="mchip-question"' in step and 'id="mchip-hint"' in step and 'id="mchip-guide"' in step and 'id="mchip-guide_vision"' in step
    talk = cl.get(f'/t/{make_talk(cl, jid)}').text
    assert 'id="mchip-talk"' in talk

class ModelAgent:
    "A fake ramabana agent that keeps the model of each `set_model`."
    def __init__(self): self.tools, self.models = {}, []
    def add_tool(self, f): self.tools[f.__name__] = f
    def ask(self, p, result=True, stop=None, **kw): return AttrDict(reply='Done.', state='complete')
    def set_model(self, name, job='turn'): self.models.append(name)
    def close(self): pass

def test_builder_turn_uses_the_build_model(mk, lr, monkeypatch):
    "The builder pane has the chip of the builder chat. The agent starts on the build model; after a pick, the next turn moves it to the new model."
    a, made = ModelAgent(), []
    monkeypatch.setattr(build_app, 'ramabana_lead', lambda roots, names, **kw: (made.append(kw.get('turn')), (a, AttrDict(scratch='')))[1])
    llm.update_settings('models', build='claude/haiku')
    cl = mk()
    bid = cl.get('/build', follow_redirects=False).headers['location'].split('/')[2].split('?')[0]
    assert 'id="mchip-build"' in cl.get(f'/build/{bid}?pane=1').text
    def turn(text):
        n = sum(e['type'] in ('RUN_FINISHED', 'RUN_ERROR') for e in lr.build(bid).events)
        cl.post(f'/build/{bid}/say', data=dict(text=text))
        wait_for(lambda: True if sum(e['type'] in ('RUN_FINISHED', 'RUN_ERROR') for e in lr.build(bid).events) > n else None, secs=20)
    turn('Hello')
    assert made == ['claude/haiku'] and a.models == []
    cl.post('/settings/chip', data=dict(task='build', model='claude/opus'))
    turn('Again')
    assert made == ['claude/haiku'] and a.models == ['claude/opus']

def test_the_builder_runs_on_claude_opus_until_you_pick(mk, monkeypatch):
    "The builder chat is an agent: with no model of its own it runs on Claude Opus, the model of a ramabana chat, and its chip and its Settings row say so."
    monkeypatch.delenv('ABHYASA_MODEL', raising=False)
    cl = mk(['settings'])
    assert cl.app.state.svc['ask'].uses('build') == 'claude-opus-5-5'
    assert 'Claude Opus' in cl.get('/settings/chip?task=build').text
    from abhyasa.blocks.settings.ui import fallback
    assert fallback('build', cl.app.state.svc['ask']).startswith('Default: Claude Opus')   # the empty choice of its Settings row
    cl.post('/settings/chip', data=dict(task='build', model='claude/haiku'))
    assert cl.app.state.svc['ask'].uses('build') == 'claude/haiku'   # a pick still wins
