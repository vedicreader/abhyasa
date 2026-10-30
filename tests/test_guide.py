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
