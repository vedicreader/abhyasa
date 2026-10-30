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
    assert figure_labels(lambda p, img, sp='': 'not json', b'x') == {}

def test_figure_cache_keeps_boxes_only(tmp_path):
    fc = FigureCache(tmp_path/'figs.json')
    k = fc.key(b'\x89PNG data')
    assert fc.get(k) is None
    fc.put(k, {'a': [1, 2, 3, 4]})
    assert FigureCache(tmp_path/'figs.json').get(k) == {'a': [1, 2, 3, 4]}
    assert b'PNG' not in (tmp_path/'figs.json').read_bytes()
