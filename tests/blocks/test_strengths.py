"Your strengths and weak spots: the part on Progress, the drill start, the explore choice, the concept line, and the graph states."

def test_page_shows_weak_and_strong(mk, lr):
    lr.update('ranking', floor=4, seen=5, stability=30., last=__import__('time').time())
    lr.update('reciprocal-rank-fusion', misses=2, misconceptions=['scores add'], seen=2)
    t = mk().get('/you').text
    assert 'Weak spots' in t and 'a misconception: scores add' in t and 'Practice my weak spots' in t and '/start?drill=1' in t
    assert t.index('Strong') < t.index('Ranking', t.index('Strong'))

def test_drill_starts_on_the_weak_spot(mk, lr):
    lr.update('reciprocal-rank-fusion', misses=2, misconceptions=['scores add'], seen=2)
    cl = mk()
    sid = cl.get('/start?drill=1', follow_redirects=False).headers['location'].split('/')[-1]
    assert 'a weak spot' in cl.get(f'/s/{sid}').text

def test_explore_choice_is_on_profile_only(mk, lr):
    "Strengths says how often the tutor tries a new way and links to the one choice on the Profile page."
    cl = mk(); lr.set_profile(by='you', why='test', explore='often'); lr.update('ranking', seen=1)
    t = cl.get('/you').text
    assert '<h3>How often to try a new way</h3>' in t and 'type="radio"' not in t and 'Often' in t and 'href="/you/profile#sr-learning-explore"' in t
    assert 'id="sr-learning-explore"' in cl.get('/you/profile').text
    assert cl.post('/you/strengths/explore', data=dict(explore='never')).status_code == 404 and lr.profile().explore == 'often'

def test_concept_line_and_graph_state(mk, lr):
    lr.update('reciprocal-rank-fusion', misses=2, seen=2)
    cl = mk()
    assert 'How well you know it' in cl.get('/c/reciprocal-rank-fusion').text
    g = cl.get('/graph.json').json()
    st = {n['id']: n['state'] for n in g['nodes']}
    assert st['reciprocal-rank-fusion'] == 'weak' and st['ranking'] == 'unseen'

