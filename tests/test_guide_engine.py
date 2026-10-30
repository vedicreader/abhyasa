"The engine of the screen guide: the board language, the context, the gate, the guard and the explainer video."
import json
from abhyasa.guide import by_id, check_line, parse_board, norm_tex, OPS

DDPM = r'q(\mathbf{x}_t\mid\mathbf{x}_0)=\mathcal{N}(\mathbf{x}_t;\sqrt{\bar\alpha_t}\mathbf{x}_0,(1-\bar\alpha_t)\mathbf{I})'

def ctx(**kw):
    return by_id(dict(anchors=[dict(id='passage', kind='passage', text='It admits sampling in closed form.'),
                               dict(id='m1', kind='formula', text=DDPM, tokens=[r'\bar\alpha_t', r'\sqrt{\bar\alpha_t}']),
                               dict(id='figure', kind='figure', text='A right triangle', labels=dict(a=[100, 420, 160, 500], b=[480, 880, 540, 960]))],
                      demo=dict(inputs=dict(t=dict(value=500, min=0, max=1000)), open=False), **kw))

def test_the_list_is_closed():
    "The 11 ops of the owner's list, and nothing that runs code."
    assert set(OPS) == {'step', 'circle', 'box', 'underline', 'arrow', 'label', 'sketch', 'point', 'clear', 'demo_set', 'video_at'}
    for bad in [dict(op='eval', js='1'), dict(op='label', at='passage', text='x', css='color:red'), dict(op='label', at='passage', text='<svg onload=x>')]:
        assert check_line(bad, ctx())

def test_a_made_up_anchor_drops_and_the_rest_draws():
    lines = ['{"op":"step","say":"Look at side a."}', '{"op":"point","at":{"a":"figure","label":"a"}}',
             '{"op":"circle","at":{"a":"figure","label":"c"}}', '{"op":"circle","at":{"a":"m1","tex":"\\\\bar{\\\\alpha}_t"}}']
    b = parse_board('\n'.join(lines), ctx())
    assert [s['op'] for s in b.steps[0]['strokes']] == ['point', 'circle'] and len(b.dropped) == 1 and not b.failed

def test_demo_set_waits_for_the_gate():
    "Before the lock-in the board cannot move the demo, so it cannot show the result first."
    o = dict(op='demo_set', set=dict(t=900))
    shut, open_ = ctx(), by_id({**ctx(), 'demo': dict(inputs=dict(t=dict(min=0, max=1000)), open=True)})
    assert 'gate' in check_line(o, shut) and check_line(o, open_) == ''

def test_tex_match_ignores_braces():
    assert norm_tex(r'\sqrt{ \bar{\alpha}_{t} }') == norm_tex(r'\sqrt{\bar\alpha_t}')

# --- the context and the figure labels -------------------------------------------------------------------------------
from abhyasa.guide import clean_context, figure_labels, FigureCache

def test_clean_context_keeps_known_keys_and_cuts():
    raw = dict(page='/walk/x/step/1', evil='<script>', anchors=[dict(id='passage', kind='passage', text='w ' * 400, onclick='x'),
                                                                 dict(id='bad id!', kind='passage', text='x'), dict(id='m1', kind='nope', text='y')])
    c = clean_context(raw)
    assert 'evil' not in c and [a['id'] for a in c.anchors] == ['passage', 'm1'] and 'onclick' not in c.anchors[0]
    assert len(c.anchors[0]['text']) <= 300 and c.anchors[1]['kind'] == 'text' and set(c.by) == {'passage', 'm1'}

def test_clean_context_cuts_all_text_to_6000():
    c = clean_context(dict(anchors=[dict(id=f'a{i}', kind='text', text='x' * 300) for i in range(40)]))
    assert sum(len(a['text']) for a in c.anchors) <= 6000

def test_figure_labels_from_a_vision_reply():
    calls = []
    def vision(p, img, sp=''): calls.append(img); return json.dumps(dict(labels=[dict(text='a', box=[90, 400, 160, 500]), dict(text='b', box=[480, 880, 540, 960]),
                                                                                  dict(text='c', box=[0, 0, 2000, 10]), dict(text='', box=[1, 1, 2, 2])]))
    assert figure_labels(vision, b'\x89PNG', 'A right triangle') == {'a': [90, 400, 160, 500], 'b': [480, 880, 540, 960]}
    assert calls == [b'\x89PNG']
    assert figure_labels(lambda p, img, sp='': 'not json', b'x') is None   # a failed reply: None, so no one keeps it

def test_figure_cache_keeps_boxes_only(tmp_path):
    fc = FigureCache(tmp_path/'figs.json')
    k = fc.key(b'\x89PNG data')
    assert fc.get(k) is None
    fc.put(k, {'a': [1, 2, 3, 4]})
    assert FigureCache(tmp_path/'figs.json').get(k) == {'a': [1, 2, 3, 4]}
    assert b'PNG' not in (tmp_path/'figs.json').read_bytes()

# --- the gate and the guard -------------------------------------------------------------------------------------------
from abhyasa.guide import explain, guard, Withheld
from abhyasa.llm import Fake
from abhyasa.ground import passage
from fastcore.basics import AttrDict

SECRET = 'sk-test1234567890abcdefXYZ'
PAGE = 'A notable property of the forward process is that it admits sampling x_t at an arbitrary timestep t in closed form.'

def page_ctx(text=PAGE):
    return dict(page='/walk/ddpm/step/2', step='Noise in one jump', source='your source · Ho et al. 2020',
                anchors=[dict(id='passage', kind='passage', text=text), dict(id='m1', kind='formula', text=DDPM, tokens=[r'\bar\alpha_t'])])

def board(sure, need='none', **step):
    return '\n'.join(json.dumps(o) for o in [dict(op='v', n=1, sure=sure, need=need), dict(op='step', say='Alpha bar t is the share of the picture that is left.', **step),
                                             dict(op='circle', at=dict(a='m1', tex=r'\bar\alpha_t'))])

class Vault:
    name = 'vault'
    def __init__(self, ps=()): self.ps, self.qs = list(ps), []
    def search(self, q, k=4): self.qs.append(q); return self.ps

def test_sure_answers_at_once():
    f = Fake({'I don\'t get': board(0.9)})
    r = explain(f, page_ctx(), "I don't get alpha bar")
    assert r.tier == 'tutor' and len(f.calls) == 1 and r.steps[0]['strokes'][0]['op'] == 'circle'
    assert r.end == "In the tutor's own words. No source found." and r.ms >= 0

def test_unsure_goes_to_the_vault():
    note = 'Alpha bar t is the product of the alphas up to step t, so it falls from one toward zero as t grows.'
    v = Vault([passage('vault:notes', 'n1', 'My DDPM notes', note, url='/doc/n1')])
    f = Fake({'Tier: vault': board(0.8, src=2, quote=note.split(', so')[0]), 'Tier: tutor': board(0.3, 'vault')})
    r = explain(f, page_ctx(), "I don't get alpha bar", sources=[v])
    assert r.tier == 'vault' and r.steps[0]['quote']['src'] == 2 and len(f.calls) == 2
    assert r.sources[1]['title'] == 'My DDPM notes' and r.sources[1]['label'] == 'your vault'

def test_still_unsure_goes_to_the_web():
    url, text = 'https://example.org/ddpm', 'Home. The cumulative product alpha bar t tells how much of the original signal remains after t noising steps.'
    pick = dict(passage='The cumulative product alpha bar t tells how much of the original signal remains after t noising steps.')
    f = Fake({'Tier: web': board(0.8, src=2, quote=pick['passage']), 'Tier: tutor': board(0.3, 'web'), 'Return JSON: {"passage"': pick})
    qs = []
    r = explain(f, page_ctx(), "I don't get alpha bar", sources=[Vault()], search=lambda q, n: qs.append(q) or [dict(title='DDPM', href=url)],
                fetch=lambda u: AttrDict(url=u, title='DDPM explained', text=text), web=True)
    assert r.tier == 'web' and r.sources[1]['url'] == url and r.steps[0]['quote']['text'].startswith('The cumulative') and qs

def test_no_web_keeps_the_tutor_words():
    f = Fake({'Tier: tutor': board(0.3, 'web')})
    r = explain(f, page_ctx(), "I don't get alpha bar", sources=[Vault()], web=False)
    assert r.tier == 'tutor' and r.end == "In the tutor's own words. No source found."

def test_a_secret_never_leaves():
    "A key in the page text reaches no model call and no web query."
    f = Fake({'Tier: tutor': board(0.2, 'web'), 'Return JSON: {"passage"': dict(passage='')})
    qs, v = [], Vault()
    explain(f, page_ctx(f'{PAGE} My key is {SECRET}.'), f"I don't get alpha bar {SECRET}", sources=[v],
            search=lambda q, n: qs.append(q) or [dict(title='x', href='https://example.org/x')], fetch=lambda u: AttrDict(url=u, title='x', text='nothing here'), web=True)
    sent = json.dumps([f.calls, qs, v.qs])
    assert f.calls and not qs and SECRET not in sent and '[SECRET]' in sent   # a web query with a key does not go

def test_guard_masks_and_refuses(monkeypatch):
    assert SECRET not in guard(f'key {SECRET}')
    import ramabana.guard
    monkeypatch.setattr(ramabana.guard, 'setting', lambda k, d=None: 'refuse' if k == 'cli.pii' else d)
    import pytest
    with pytest.raises(Withheld): guard('Mail me at ada.lovelace@example.com please.')

def test_a_secret_in_a_figure_caption_never_reaches_the_vision_call():
    seen = []
    figure_labels(lambda p, img, sp='': seen.append(p) or '{"labels": []}', b'\x89PNG', f'A triangle. Key {SECRET}')
    assert seen and SECRET not in seen[0] and '[SECRET]' in seen[0]

def test_a_raw_context_with_by_is_cleaned(monkeypatch):
    "A host sends the page context as the browser gave it, with a `by` key: explain still cleans it, so a long anchor is cut and an unknown key goes."
    import abhyasa.guide as G
    seen, real = [], G.board_prompt
    monkeypatch.setattr(G, 'board_prompt', lambda ctx, *a, **kw: seen.append(ctx) or real(ctx, *a, **kw))
    raw = dict(page_ctx('q' * 1000), evil='EVIL', by={'passage': dict(id='passage', text='q' * 1000)})
    f = Fake({'I don\'t get': board(0.9)})
    explain(f, raw, "I don't get alpha bar")
    ctx = seen[0]
    assert 'evil' not in ctx and len(ctx.by['passage']['text']) == 300 and ctx.anchors[0]['text'] == 'q' * 300
    assert 'q' * 301 not in json.dumps(f.calls) and 'EVIL' not in json.dumps(f.calls)

def test_the_routed_guide_guards_for_the_model_of_its_route(monkeypatch):
    "With `cli.pii` redact, a guide or vision model on this Mac gets the mail address, and a hosted one gets `[EMAIL]`. A key is masked for both."
    import ramabana.guard
    from ramabana.core import ModelSpec
    from ramabana.testing import fake_agent, FakeBackend
    from abhyasa import llm
    from abhyasa.guide import guide_ask, vision_ask
    monkeypatch.setattr(ramabana.guard, 'setting', lambda k, d=None: 'redact' if k == 'cli.pii' else d)
    a, _ = fake_agent()
    monkeypatch.setitem(llm._ra, 'agent', a)
    r = llm.Router(llm.RouteAsk('claude/sonnet'), models=lambda: {}, tokens=lambda: {})
    for spec, mail in ((ModelSpec('mlx/gemma', 'mlx', 'gemma', ctx=4096), 'ada@example.com'), (ModelSpec('cloud', 'remote', 'cloud', ctx=4096), '[EMAIL]')):
        be = FakeBackend(spec)
        monkeypatch.setattr(a, '_be_or_none', lambda job='turn', be=be: be)
        assert guide_ask(r)(f'mail ada@example.com key {SECRET}') == f'ONESHOT:mail {mail} key [SECRET]'
        assert f'alt {mail} [SECRET]' in vision_ask(r)(f'alt ada@example.com {SECRET}', b'\x89PNG', 'sp')

def test_a_remote_route_that_drops_the_picture_is_text_only(monkeypatch):
    "rishi's remote one-shot that builds its message from dict parts only drops the image of `compose`: `vision_ask` then makes no call, and `vision_why` says why."
    from rishi.remote import RemoteChat, to_msg
    from urai import mk_msg
    from abhyasa import llm
    from abhyasa.guide import vision_ask, vision_why
    r = llm.Router(llm.RouteAsk('claude/sonnet'), models=lambda: {}, tokens=lambda: {})
    monkeypatch.setattr(RemoteChat, '_oneshot_args', lambda self, p, sp, n: ([to_msg({'role': 'user', 'content': p})], {}))
    assert vision_why(r, 'codex/gpt-6.1-sol') == 'GPT-6.1 Sol does not get pictures on this route.' and vision_ask(r, 'codex/gpt-6.1-sol') is None
    monkeypatch.setattr(RemoteChat, '_oneshot_args', lambda self, p, sp, n: ([to_msg(mk_msg(p))], {}))
    assert vision_why(r, 'codex/gpt-6.1-sol') == '' and callable(vision_ask(r, 'codex/gpt-6.1-sol'))
