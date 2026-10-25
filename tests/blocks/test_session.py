def start(cl, **data):
    r = cl.post('/start', data=data, follow_redirects=False)
    return r.headers['location'].split('/')[-1]

def test_struggle_then_pass(mk):
    cl = mk()
    sid = start(cl)
    page = cl.get(f'/s/{sid}').text
    assert 'What does a rank tell you?' in page and 'Its position' not in page   # the model answer stays hidden
    assert 'Ranking' in page                                                      # rrf waits for its prereq
    assert 'Not yet' in cl.post(f'/s/{sid}/answer', data=dict(answer='a score', confidence=70)).text
    assert 'Think about positions' in cl.post(f'/s/{sid}/hint').text
    r = cl.post(f'/s/{sid}/answer', data=dict(answer='its rank position', confidence=70)).text
    assert 'Right, but shaky' in r
    assert 'What does a rank tell you?' in cl.post(f'/s/{sid}/next').text        # fetched ahead

def test_dont_know_teaches(mk):
    cl = mk()
    sid = start(cl)
    cl.get(f'/s/{sid}')
    r = cl.post(f'/s/{sid}/giveup', data=dict(dont_know=1)).text
    assert 'A gap' in r and 'Check:' in r

def test_focus_and_end(mk, lr):
    cl = mk()
    lr.update('ranking', floor=3)
    sid = start(cl, focus='reciprocal-rank-fusion')
    assert 'Reciprocal rank fusion' in cl.get(f'/s/{sid}').text
    assert 'This session is over' not in cl.get(f'/s/{sid}/end').text
    assert cl.get(f'/s/{sid}', follow_redirects=False).status_code in (302, 303)

def test_today_and_concept_hooks(mk):
    cl = mk()
    today = cl.get('/').text
    assert 'Next: Ranking' in today and 'action="/start"' in today and 'Subjects' in today
    c = cl.get('/c/ranking').text
    assert 'Learn this' in c and 'See in the graph' in c

def test_mic_on_card_from_voice_block(mk):
    cl = mk()
    sid = start(cl)
    assert 'abhyasaMic' in cl.get(f'/s/{sid}').text
    cl2 = mk(names=['concepts', 'session', 'today'])   # without the voice block: no mic, nothing breaks
    sid = start(cl2)
    assert 'abhyasaMic' not in cl2.get(f'/s/{sid}').text
