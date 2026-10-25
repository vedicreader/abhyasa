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

def test_feedback_cites_sources_after_close(mk):
    cl = mk()
    sid = start(cl)
    assert 'My ranking notes' not in cl.get(f'/s/{sid}').text          # hidden while you work
    r = cl.post(f'/s/{sid}/answer', data=dict(answer='its rank position', confidence=80)).text
    assert 'From your sources' in r and 'My ranking notes' in r

def test_chat_keeps_each_turn_in_order(mk):
    cl = mk()
    sid = start(cl)
    cl.get(f'/s/{sid}')
    r1 = cl.post(f'/s/{sid}/answer', data=dict(answer='add the scores', thinking='they are numbers', confidence=70)).text
    assert 'add the scores' in r1 and 'Not yet' in r1 and 'First error' in r1
    assert 'id="left"' in r1 and 'Two more tries' in r1 and 'Teach me' in r1    # the composer learns the tries left, by oob swaps
    h1 = cl.post(f'/s/{sid}/hint').text
    cl.post(f'/s/{sid}/answer', data=dict(answer='scale them first', confidence=50))
    h2 = cl.post(f'/s/{sid}/hint').text
    assert 'Hint 1' in h1 and 'Hint 2' in h2
    r3 = cl.post(f'/s/{sid}/answer', data=dict(answer='the rank position', confidence=90)).text
    assert 'Right, but shaky' in r3 and 'id="composer"' in r3 and 'hx-swap-oob' in r3   # the composer now holds Next
    page = cl.get(f'/s/{sid}').text                    # a reload keeps the closed thread, then the next question
    order = ['add the scores', 'Not yet', 'Hint 1', 'scale them first', 'Hint 2', 'the rank position', 'Right, but shaky']
    at = [page.index(x) for x in order]
    assert at == sorted(at), dict(zip(order, at))
    assert page.count('class="m you"') == 3 and page.count('class="m tutor fb no"') == 2
    assert page.count('class="qa"') == 2               # the next question follows in the same scroll

def test_follow_up_only_and_composer_empties(mk, fake):
    cl = mk()
    sid = start(cl)
    cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/answer', data=dict(answer='add the scores', confidence=70))
    cl.post(f'/s/{sid}/answer', data=dict(answer='then sort them', confidence=70))
    p = [c[0] for c in fake.calls if 'You grade' in c[1]][-1]
    assert p.index('Learner: add the scores') < p.index("Learner's answer: then sort them")   # the thread, then only the follow-up
    page = cl.get(f'/s/{sid}').text
    composer = page[page.index('id="composer"'):]
    assert 'then sort them' not in composer           # the message is in the chat, not in the box

def test_next_twice_does_not_repeat(mk):
    cl = mk()
    sid = start(cl)
    cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/answer', data=dict(answer='the rank position', confidence=90))
    assert 'class="qa"' in cl.post(f'/s/{sid}/next').text
    assert cl.post(f'/s/{sid}/next').status_code == 204
    assert cl.post(f'/s/{sid}/hint').status_code in (200, 204)

def test_viewer_shows_the_conversation_of_an_attempt(mk, lr):
    import json
    cl = mk()
    sid = start(cl)
    cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/answer', data=dict(answer='add the scores', confidence=70))
    cl.post(f'/s/{sid}/answer', data=dict(answer='the rank position', confidence=70))
    final = next(r for r in lr._docs('attempt') if json.loads(r['meta']).get('final'))
    t = cl.get(f"/v/learning/{final['id']}").text
    assert 'The conversation' in t and t.index('add the scores') < t.index('the rank position')
