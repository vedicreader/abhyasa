"Your strengths and weak spots: the page, the drill start, the explore choice, the concept line, and the graph states."

def test_page_shows_weak_and_strong(mk, lr):
    lr.update('ranking', floor=4, seen=5, stability=30., last=__import__('time').time())
    lr.update('reciprocal-rank-fusion', misses=2, misconceptions=['scores add'], seen=2)
    t = mk().get('/you/strengths').text
    assert 'Weak spots' in t and 'a misconception: scores add' in t and 'Practice my weak spots' in t and '/start?drill=1' in t
    assert t.index('Strong') < t.index('Ranking', t.index('Strong'))

def test_drill_starts_on_the_weak_spot(mk, lr):
    lr.update('reciprocal-rank-fusion', misses=2, misconceptions=['scores add'], seen=2)
    cl = mk()
    sid = cl.get('/start?drill=1', follow_redirects=False).headers['location'].split('/')[-1]
    assert 'a weak spot' in cl.get(f'/s/{sid}').text

def test_explore_choice_saves(mk, lr):
    assert 'Saved' in mk().post('/you/strengths/explore', data=dict(explore='often')).text
    assert lr.profile().explore == 'often'

def test_concept_line_and_graph_state(mk, lr):
    lr.update('reciprocal-rank-fusion', misses=2, seen=2)
    cl = mk()
    assert 'How well you know it' in cl.get('/c/reciprocal-rank-fusion').text
    g = cl.get('/graph.json').json()
    st = {n['id']: n['state'] for n in g['nodes']}
    assert st['reciprocal-rank-fusion'] == 'weak' and st['ranking'] == 'unseen'

def test_key_on_every_page(mk):
    assert "abhyasaKeys.KeyG = '#strengths-key'" in mk().get('/').text
