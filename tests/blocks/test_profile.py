"What abhyasa knows about you: the page, edits, the first conversation, undo, clear, and the line on Today."

def test_meet_on_today_until_known(mk, lr):
    cl = mk()
    assert 'Tell abhyasa about you' in cl.get('/').text
    lr.set_profile(background='codes in Python')
    t = cl.get('/').text
    assert 'Tell abhyasa about you' not in t and 'What abhyasa knows about you' in t

def test_edit_and_undo(mk, lr):
    cl = mk()
    assert 'data-mic' in cl.get('/you').text
    r = cl.post('/you', data=dict(background='codes in Python\nknows Sanskrit grammar', examples=['code', 'maths'], pace='gentle', session_len='8')).text
    assert 'Saved' in r
    p = lr.profile()
    assert p.background == ['codes in Python', 'knows Sanskrit grammar'] and p.examples == ['code', 'maths'] and p.pace == 'gentle' and p.session_len == 8
    page = cl.get('/you').text
    assert 'What changed, and why' in page and 'codes in Python' in page and 'Undo' in page
    cid = [c for c in lr.profile().changes if c['field'] == 'pace'][0]['id']   # by id: two changes of one save can have the same time
    cl.post('/you/undo', data=dict(id=cid))
    assert lr.profile().pace == 'steady' and lr.profile().session_len == 8

def test_onboarding(mk, lr, fake):
    cl = mk()
    page = cl.get('/you/start').text
    assert page.count('data-mic') == 4 and 'What do you want to learn' in page
    fake.rules['make a short learner profile'] = dict(background=['writes Python'], goals=['read LLM papers'], examples=['code'], pace='steady', session_len=10, notes='')
    r = cl.post('/you/start', data=dict(who='I write Python', want='LLMs'), follow_redirects=False)
    assert r.headers['location'] == '/you?new=1'
    assert lr.profile().goals == ['read LLM papers'] and 'Your first conversation' in cl.get('/you?new=1').text

def test_observe_now_and_clear(mk, lr, fake):
    cl = mk()
    assert 'No change' in cl.post('/you/observe').text          # no answers yet: no evidence
    lr.record('ranking', 'Why ranks?', answer='scores', correct=False, confidence=80, depth=3, misconception='scores compare', final=True)
    fake.rules['You keep a short profile'] = dict(changes=[dict(field='confuses', add='ranks against scores', why='You missed it.')])
    assert 'ranks against scores' in cl.post('/you/observe').text
    cl.post('/you/clear')
    assert not lr.profile().known

def test_profile_in_the_question(mk, lr, fake):
    lr.set_profile(background='codes in Python')
    cl = mk()
    sid = cl.post('/start', follow_redirects=False).headers['location'].split('/')[-1]
    cl.get(f'/s/{sid}')
    assert any('codes in Python' in p for p, _ in fake.calls)

def test_voice_everywhere(mk):
    cl = mk()
    page = cl.get('/you').text
    assert 'id="mic-float"' in page and 'data-mic' in page          # the voice block adds its floating mic to each page
    assert 'mic-float' not in mk(names=['today']).get('/').text   # without the voice block nothing breaks

def test_calibration(mk, lr):
    cl = mk(); lr.set_profile(background=['codes in Python'])   # an empty profile with no answers shows no calibration
    assert 'How well you know what you know' in cl.get('/you').text and 'After five answers' in cl.get('/you').text
    for i, (ok, conf) in enumerate([(False, 90), (False, 90), (True, 90), (False, 70), (True, 30)]):
        lr.record('ranking', f'q{i}', correct=ok, confidence=conf, depth=3, session='s', final=True)
    t = cl.get('/you').text
    assert 'you were right in 1 of 4' in t and 'how could this be wrong?' in t
