"Show me, anywhere: a demo from your words on a walk step and in a session, with no try used, a record of each ask, and the 3D and Leela links."
import re
from walk_data import walk, leela_file
from rupaka.spec import validate, gallery
from abhyasa.demo import ask_key

def svc(cl): return cl.app.state.svc

def wait_asks(cl, slug):
    "Wait for each demo job of an ask on `slug`; their keys."
    ks = [k for k in svc(cl)['tutor'].jobs if k.startswith(f'{slug}#')]
    for k in ks: svc(cl)['tutor'].jobs[k].result(timeout=60)
    return ks

def aid_of(html): return re.search(r'data-ask="([0-9a-f]{12})"', html)[1]

def walk_at(cl, lr, i=1):
    "A started walk with a short check open on step `i`; the walk id, the slug of the step and the open question."
    jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, i, check=dict(way='words', kind='short', depth=2, why=''))
    cl.get(f'/w/{jid}/{i}/check')
    j = lr.journey(jid)
    return jid, j.steps[i]['slug'], svc(cl)['tutor'].open[j.steps[i]['qid']]

def test_show_me_on_a_walk_step_makes_a_demo_from_the_open_check(mk, walk_fake, lr):
    cl = mk(); jid, slug, q = walk_at(cl, lr)
    page, card = cl.get(f'/w/{jid}/1').text, cl.get(f'/w/{jid}/1/check').text
    assert 'id="show-demo"' not in page and 'id="show-slot"' in page   # one Show me: in the row of the open check, after Hint and Explain
    assert card.count('id="show-demo"') == 1 and '⌥E' in card and card.index('id="hint"') < card.index('data-guide-open') < card.index('id="show-demo"') < card.index('id="idk"')
    r = cl.post('/demo/ask', data=dict(where='walk', concept=slug, walk=jid, step='1')).text
    assert 'A 2D demo' in r and 'predict first' in r
    wait_asks(cl, slug)
    a = lr.asked(aid_of(r))
    assert (a.where, a.walk, a.step, a.said) == ('walk', jid, 1, '') and q.question in a.ask   # made from the open check
    d = lr.demo_for(slug, aim='', key=a.key)
    assert d and list(validate(d.spec)) == [] and d.asked['key'] == ask_key(a.ask)
    card = cl.get(f'/demo/asked/{a.id}').text
    assert 'data-rupaka' in card and f'data-ask="{a.id}"' in card

def test_show_me_in_a_session_is_a_tutor_message(mk, lr):
    cl = mk()
    sid = cl.post('/start', data=dict(focus='ranking'), follow_redirects=False).headers['location'].split('/')[-1]
    page = cl.get(f'/s/{sid}').text
    qid = re.search(r'data-qid="([^"]+)"', page)[1]
    assert 'id="show-demo"' in page and f'#tl-{qid}' in page
    r = cl.post('/demo/ask', data=dict(where='session', qid=qid)).text
    assert 'class="m tutor extra"' in r and 'A 2D demo' in r
    wait_asks(cl, 'ranking')
    a = lr.asked(aid_of(r))
    assert (a.where, a.session, a.concept) == ('session', sid, 'ranking')
    d = lr.demo_for('ranking', aim='', key=a.key)
    assert d and list(validate(d.spec)) == []
    assert 'data-rupaka' in cl.get(f'/demo/asked/{a.id}').text

def test_two_asks_on_one_concept_get_two_keys_and_two_demos(mk, walk_fake, lr):
    lr.put_demo({**gallery()['reciprocal-rank-fusion'], 'id': 'plain-rrf'}, 'reciprocal-rank-fusion')
    cl = mk()
    r1 = cl.post('/demo/ask', data=dict(where='concept', concept='reciprocal-rank-fusion', said='how k changes the sum')).text
    r2 = cl.post('/demo/ask', data=dict(where='concept', concept='reciprocal-rank-fusion', said='why the top rank wins')).text
    ks = wait_asks(cl, 'reciprocal-rank-fusion')
    assert len(ks) == 2 and len(set(ks)) == 2
    a1, a2 = lr.asked(aid_of(r1)), lr.asked(aid_of(r2))
    d1, d2 = lr.demo_for(a1.concept, aim='', key=a1.key), lr.demo_for(a2.concept, aim='', key=a2.key)
    assert d1.slug != d2.slug and {d1.asked['said'], d2.asked['said']} == {'how k changes the sum', 'why the top rank wins'}
    assert lr.demo_for('reciprocal-rank-fusion', aim='').slug == 'plain-rrf'   # the plain demo of the concept stays as it was

def test_show_me_typed_in_a_walk_answer_box_uses_no_try(mk, walk_fake, lr):
    cl = mk(); jid, slug, q = walk_at(cl, lr)
    n0 = len(lr.attempts(slug))
    r = cl.post(f'/w/{jid}/1/answer', data=dict(answer='show me how the scores become weights', confidence=50)).text
    assert 'hx-swap-oob="innerHTML"' in r and 'id="show-slot"' in r and 'A 2D demo' in r
    assert q.id in svc(cl)['tutor'].open and svc(cl)['tutor'].open[q.id].tries == [] and len(lr.attempts(slug)) == n0   # not graded
    wait_asks(cl, slug)
    a = lr.asks(walk=jid)[0]
    assert (a.said, a.step, a.kind) == ('how the scores become weights', 1, 'demo') and a.slug and a.outcome == ''

def test_show_me_typed_in_a_session_uses_no_try(mk, lr):
    cl = mk()
    sid = cl.post('/start', data=dict(focus='ranking'), follow_redirects=False).headers['location'].split('/')[-1]
    page = cl.get(f'/s/{sid}').text
    qid = re.search(r'data-qid="([^"]+)"', page)[1]
    r = cl.post(f'/s/{sid}/answer', data=dict(answer='Show me how a rank orders the list')).text
    assert 'tutor extra' in r and 'A 2D demo' in r and 'more tries' not in r and 'Nudge' not in r
    assert svc(cl)['tutor'].open[qid].tries == [] and lr.attempts('ranking') == []
    wait_asks(cl, 'ranking')
    assert lr.asks(session=sid)[0].said == 'how a rank orders the list'

def test_a_prediction_on_an_asked_demo_gives_the_ask_its_outcome(mk, walk_fake, lr):
    cl = mk(); jid, slug, q = walk_at(cl, lr)
    r = cl.post('/demo/ask', data=dict(where='walk', concept=slug, walk=jid, step='1', said='how a large score wins')).text
    wait_asks(cl, slug)
    a = lr.asks(walk=jid)[0]
    gate = next(b['id'] for b in lr.demo(a.slug).spec['blocks'] if b.get('type') == 'gate')
    assert cl.post(f'/demo/{a.slug}/predict', data=dict(gate=gate, picked='1', ans='1', ok='true', ask=a.id)).json() == dict(ok=True)
    assert lr.asks(walk=jid)[0].outcome == 'right'
    assert not lr.journey(jid).steps[1].get('done')   # the demo of an ask is not the check of the step

def test_3d_and_leela_links_say_their_state(mk, walk_fake, lr, monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    cl = mk()
    r = cl.post('/demo/ask', data=dict(where='concept', concept='ranking', said='')).text
    assert 'Show it in 3D' in r and '"kind": "3d"' in r and 'Show a 2D demo' not in r   # a 2D demo: 3D is one click away
    assert 'Leela is not running' in r and '/learn?' not in r
    leela_file(tmp_path)
    r = cl.post('/demo/ask', data=dict(where='concept', concept='ranking', said='let me try it in code')).text
    assert 'A notebook in Leela' in r and 'try it in code' in r and '/learn?topic=Ranking' in r and 'Show a 2D demo' in r
    assert not [k for k in svc(cl)['tutor'].jobs if k.startswith('ranking#')]   # Leela: no 2D job until you ask for it
    two = cl.post('/demo/ask', data=dict(where='concept', concept='ranking', said='let me try it in code', kind='demo')).text
    assert 'A 2D demo' in two and len(wait_asks(cl, 'ranking')) == 1
