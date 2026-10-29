"The talk block: make a talk from a walk, change its slides, and find it again."
from talk_data import *
from abhyasa.settings import val
import hashlib, json, pytest
from fastcore.basics import AttrDict
from pathlib import Path

def test_present_this_walk(mk, talk_fake, lr):
    cl = mk(); jid = prep_walk(lr, walk(cl, lr))
    assert 'Present this walk' in cl.get(f'/w/{jid}').text and 'Present this walk' in cl.get(f'/j/{jid}').text
    tid = make_talk(cl, jid); page = cl.get(f'/t/{tid}').text
    assert page.index('Sequential computation') < page.index('Softmax') < page.index('Scaling by the root of dk')
    assert 'About 20 min of a 20 min slot' in page and 'A change here does not change the walk.' in page
    assert 'T goes from 1 to 2' in page and 'Softmax makes weights from scores.' in page   # the editor shows the question and the note

def test_change_the_slides(mk, talk_fake, lr):
    cl = mk(); jid = prep_walk(lr, walk(cl, lr)); before = lr.journey(jid).steps; tid = make_talk(cl, jid)
    cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='up'))
    assert [s['id'] for s in lr.talk(tid).slides] == ['s2', 's1', 's3', 's4', 's5']
    cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='drop'))
    cl.post(f'/t/{tid}/slide', data=dict(sid='s3', act='pause', prompt='Talk to your neighbour: why divide?', secs=120))
    t = lr.talk(tid)
    assert [s['id'] for s in t.slides] == ['s2', 's3', 's6', 's4', 's5'] and t.slides[2]['kind'] == 'pause' and t.slides[2]['mins'] == 2
    cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='edit', notes='Point at the figure.', beats='passage\nlit:softmax function\nfigure'))
    assert lr.talk(tid).slides[0]['beats'] == ['passage', 'lit:softmax function', 'figure'] and lr.talk(tid).slides[0]['notes'] == 'Point at the figure.'
    r = cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='edit', beats='lit:gradients'))
    assert r.status_code == 400 and 'lights text that is not in the passage' in r.text
    assert lr.talk(tid).slides[0]['beats'] == ['passage', 'lit:softmax function', 'figure']
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s99', act='up')).status_code == 404
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='fly')).status_code == 400
    cl.post(f'/t/{tid}/slot', data=dict(minutes=40))
    assert 'of a 40 min slot' in cl.get(f'/t/{tid}').text and lr.journey(jid).steps == before   # the walk does not change

def test_talks_in_learn_and_search(mk, talk_fake, lr):
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr)))
    page = cl.get('/learn').text
    assert 'Your talks' in page and f'href="/t/{tid}"' in page
    assert cl.get('/search?q=Attention').status_code == 200 and cl.get('/t/nope').status_code == 404
    found = cl.get('/search?q=talk Attention').text
    assert f'href="/t/{tid}"' in found and 'A talk · 5 slides' in found   # search finds the talk, with its slide count

# --- more of the edit, the slot and the guards ----------------------------------------------------------------------

def talk_of(mk, lr):
    cl = mk(); return cl, make_talk(cl, prep_walk(lr, walk(cl, lr)))

def test_edit_the_question(mk, talk_fake, lr):
    "A change to the question keeps the rest; a bad answer or a bad order is refused, and nothing is saved."
    cl, tid = talk_of(mk, lr)
    post = lambda **kw: cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', **kw))
    s = lr.talk(tid).slides[0]; mins = s['mins']
    assert s['ask']['kind'] == 'choice' and post(answer='2').status_code == 200
    a = lr.talk(tid).slides[0]['ask']
    assert a['answer'] == 2 and a['q'] == s['ask']['q'] and a['options'] == s['ask']['options']
    assert post(answer='9').status_code == 400 and lr.talk(tid).slides[0]['ask']['answer'] == 2
    assert post(answer='x').text == 'Pick the right option.'
    assert post(kind='none').status_code == 200
    s = lr.talk(tid).slides[0]
    assert s['ask'] is None and s['mins'] == mins - val('talks.ask_min')   # no question: its minute goes
    assert post(kind='words', q='Say what a recurrent model does.').status_code == 200
    assert lr.talk(tid).slides[0]['ask'] == dict(kind='words', q='Say what a recurrent model does.', most=80) and lr.talk(tid).slides[0]['mins'] == mins

def test_an_order_is_mixed(mk, talk_fake, lr):
    "The presenter writes the cards in the right order; the room sees them mixed, and the answer gives the right order back."
    cl, tid = talk_of(mk, lr)
    right = ['Dot products', 'Divide by the root of dk', 'Softmax', 'Weigh the values']
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='edit', kind='order', q='Put the steps in order.', options='\n'.join(right))).status_code == 200
    a = lr.talk(tid).slides[1]['ask']
    assert a['options'] != right and [a['options'][i] for i in a['answer']] == right
    r = cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='edit', kind='order', q='Q?', options='a\nb\nc', answer='0,0,1'))
    assert r.status_code == 400 and 'is not an order of the options' in r.text
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='edit', kind='order', q='Q?', options='a\nb')).status_code == 400

def test_show_parts_and_more_slides(mk, talk_fake, lr):
    "show_figure off takes out the figure beat and on puts it back after the passage; a questions slide takes the next id; a primer goes before."
    cl, tid = talk_of(mk, lr)
    post = lambda **kw: cl.post(f'/t/{tid}/slide', data=kw)
    assert lr.talk(tid).slides[1]['beats'] == ['passage', 'figure']
    post(sid='s2', act='edit', show_figure='off'); assert lr.talk(tid).slides[1]['beats'] == ['passage']
    post(sid='s2', act='edit', show_figure='on'); assert lr.talk(tid).slides[1]['beats'] == ['passage', 'figure']
    r = post(sid='s1', act='edit', show_figure='on')   # the first idea has no figure
    assert r.status_code == 400 and "needs a figure to show" in r.text
    post(sid='s3', act='questions'); assert [s['id'] for s in lr.talk(tid).slides][3] == 's6'
    post(sid='s3', act='primer', slug='softmax')
    t = lr.talk(tid); assert [s['kind'] for s in t.slides][2:4] == ['primer', 'idea'] and t.slides[2]['title'] == 'Softmax'
    assert post(sid='s3', act='primer', slug='nope').status_code == 400
    assert post(sid='s3', act='pause', secs='5').status_code == 400

def test_slot_and_phones(mk, talk_fake, lr):
    "The slot is 5 to 240 minutes; room phones is on or off; each changes only itself."
    cl, tid = talk_of(mk, lr)
    assert cl.post(f'/t/{tid}/slot', data=dict(minutes=4)).status_code == 400 and cl.post(f'/t/{tid}/slot', data=dict(minutes=241)).status_code == 400
    cl.post(f'/t/{tid}/slot', data=dict(phones='on'))
    t = lr.talk(tid); assert t.phones is True and t.minutes == 20
    assert cl.post('/t/nope/slot', data=dict(minutes=30)).status_code == 404

def test_editor_page(mk, talk_fake, lr):
    "html has the class talk; one row for each slide; one main button, Present with ⌥S; room phones; the slide form for E."
    cl, tid = talk_of(mk, lr)
    page = cl.get(f'/t/{tid}').text
    assert 'class="talk"' in page and page.count('class="slide"') == 5 and 'data-sid="s3"' in page
    assert page.count('class="go"') == 1 and 'Present <kbd>⌥S</kbd>' in page and 'Room phones' in page and 'name="phones"' in page
    assert page.count('class="slide-edit"') == 5 and '/assets/talk.js' in page

def test_new_talk_needs_a_walk(mk, talk_fake, lr):
    "No talk from a journey that is not a walk, or a walk that is not there; the job of a walk with no talk says so."
    cl = mk()
    assert 'No such walk.' in cl.post('/talk/new', data=dict(jid='nope')).text
    assert 'No talk is being made' in cl.get('/talk/job?jid=nope').text

def test_a_failed_talk_says_so(mk, talk_fake, lr, monkeypatch):
    cl = mk(); jid = prep_walk(lr, walk(cl, lr))
    def boom(*a, **kw): raise RuntimeError('a library said <b>this</b>')
    monkeypatch.setattr('abhyasa.blocks.talk.app.talk_from_walk', boom)
    cl.post('/talk/new', data=dict(jid=jid))
    def said():
        r = cl.get(f'/talk/job?jid={jid}').text
        return None if 'Making the talk' in r else r
    said = wait_for(said)
    assert 'abhyasa could not make the talk.' in said and 'library' not in said

def test_talk_posts_are_local_only(mk, talk_fake, lr):
    "Each new POST route is behind LocalOnly: a foreign Origin is refused before the route runs."
    cl, tid = talk_of(mk, lr)
    for path, data in (('/talk/new', dict(jid='x')), (f'/t/{tid}/slide', dict(sid='s1', act='drop')), (f'/t/{tid}/slot', dict(minutes=30))):
        assert cl.post(path, data=data, headers={'Origin': 'https://evil.example'}).status_code == 403, path
    assert len(lr.talk(tid).slides) == 5 and lr.talk(tid).minutes == 20

# --- a plain journey as a talk ---------------------------------------------------------------------------------------

def journey_of(lr, n=0):
    "A plain journey on the two ideas of `lr`, the second one added by you, then `n` more ideas; return its id."
    for k in range(n): lr.put(f'Part {k}', f'Part {k} is one idea.', 'ml')
    ss = [dict(slug='ranking', status='todo', why='You rank before you fuse.'), dict(slug='reciprocal-rank-fusion', status='todo', why='you added it'),
          *[dict(slug=f'part-{k}', status='todo', why='') for k in range(n)]]
    return lr.put_journey(dict(id='ranking-basics-ab12', title='Ranking basics', goal='Learn how to rank results', subject='ml', steps=ss)).id

def journey_talk(cl, jid, **kw):
    "Make a talk from plain journey `jid` through the app and wait for the job; return the talk id."
    cl.post('/talk/journey', data=dict(jid=jid, **kw))
    return wait_for(lambda: cl.get(f'/talk/job?jid={jid}').headers.get('hx-redirect')).split('/')[-1]

def test_present_this_journey(mk, talk_fake, lr):
    "A plain journey has Present this walk, from the journey; the talk has its steps in order and opens in the editor; its walk is not your learning."
    cl = mk(); jid = journey_of(lr); n = len(lr.journeys())
    page = cl.get(f'/j/{jid}').text
    assert 'Present this walk' in page and 'hx-post="/talk/journey"' in page and 'hx-post="/talk/new"' not in page and len(lr.journeys()) == n   # the GET only reads
    assert 'Making the talk…' in cl.post('/talk/journey', data=dict(jid=jid)).text
    tid = wait_for(lambda: cl.get(f'/talk/job?jid={jid}').headers.get('hx-redirect')).split('/')[-1]
    t = lr.talk(tid); w = lr.journey(t.src['walk'])
    assert [s.get('concept') for s in t.slides][:2] == ['ranking', 'reciprocal-rank-fusion'] and w.goal == 'Learn how to rank results'
    assert w.parent == {'journey': jid, 'for': 'talk'} and lr.journey(jid).get('mode') is None
    ed = cl.get(f'/t/{tid}').text
    assert 'Made from your walk' in ed and f'href="/path/{jid}"' in ed and 'This talk has the first' not in ed and 'The walk changed' not in ed
    for pg in ('/', '/journeys', '/learning', '/c/ranking'): assert f'/w/{w.id}' not in cl.get(pg).text, pg

def test_a_journey_talk_has_content(mk, talk_fake, lr):
    "Each idea slide of a journey talk has content and notes: a step with no passage gets points, and a step with a passage keeps it."
    cl = mk(); jid = journey_of(lr)
    assert 'points and the speaker notes' in cl.post('/talk/journey', data=dict(jid=jid)).text   # the pending card says what the tutor writes
    tid = wait_for(lambda: cl.get(f'/talk/job?jid={jid}').headers.get('hx-redirect')).split('/')[-1]
    s1, s2 = lr.talk(tid).slides[:2]
    assert s1['show']['passage'] == 'Ranking orders items by score.' and 'body' not in s1['show'] and '**Watch for:**' in s1['notes']
    assert s1['cites'] == [dict(src='vault:notes', ref='n1', title='My ranking notes', url='https://example.org/notes')]   # from your sources
    assert s2['show']['body'] == SLIDE['points'] and s2['beats'][0] == 'body' and '**Ask the room:**' in s2['notes'] and 'cites' not in s2

def test_the_room_sees_the_points(mk, talk_fake, lr):
    "The audience window shows the points of a slide and never its notes or sources; the presenter window shows the notes and the sources."
    cl = mk(); tid = journey_talk(cl, journey_of(lr)); cl.post(f'/t/{tid}/start'); run = lr.run(lr.talk(tid).live)
    a = cl.get(f'/t/{tid}/audience?k={run["key"]}').text
    assert 'class="points"' in a and '<span class="">The idea has one main step.</span>' in a
    assert 'People mix up' not in a and 'Start with the main step' not in a and 'Watch for' not in a and 'My ranking notes' not in a
    p = cl.get(f'/t/{tid}/present').text
    assert 'People mix up the main step and the example.' in p and 'From your sources' in p and 'My ranking notes' in p

def test_edit_the_points(mk, talk_fake, lr):
    "The editor shows the points, one on each line; a change saves them, and no points takes the beat out."
    cl = mk(); tid = journey_talk(cl, journey_of(lr))
    ed = cl.get(f'/t/{tid}').text
    assert 'name="body"' in ed and 'The idea has one main step.' in ed
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='edit', body='One point.\nTwo points.')).status_code == 200
    s = lr.talk(tid).slides[1]; assert s['show']['body'] == ['One point.', 'Two points.'] and s['beats'][0] == 'body'
    cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='edit', body=''))
    s = lr.talk(tid).slides[1]; assert s['show']['body'] == [] and 'body' not in s['beats']
    cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='edit', body='Back again.'))
    assert lr.talk(tid).slides[1]['beats'][0] == 'body'
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='edit', body='\n'.join(['A point.'] * 7))).status_code == 400
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='edit', body='x' * 301)).status_code == 400

def test_fill_the_slides(mk, talk_fake, lr):
    "An old talk with bare slides offers Fill the slides; the GET only reads, and the POST runs the job that fills them."
    from abhyasa.talk import talk_from_walk
    cl = mk(); tid = journey_talk(cl, journey_of(lr)); wid = lr.talk(tid).src['walk']
    old = talk_from_walk(lr, talk_fake, wid, fill=False); before = lr.talk(old.id)
    ed = cl.get(f'/t/{old.id}').text
    assert 'Fill the slides' in ed and '2 slides have no points or no speaker note.' in ed and lr.talk(old.id) == before   # the GET only reads
    assert 'Fill the slides' not in cl.get(f'/t/{tid}').text   # a full talk does not offer it
    assert 'Filling the slides' in cl.post(f'/t/{old.id}/fill').text
    assert wait_for(lambda: cl.get(f'/talk/job?jid={old.id}').headers.get('hx-redirect')) == f'/t/{old.id}'
    s1, s2 = lr.talk(old.id).slides[:2]
    assert '**Watch for:**' in s1['notes'] and s2['show']['body'] == SLIDE['points'] and 'Fill the slides' not in cl.get(f'/t/{old.id}').text
    assert cl.post('/t/nope/fill').status_code == 404
    assert cl.post(f'/t/{old.id}/fill', headers={'Origin': 'https://evil.example'}).status_code == 403

def test_a_journey_talk_again(mk, talk_fake, lr):
    "A journey that you presented before offers its talk and Make it again; a second press gives the same talk, and Make it again a new one."
    cl = mk(); jid = journey_of(lr); tid = journey_talk(cl, jid); n = len(lr.journeys())
    page = cl.get(f'/j/{jid}').text
    assert 'Open the talk' in page and f'href="/t/{tid}"' in page and 'Make it again' in page
    assert journey_talk(cl, jid) == tid and len(lr.journeys()) == n   # no new walk and no new talk
    tid2 = journey_talk(cl, jid, again='1')
    assert tid2 != tid and len(lr.journeys()) == n + 1 and f'href="/t/{tid2}"' in cl.get(f'/j/{jid}').text
    assert lr.talk(tid2).title.startswith('Ranking basics · ') and lr.talk(tid).title == 'Ranking basics'   # the old talk stays

def test_a_journey_talk_out_of_date(mk, talk_fake, lr):
    "When the journey changes after the talk was made, the editor says so."
    cl = mk(); jid = journey_of(lr); tid = journey_talk(cl, jid)
    line = 'The walk changed after this talk was made. Make it again to update it.'
    assert line not in cl.get(f'/t/{tid}').text
    lr.journey_step(jid, 'ranking', 'down')
    assert line in cl.get(f'/t/{tid}').text

def test_a_long_journey_talk_says_so(mk, talk_fake, lr):
    "A journey with more steps than a walk has gives a talk of the first steps, and the editor says so."
    cl = mk(); jid = journey_of(lr, n=12); tid = journey_talk(cl, jid)
    assert sum(s['kind'] == 'idea' for s in lr.talk(tid).slides) == val('walks.steps') == 12
    ed = cl.get(f'/t/{tid}').text
    assert 'This talk has the first steps of the walk, up to the Ideas in a walk setting (12 by default).' in ed and 'Skipped steps are left out.' in ed

def test_journey_talk_guards(mk, talk_fake, lr):
    "No talk from a journey that is not there or from a walk; the POST is local-only; a walk has no Present this journey."
    cl = mk(); jid = journey_of(lr); n = len(lr.journeys())
    assert cl.post('/talk/journey', data=dict(jid=jid), headers={'Origin': 'https://evil.example'}).status_code == 403
    assert len(lr.journeys()) == n and not lr.talks()
    assert 'No such walk.' in cl.post('/talk/journey', data=dict(jid='nope')).text
    wid = walk(cl, lr)
    assert 'No such walk.' in cl.post('/talk/journey', data=dict(jid=wid)).text and 'hx-post="/talk/journey"' not in cl.get(f'/j/{wid}').text.split('Your other walks')[0]

def test_editor_keys_in_a_browser(mk, talk_fake, lr, tmp_path):
    "In Chromium: W and S move the focus, ⇧S moves the slide, Q adds a pause, X twice takes a slide out, E opens the form, and a bad beat shows its problem as text."
    pw = pytest.importorskip('playwright.sync_api')
    import threading, time, uvicorn
    cl, tid = talk_of(mk, lr)
    port = free_port()
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    threading.Thread(target=srv.run, daemon=True).start()
    end = time.monotonic() + 10
    while not srv.started:
        assert time.monotonic() < end, 'the server did not start in 10 s'
        time.sleep(.05)
    ids = lambda: [s['id'] for s in lr.talk(tid).slides]
    try:
        with pw.sync_playwright() as p:
            if not Path(p.chromium.executable_path).exists(): pytest.skip("Playwright's Chromium is not installed")
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page(viewport=dict(width=1280, height=900)); pg.goto(f'http://127.0.0.1:{port}/t/{tid}'); pg.wait_for_load_state('networkidle')
                focused = lambda: pg.evaluate("document.activeElement.dataset.sid || ''")
                pg.keyboard.press('s'); pg.keyboard.press('s'); assert focused() == 's2'
                pg.keyboard.press('w'); assert focused() == 's1'
                pg.keyboard.press('Shift+S'); pg.wait_for_function("document.activeElement.dataset.sid === 's1' && document.querySelectorAll('#deck li.slide')[1].dataset.sid === 's1'")
                assert ids()[:2] == ['s2', 's1']
                pg.keyboard.press('q'); pg.wait_for_function("document.querySelectorAll('#deck li.slide').length === 6 && document.activeElement.dataset.sid === 's1'")
                assert lr.talk(tid).slides[2]['kind'] == 'pause' and lr.talk(tid).slides[2]['prompt'] == 'Talk to your neighbour.'
                pg.keyboard.press('x'); assert pg.locator('#deck .sure').count() == 1 and len(ids()) == 6
                pg.keyboard.press('x'); pg.wait_for_function("document.querySelectorAll('#deck li.slide').length === 5 && !!document.activeElement.dataset.sid")
                pg.keyboard.press('w'); pg.keyboard.press('e')
                sid = pg.evaluate("document.activeElement.closest('li.slide').dataset.sid")
                assert pg.evaluate("document.activeElement.name") == 'notes'
                pg.screenshot(path=str(tmp_path/'editor.png'), full_page=True)
                pg.keyboard.press('Escape'); assert focused() == sid and pg.url.endswith(f'/t/{tid}')   # Esc closes the form, and does not go up
                pg.keyboard.press('e')
                box = pg.locator(f'li.slide[data-sid="{sid}"] textarea[name=beats]')
                box.fill('passage\nlit:<b>nope</b>'); pg.locator(f'li.slide[data-sid="{sid}"] form.slide-edit button').click()
                pg.wait_for_selector('#deck .req-err')
                err = pg.locator('#deck .req-err')
                assert 'lights text that is not in the passage' in err.inner_text() and err.locator('b').count() == 0   # text, never HTML
                assert pg.evaluate("document.querySelectorAll('.req-err').length") == 1
                pg.reload(); pg.wait_for_load_state('networkidle')   # the bad beat stays in the box until the page loads again
                notes = lr.talk(tid).slides[0]['notes']; sid = lr.talk(tid).slides[0]['id']   # the first slide has a choice question
                pg.evaluate(f"document.querySelector('li.slide[data-sid=\"{sid}\"] details.edit').open = true")
                pg.locator(f'li.slide[data-sid="{sid}"] input[type=radio][value="1"]').check()
                pg.screenshot(path=str(tmp_path/'choice.png'), full_page=True)
                pg.locator(f'li.slide[data-sid="{sid}"] form.slide-edit button').click()
                pg.wait_for_function(f"document.activeElement.dataset.sid === '{sid}'")
                a = lr.talk(tid).slides[0]['ask']   # the radio button sends the right option; the other fields stay
                assert a['answer'] == 1 and a['options'] == CHOICE['options'] and lr.talk(tid).slides[0]['notes'] == notes
            finally: b.close()
    finally: srv.should_exit = True

def test_editor_options_and_guards(mk, talk_fake, lr):
    "The editor sends a box for each option and a radio button on the right one; an order is listed right and saved mixed; on and off only."
    cl, tid = talk_of(mk, lr)
    post = lambda **kw: cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', **kw))
    page = cl.get(f'/t/{tid}').text
    assert 'from 0' not in page and 'name="answer"' in page and 'type="radio"' in page
    boxes = ['Weights', '', 'Largest only', 'In order', '', '']   # empty boxes do not count: the radio on box 3 is option 2
    assert post(kind='choice', q='Q?', options=boxes, answer='3').status_code == 200
    a = lr.talk(tid).slides[0]['ask']; assert a['options'] == ['Weights', 'Largest only', 'In order'] and a['answer'] == 2
    assert post(kind='choice', q='Q?', options=boxes, answer='1').text == 'Pick an option that has text.'
    assert post(kind='choice', q='Q?', options=boxes).status_code == 200   # the same kind: the right option stays
    right = ['Dot products', 'Divide', 'Softmax', 'Weigh', '', '']
    assert post(kind='order', q='Put them in order.', options=right, answer='0').status_code == 200
    a = lr.talk(tid).slides[0]['ask']; assert [a['options'][i] for i in a['answer']] == right[:4] and a['options'] != right[:4]
    assert all(f'value="{o}"' in cl.get(f'/t/{tid}').text for o in right[:4])
    page = cl.get(f'/t/{tid}').text; at = [page.index(f'value="{o}"') for o in right[:4]]
    assert at == sorted(at)   # the editor lists the order right
    assert post(show_passage='yes').status_code == 400 and lr.talk(tid).slides[0]['beats'] == ['passage']
    assert cl.post(f'/t/{tid}/slot', data=dict(phones='maybe')).status_code == 400 and lr.talk(tid).phones is False
    cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='pause'))
    pause = lr.talk(tid).slides[1]['id']
    r = cl.post(f'/t/{tid}/slide', data=dict(sid=pause, act='edit', kind='choice', q='Q?', options='a\nb', answer='0'))
    assert r.status_code == 400 and r.text == 'This slide has no question for the room.' and lr.talk(tid).slides[1]['ask'] is None
    assert 'class="quiet small danger"' in cl.get(f'/t/{tid}').text   # Take it out looks like a danger

# --- the presenter view, the audience view, hands and the talk keys --------------------------------------------------

def started(cl, lr):
    "A talk on the prepared walk, started; return (tid, run)."
    tid = make_talk(cl, prep_walk(lr, walk(cl, lr))); cl.post(f'/t/{tid}/start')
    return tid, lr.run(lr.talk(tid).live)

def test_start_and_present(mk, talk_fake, lr):
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr)))
    assert cl.get(f'/t/{tid}/present', follow_redirects=False).headers['location'] == f'/t/{tid}'
    r = cl.post(f'/t/{tid}/start', follow_redirects=False)
    run = lr.run(lr.talk(tid).live)
    assert r.headers['location'] == f'/t/{tid}/present' and run['at']['slide'] == 's1'
    page = cl.get(f'/t/{tid}/present').text
    assert '<nav' not in page and 'Softmax makes weights from scores.' in page and f'/t/{tid}/audience?k={run["key"]}' in page
    assert f'data-channel="{tid}:{run["key"]}"' in page

def test_audience_has_no_notes_and_no_answers(mk, talk_fake, lr):
    cl = mk(); tid, run = started(cl, lr)
    a = cl.get(f'/t/{tid}/audience?k={run["key"]}').text
    assert '<nav' not in a and 'Softmax makes weights' not in a and '"answer"' not in a and 'data-answer' not in a
    assert 'It falls' in a and 'softmax-temperature' in a                                   # the public options, and the demo spec for the live demo
    h = hashlib.sha256(PNG).hexdigest()
    assert f'/t/{tid}/img/{h}' in a and cl.get(f'/t/{tid}/img/{h}').headers['content-type'] == 'image/png'
    assert cl.get(f'/t/{tid}/img/{"0" * 64}').status_code == 404 and cl.get(f'/t/{tid}/img/vault.db').status_code == 404

def test_audience_needs_the_run_key(mk, talk_fake, lr):
    cl = mk(); tid, run = started(cl, lr)
    assert cl.get(f'/t/{tid}/audience?k=0000000000000000').status_code == 403 and cl.get(f'/t/{tid}/audience').status_code == 403
    assert cl.get(f'/t/{tid}/audience', params=dict(k='é' * 16)).status_code == 403

def test_place_survives_a_reload(mk, talk_fake, lr):
    cl = mk(); tid, run = started(cl, lr)
    assert cl.post(f'/t/{tid}/at', data=dict(slide='s3', beat=2)).status_code == 200
    assert lr.run(run['id'])['at'] == dict(slide='s3', beat=2, blank=False, pane=None, ask=None)
    assert 'data-slide="s3" data-beat="2"' in cl.get(f'/t/{tid}/present').text
    assert 'data-slide="s3" data-beat="2"' in cl.get(f'/t/{tid}/audience?k={run["key"]}').text
    for bad in (dict(slide='s9', beat=1), dict(slide='s3', beat=3), dict(slide='s3', beat=0), dict(slide='s3', beat=1, pane='https://evil.example/')):
        assert cl.post(f'/t/{tid}/at', data=bad).status_code == 400, bad
    assert lr.run(run['id'])['at']['slide'] == 's3'

def test_hands_and_result_stay_out_of_learning(mk, talk_fake, lr):
    cl = mk(); tid, run = started(cl, lr); n0 = len(lr.attempts(limit=1000))
    m = cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='open')).json()
    assert m == dict(v=1, t='ask', slide='s3', ask=dict(kind='choice', q='T goes from 1 to 2. What happens to the share of Paris?', options=['It rises', 'It falls', 'It stays the same']))
    cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='main', main=0))
    res = cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='reveal')).json()
    assert res == dict(v=1, t='result', slide='s3', kind='choice', rounds=[], right=1, main=0)
    assert lr.run(run['id'])['asks']['s3'] == dict(kind='choice', rounds=[], main=0, shown=[])
    assert len(lr.attempts(limit=1000)) == n0
    assert cl.post(f'/t/{tid}/ask', data=dict(slide='s4', act='open')).status_code == 400   # the questions slide has no question

def test_talk_keys_are_in_the_table():
    from abhyasa.core.keys import KEYS
    assert ('Talk', 'D', 'Next beat, then the next slide') in KEYS and ('Talk', 'Q', 'Ask the room, or close the question') in KEYS
    assert ('Talk', '⌥S', 'The main button: start the talk, ask the room, vote again, end the talk') in KEYS
    assert not [k for g, k, _ in KEYS if g == 'Talk' and k in ('⌥Q', '⌥R', '⌥X', '⌥E')]   # no new ⌥ key

def test_a_new_slide_opens_clean(mk, talk_fake, lr):
    "A move on the same slide keeps the blank screen, the pane and the question; a new slide clears them, and the reply closes the question."
    cl = mk(); tid, run = started(cl, lr)
    post = lambda **kw: cl.post(f'/t/{tid}/at', data=kw)
    cl.post(f'/t/{tid}/ask', data=dict(slide='s1', act='open'))
    d = cl.post(f'/t/{tid}/beside', data=dict(slide='s1', slug='softmax', how='primer')).json()
    r = post(slide='s1', beat=1, blank=1, pane=d['url']).json()
    assert r['at'] == dict(slide='s1', beat=1, blank=True, pane=d['url'], ask='s1')
    assert dict(v=1, t='pane', url=d['pane'], page=0) in r['msgs'] and dict(v=1, t='blank', on=True) in r['msgs']
    r = post(slide='s2', beat=1).json()
    assert r['at'] == dict(slide='s2', beat=1, blank=False, pane=None, ask=None) and dict(v=1, t='ask', slide='s1', ask=None) in r['msgs']
    assert post(slide='s2', beat=1, pane='').status_code == 200 and post(slide='s2', beat=1, blank='yes').status_code == 400
    assert post(slide='s2', beat=1, pane='/w/../0').status_code == 400 and post(slide='s2', beat='x').status_code == 400
    assert post(slide='s2', beat=1, pane=d['url']).status_code == 400   # the primer closed with its slide: its URL is no good now
    for bad in ('/w/g-1a2b/0', '/w/x/0?a?pane=1&talk=1', '/w/x/0?a#?pane=1&talk=1'): assert post(slide='s2', beat=1, pane=bad).status_code == 400, bad
    assert [x['slide'] for x in lr.run(run['id'])['shown']] == ['s1', 's2']

def test_question_guards_and_pair(mk, talk_fake, lr):
    "A hands pick out of range is refused; pair gives the prompt with the setting; an unknown act is refused; start again goes to the same run."
    cl = mk(); tid, run = started(cl, lr)
    post = lambda **kw: cl.post(f'/t/{tid}/ask', data=dict(slide='s3', **kw))
    assert post(act='main', main=3).status_code == 400 and post(act='main', main='x').status_code == 400 and post(act='fly').status_code == 400
    assert post(act='pair', on=1).json() == dict(v=1, t='pair', on=True, prompt=f"Talk to your neighbour for {val('talks.pair_min')} minutes.")
    assert post(act='close').json() == dict(v=1, t='ask', slide='s3', ask=None)
    assert cl.post(f'/t/{tid}/ask', data=dict(slide='s9', act='open')).status_code == 400
    cl.post(f'/t/{tid}/start'); assert lr.talk(tid).live == run['id'] and len(lr.runs(tid)) == 1

def test_run_posts_are_local_only(mk, talk_fake, lr):
    "start, at and ask are behind LocalOnly: a foreign Origin is refused, and the place does not change."
    cl = mk(); tid, run = started(cl, lr)
    evil = {'Origin': 'https://evil.example'}
    for path, data in ((f'/t/{tid}/start', {}), (f'/t/{tid}/at', dict(slide='s2', beat=1)), (f'/t/{tid}/ask', dict(slide='s3', act='open'))):
        assert cl.post(path, data=data, headers=evil).status_code == 403, path
    assert lr.run(run['id'])['at'] == dict(slide='s1', beat=1, blank=False, pane=None, ask=None)

def test_room_spec_takes_out_each_gate_answer():
    "room_spec takes `answer` out of a gate at any depth, and keeps the rest; a state-path gate keeps its state, where the value stays."
    from abhyasa.core import room_spec
    gate = dict(type='gate', id='g', prompt='Which?', options=['a', 'b'], answer={'is': 'b'})
    spec = dict(id='d', state=dict(best='b'), blocks=[dict(type='row', blocks=[dict(type='stack', blocks=[gate])]),
                                                       dict(type='gate', id='h', prompt='Best?', options={'from': 'opts'}, answer='best'),
                                                       dict(type='caption', answer='not a gate', text='x')])
    out = room_spec(spec)
    assert 'answer' not in out['blocks'][0]['blocks'][0]['blocks'][0] and out['blocks'][0]['blocks'][0]['blocks'][0]['options'] == ['a', 'b']
    assert 'answer' not in out['blocks'][1] and out['state'] == dict(best='b')   # the state path is gone; the state is the demo's own
    assert out['blocks'][2]['answer'] == 'not a gate' and spec['blocks'][1]['answer'] == 'best' and gate['answer'] == {'is': 'b'}   # a copy

def test_result_and_pair_stay_for_a_reload(mk, talk_fake, lr):
    "The result, the pair prompt and the slides whose answer showed are in the run log; the presenter page has them; a new slide clears them."
    cl = mk(); tid, run = started(cl, lr)
    post = lambda **kw: cl.post(f'/t/{tid}/ask', data=dict(slide='s3', **kw))
    cl.post(f'/t/{tid}/at', data=dict(slide='s3', beat=1))
    post(act='open'); post(act='main', main=0); res = post(act='reveal').json(); pair = post(act='pair', on=1).json()
    assert lr.run(run['id'])['stage'] == dict(result=res, pair=pair, revealed=['s3'])
    cl.post(f'/t/{tid}/at', data=dict(slide='s3', beat=2))
    page = cl.get(f'/t/{tid}/present').text
    assert 'data-result="null"' not in page and 'data-pair="null"' not in page and 'class="shaky"' in page   # most hands chose a wrong option
    cl.post(f'/t/{tid}/at', data=dict(slide='s4', beat=1))
    assert lr.run(run['id'])['stage'] == dict(result=None, pair=None, revealed=['s3']) and 'class="shaky"' in cl.get(f'/t/{tid}/present').text

# --- the side pane in a talk, and after the talk --------------------------------------------------------------------------

def test_beside_opens_a_primer_for_the_room(mk, talk_fake, lr):
    cl = mk(); tid, run = started(cl, lr)
    assert 'Softmax' in cl.post(f'/t/{tid}/beside', data=dict(slide='s3')).text      # the needs of idea 3
    d = cl.post(f'/t/{tid}/beside', data=dict(slide='s3', slug='softmax', how='primer')).json()
    sid = d['url'].split('/')[2]
    assert d['pane'] == f'/w/{sid}/0?pane=1&talk=1' and lr.journey(sid).parent == {'talk': tid, 'slide': 's3'}
    assert cl.post(f'/t/{tid}/at', data=dict(slide='s3', beat=1, pane=d['url'])).status_code == 200
    cl.post(f'/t/{tid}/beside', data=dict(close='1'))
    assert lr.run(run['id'])['beside'][0]['slug'] == 'softmax'
    assert cl.post(f'/t/{tid}/beside', data=dict(slide='s3', slug='softmax', how='session')).status_code == 400

def test_primer_pages(mk, talk_fake, lr):
    "The page of the primer beside a slide goes into the run log and the pane message; with no primer, or out of range, it is refused."
    cl = mk(); tid, run = started(cl, lr)
    post = lambda **kw: cl.post(f'/t/{tid}/at', data=dict(slide='s3', beat=1, **kw))
    assert post(page=1).status_code == 400   # no primer is open
    d = cl.post(f'/t/{tid}/beside', data=dict(slide='s3', slug='softmax', how='primer')).json()
    assert post(pane=d['url']).status_code == 200
    r = post(page=2).json()
    assert dict(v=1, t='pane', url=d['pane'], page=2) in r['msgs'] and lr.run(run['id'])['side']['page'] == 2
    assert dict(v=1, t='pane', url=d['pane'], page=2) in post().json()['msgs']   # a move on the same slide keeps the page
    for bad in ('-1', '20', 'x'): assert post(page=bad).status_code == 400, bad
    r = cl.post(f'/t/{tid}/at', data=dict(slide='s4', beat=1)).json()   # a new slide closes the primer, and its page
    assert dict(v=1, t='pane', url=None, page=0) in r['msgs'] and not lr.run(run['id'])['side']

def test_a_primer_in_a_talk_is_short():
    "A primer for the room has no picture and no heading, and whole sentences up to about 240 characters; one short line stays."
    from abhyasa.blocks.walk.ui import talk_text
    long = ('We suspect that for large values of dk, the dot products grow large in magnitude, pushing the softmax function into regions '
            'where it has extremely small gradients. 3.2.1 Scaled Dot-Product Attention We compute the dot products of the query with all keys, '
            'divide each by √dk, and apply a softmax function. ![Figure 2](images/fig2.png) 1 Introduction')
    assert talk_text(long) == long.split(' 3.2.1')[0]
    assert talk_text('3.2.1 Scaled Dot-Product Attention\n\nWe compute the dot.\n\n![Figure 2](images/fig2.png)') == 'We compute the dot.'
    assert talk_text('apply a softmax function to obtain the weights on the values') == 'apply a softmax function to obtain the weights on the values'
    assert talk_text('# Head\n\nOne. Two. Three.', 6) == 'One.' and talk_text('word ' * 200).endswith('word…') and len(talk_text('word ' * 200)) <= 481

def test_end_and_after_the_talk(mk, talk_fake, lr, monkeypatch):
    cl = mk(); tid, run = started(cl, lr)
    cl.post(f'/t/{tid}/ask', data=dict(slide='s1', act='open')); cl.post(f'/t/{tid}/ask', data=dict(slide='s1', act='main', main=1))
    r = cl.post(f'/t/{tid}/end', follow_redirects=False)
    assert r.headers['location'] == f'/t/{tid}/after?run={run["id"]}' and lr.talk(tid).live is None and lr.run(run['id'])['ended']
    page = cl.get(r.headers['location']).text
    assert 'Where the room was unsure' in page and 'Most hands: B (right: A)' in page
    assert 'The answers of the room do not change your own learning.' in page
    f = cl.get(f'/t/{tid}/recap.html?run={run["id"]}')
    assert 'attachment' in f.headers['content-disposition'] and '-recap.html' in f.headers['content-disposition'] and '<script' not in f.text
    goals = []
    monkeypatch.setattr('abhyasa.blocks.talk.app.walk_from_topic', lambda lr, ask, goal, **kw: goals.append(goal) or AttrDict(id='review-ab12'))
    assert cl.post(f'/t/{tid}/follow', data=dict(run=run['id']), follow_redirects=False).headers['location'] == '/w/review-ab12'
    assert goals == ['Review: Sequential computation']
    cl.post(f'/t/{tid}/slide', data=dict(sid='s3', act='primer', slug='softmax'))
    t = lr.talk(tid); assert [s['kind'] for s in t.slides][2:4] == ['primer', 'idea'] and t.slides[2]['title'] == 'Softmax'

def test_beside_guards_and_the_pane_question(mk, talk_fake, lr):
    "No second pane while one is open (409); Q with the pane open asks on the primer's idea, one model call; a new slide closes the pane."
    cl = mk(); tid, run = started(cl, lr)
    post = lambda **kw: cl.post(f'/t/{tid}/beside', data=kw)
    assert post(slide='s9').status_code == 400 and post(slide='s3', slug='nope', how='primer').status_code == 400
    d = post(slide='s3', slug='softmax', how='primer').json()
    assert post(slide='s3').status_code == 409 and post(slide='s3', slug='softmax', how='primer').status_code == 409
    cl.post(f'/t/{tid}/at', data=dict(slide='s3', beat=1, pane=d['url']))
    asked = lambda: sum('You turn one check' in str(c) for c in talk_fake.calls); calls = asked()
    m = cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='open', pane=1)).json()
    assert m['msg'] == dict(v=1, t='ask', slide='s3', ask=dict(kind='choice', q=CHOICE['q'], options=CHOICE['options'])) and m['ask']['answer'] == 0
    assert 'answer' not in m['msg']['ask']
    assert cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='open', pane=1)).json()['ask'] == m['ask']   # kept in the run
    assert asked() == calls + 1   # one model call for two opens
    cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='main', main=2, pane=1))
    assert cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='reveal', pane=1)).json() == dict(v=1, t='result', slide='s3', kind='choice', rounds=[], right=0, main=2)
    r = lr.run(run['id']); assert r['side']['main'] == 2 and 's3' not in r['asks']   # the pane question is not the slide's own
    r = cl.post(f'/t/{tid}/at', data=dict(slide='s4', beat=1)).json()
    assert dict(v=1, t='pane', url=None, page=0) in r['msgs'] and [x['slug'] for x in lr.run(run['id'])['beside']] == ['softmax'] and not lr.run(run['id'])['side']
    b = lr.run(run['id'])['beside'][0]; assert b['main'] == 2 and b['ask'] == m['ask']   # the question on the primer is kept
    assert cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='open', pane=1)).status_code == 400   # no pane is open now
    evil = {'Origin': 'https://evil.example'}
    for path, data in ((f'/t/{tid}/beside', dict(slide='s3')), (f'/t/{tid}/end', {}), (f'/t/{tid}/follow', dict(run=run['id']))):
        assert cl.post(path, data=data, headers=evil).status_code == 403, path

def test_after_guards_and_the_recap_file(mk, talk_fake, lr):
    "A run of another talk is not found; Look at it first shows the file inline with a strict policy; Add it to the talk works from the page."
    cl = mk(); tid, run = started(cl, lr)
    d = cl.post(f'/t/{tid}/beside', data=dict(slide='s3', slug='softmax', how='primer')).json()
    cl.post(f'/t/{tid}/at', data=dict(slide='s3', beat=1, pane=d['url']))
    cl.post(f'/t/{tid}/end')
    assert cl.post(f'/t/{tid}/end', follow_redirects=False).headers['location'] == f'/t/{tid}/after?run={run["id"]}'   # a second press
    assert cl.get(f'/t/{tid}/after?run=run-00000000').status_code == 404 and cl.get('/t/nope/after').status_code == 404
    page = cl.get(f'/t/{tid}/after').text   # the newest run
    assert 'Next time: put the Softmax primer before idea 3' in page and 'Add it to the talk' in page
    f = cl.get(f'/t/{tid}/recap.html?run={run["id"]}&look=1')
    assert f.headers['content-disposition'] == 'inline' and "default-src 'none'" in f.headers['content-security-policy']
    assert cl.post(f'/t/{tid}/follow', data=dict(run=run['id'])).status_code == 400   # the room was sure on each idea
    assert cl.post(f'/t/{tid}/follow', data=dict(run='run-00000000')).status_code == 404
    r = cl.post(f'/t/{tid}/slide', data=dict(sid='s3', act='primer', slug='softmax', **{'from': 'after'}))
    assert 'is in the talk now' in r.text and lr.talk(tid).slides[2]['kind'] == 'primer'
    assert 'It is in the talk now.' in cl.get(f'/t/{tid}/after').text

def test_a_question_on_a_primer_is_in_the_recap(mk, talk_fake, lr, monkeypatch):
    "Most hands chose a wrong option on the primer's question: After the talk shows it after its slide, and the follow-up walk has its idea."
    cl = mk(); tid, run = started(cl, lr)
    d = cl.post(f'/t/{tid}/beside', data=dict(slide='s3', slug='softmax', how='primer')).json()
    cl.post(f'/t/{tid}/at', data=dict(slide='s3', beat=1, pane=d['url']))
    cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='open', pane=1)); cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='main', main=1, pane=1))
    page = cl.get(cl.post(f'/t/{tid}/end', follow_redirects=False).headers['location']).text
    assert 'Softmax (beside idea 3)' in page and 'Most hands: B (right: A)' in page and '1 question to the room' in page
    goals = []
    monkeypatch.setattr('abhyasa.blocks.talk.app.walk_from_topic', lambda lr, ask, goal, **kw: goals.append(goal) or AttrDict(id='review-ab12'))
    cl.post(f'/t/{tid}/follow', data=dict(run=run['id']), follow_redirects=False)
    assert goals == ['Review: Softmax']

def test_a_talk_side_walk_is_not_your_learning(mk, talk_fake, lr, monkeypatch):
    "A side walk that a talk made is not in Continue, in Journeys or on the concept page; its step keeps no read time and starts no demo."
    cl = mk(); tid, run = started(cl, lr)
    jobs = []
    monkeypatch.setattr('abhyasa.blocks.walk.app.queue_demo', lambda *a, **kw: jobs.append(a))
    d = cl.post(f'/t/{tid}/beside', data=dict(slide='s3', slug='softmax', how='walk')).json()
    sid = d['url'].split('/')[2]; j = lr.journey(sid)
    assert j.parent == {'talk': tid, 'slide': 's3'}
    other = next(c.slug for c in lr.concepts() if c.slug not in ('softmax', 'scaling-by-the-root-of-dk'))
    nxt = {**j.steps[0], 'slug': other, 'check': dict(way='demo', kind='demo', depth=2, why='')}   # a visit of step 0 would start its demo
    j = lr.put_journey({**j, 'steps': [*j.steps, nxt]})
    for i in range(len(j.steps)): assert cl.get(f'/w/{sid}/{i}?pane=1&talk=1').status_code == 200
    assert not any(s.get('read_at') for s in lr.journey(sid).steps) and jobs == []
    for page in ('/', '/journeys', '/c/softmax', '/learning'): assert f'/w/{sid}' not in cl.get(page).text, page
    lr.put_journey({**lr.journey(sid), 'parent': None}); cl.get(f'/w/{sid}/0')   # the same walk as your own: the visit is kept
    assert lr.journey(sid).steps[0].get('read_at') and jobs and f'/w/{sid}' in cl.get('/journeys').text

def serve(cl):
    "Run the app of `cl` on a free port in a thread; return (server, base URL)."
    import threading, time, uvicorn
    port = free_port()
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    threading.Thread(target=srv.run, daemon=True).start()
    end = time.monotonic() + 10
    while not srv.started:
        assert time.monotonic() < end, 'the server did not start in 10 s'
        time.sleep(.05)
    return srv, f'http://127.0.0.1:{port}'

HEARD = """(() => { const B = window.BroadcastChannel; window.heard = [];
  window.BroadcastChannel = class extends B { constructor(n) { super(n); this.addEventListener('message', e => heard.push(JSON.stringify(e.data))); } }; })()"""
NO_ANSWER = """(() => { const g = document.querySelector('section[data-sid=s3] [data-rupaka]').rupaka.spec.blocks.find(b => b.type === 'gate');
  return [...heard.filter(m => /"t":"answers"|"is":|"answer"/.test(m)), ...(/"answer"/.test(document.documentElement.outerHTML) ? ['the page'] : []),
          ...('answer' in g ? ['the gate'] : [])]; })()"""

def test_two_windows_in_a_browser(mk, talk_fake, lr, tmp_path):
    """In Chromium, a presenter page and an audience page of one run: the keys move both, a lit beat lights the words, a question
    opens with hands and the right answer, the demo follows the presenter, B blanks the room, a reload finds the place, and
    the stray keys do nothing."""
    pw = pytest.importorskip('playwright.sync_api')
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr)))
    p1 = lr.talk(tid).slides[0]['show']['passage']; words = ' '.join(p1.split()[1:3])
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', beats=f'passage\nlit:{words}')).status_code == 200
    cl.post(f'/t/{tid}/start'); run = lr.run(lr.talk(tid).live); n0 = len(lr.attempts(limit=1000))
    at = lambda: lr.run(run['id'])['at']
    srv, base = serve(cl)
    try:
        with pw.sync_playwright() as p:
            if not Path(p.chromium.executable_path).exists(): pytest.skip("Playwright's Chromium is not installed")
            b = p.chromium.launch(headless=True)
            try:
                c = b.new_context(viewport=dict(width=1280, height=800))
                errs = []
                pr = c.new_page(); pr.on('pageerror', lambda e: errs.append(str(e)))
                pr.goto(f'{base}/t/{tid}/present'); pr.wait_for_load_state('networkidle')
                au = c.new_page(); au.on('pageerror', lambda e: errs.append(str(e)))
                au.set_viewport_size(dict(width=1280, height=720))
                au.add_init_script(HEARD)   # each stage message that the audience window gets, as JSON
                au.goto(f'{base}/t/{tid}/audience?k={run["key"]}'); au.wait_for_load_state('networkidle')
                pr.wait_for_selector('#aud-live:not([hidden])')   # the audience window said hello: no popup opens on the first key
                pr.bring_to_front()
                shown = lambda pg: pg.evaluate("[document.getElementById('stage').dataset.slide, +document.getElementById('stage').dataset.beat, document.querySelector('#stage > section.stage:not([hidden])').dataset.sid]")
                assert shown(au) == ['s1', 1, 's1'] and au.locator('#stage mark.lit').count() == 0
                pr.keyboard.press('d')
                au.wait_for_function("document.getElementById('stage').dataset.beat === '2'")
                assert at()['beat'] == 2 and au.locator('#stage mark.lit').inner_text() == words and pr.locator('#stage mark.lit').inner_text() == words
                pr.keyboard.press('a'); au.wait_for_function("document.getElementById('stage').dataset.beat === '1'")
                assert au.locator('#stage mark.lit').count() == 0
                pr.keyboard.press('ArrowRight'); pr.keyboard.press('PageDown')   # a clicker: past the last beat goes to the next slide
                au.wait_for_function("document.getElementById('stage').dataset.slide === 's2'")
                assert at()['slide'] == 's2' and pr.locator('#notes > div:not([hidden])').inner_text().startswith('Softmax makes weights')
                pr.screenshot(path=str(tmp_path/'presenter-s2.png')); au.screenshot(path=str(tmp_path/'audience-s2.png'))
                pr.keyboard.press('g'); pr.keyboard.press('3')
                au.wait_for_function("document.getElementById('stage').dataset.slide === 's3'")
                pr.keyboard.press('d'); au.wait_for_function("document.querySelector('section[data-sid=s3] .demo:not([hidden]) [data-rk-ready]')")
                # the presenter picks at the gate: the talk settles it, so nothing goes to the learner; the audience copy follows
                why = pr.locator('section[data-sid=s3] .rk-gate textarea'); why.click(); pr.keyboard.type('a/b')
                assert why.input_value() == 'a/b'   # a / in a text box of the demo stays in the box
                pr.evaluate("""() => { const h = document.querySelector('section[data-sid=s3] [data-rupaka]');
                  h.querySelector('.rk-gate .opts button').click(); h.querySelector('.rk-gate button.go').click();
                  const i = h.querySelector('.rk-slider input'); i.value = 2; i.dispatchEvent(new Event('input', {bubbles: true})); }""")
                au.wait_for_function("document.querySelector('section[data-sid=s3] [data-rupaka]').rupaka.st.t === 2")
                assert au.evaluate("document.querySelector('section[data-sid=s3] [data-rupaka]').rupaka.st.gate.hot") == 'done'
                # the presenter's pick goes to the audience copy, but the room copy has no answer (room_spec), so it draws no verdict
                verdict = "(v => v.hidden ? null : v.textContent)(document.querySelector('section[data-sid=s3] .rk-gate .verdict'))"
                assert pr.evaluate("document.querySelector('section[data-sid=s3] [data-rupaka]')._mirror.snapshot().pick") == dict(hot=0)
                assert pr.evaluate(verdict).startswith('You said It rises. It is It falls.') and au.evaluate(verdict) is None
                assert au.evaluate("document.querySelector('section[data-sid=s3] .rk-gate').inert") is True
                au.screenshot(path=str(tmp_path/'audience-demo.png'))
                pr.wait_for_timeout(100)   # the demo fits its part in both windows, with no scroll, and at the same place on the slide
                box = "(() => { const st = document.getElementById('stage').getBoundingClientRect(), d = document.querySelector('section[data-sid=s3] .demo'), " \
                      "s = d.querySelector('.rk-slider').getBoundingClientRect(), h = d.querySelector('[data-rupaka]').getBoundingClientRect(), b = d.getBoundingClientRect(); " \
                      "return {fits: h.bottom <= b.bottom + 1 && h.right <= b.right + 1 && s.bottom <= innerHeight && d.scrollHeight <= d.clientHeight + 1, " \
                      "page: document.documentElement.scrollHeight <= innerHeight, x: (s.left - st.left) / st.width, y: (s.top - st.top) / st.height}; })()"
                fa, fp = au.evaluate(box), pr.evaluate(box)
                assert fa['fits'] and fa['page'] and fp['fits'] and abs(fa['x'] - fp['x']) < .01 and abs(fa['y'] - fp['y']) < .01, (fa, fp)
                pr.keyboard.press('e'); assert pr.evaluate("!!document.activeElement.closest('[data-rupaka]')")   # E goes into the demo
                pr.keyboard.press('d'); pr.wait_for_timeout(150); assert at()['beat'] == 2   # there the demo's own keys win
                pr.keyboard.press('Escape'); assert pr.evaluate("!document.activeElement.closest('[data-rupaka]')") and at()['slide'] == 's3'
                pr.keyboard.press('q'); au.wait_for_selector('#stage .stage-ask:not([hidden])')
                assert 'It falls' in au.locator('#stage .stage-ask').inner_text() and at()['ask'] == 's3'
                assert au.locator('#stage .stage-ask li.right').count() == 0   # no answer before R
                au.reload(); au.wait_for_selector('#stage .stage-ask:not([hidden])')   # a reload in the middle of a question catches up
                assert shown(au)[0] == 's3'
                au.wait_for_function("document.querySelector('section[data-sid=s3] [data-rupaka]').rupaka?.st.t === 2")   # and the demo state
                assert au.evaluate(verdict) is None   # and still no verdict
                assert au.evaluate(NO_ANSWER) == []   # before R: no answer in the messages, the page or the room copy of the gate
                pr.bring_to_front(); pr.keyboard.press('1'); pr.keyboard.press('r')
                au.wait_for_selector('#stage .stage-ask li.right')
                au.wait_for_function(f"({verdict} || '').startsWith('You said It rises. It is It falls.')")   # after R the room sees the verdict of the pick
                au.reload(); au.wait_for_selector('#stage .stage-ask li.right')
                au.wait_for_function(f"({verdict} || '').startsWith('You said It rises. It is It falls.')")   # a reload after R gets it on hello
                assert au.locator('#stage .stage-ask li.right').inner_text().startswith('BIt falls') or 'It falls' in au.locator('#stage .stage-ask li.right').inner_text()
                assert lr.run(run['id'])['asks']['s3']['main'] == 0
                pr.screenshot(path=str(tmp_path/'presenter.png')); au.screenshot(path=str(tmp_path/'audience.png'))
                pr.reload(); pr.wait_for_load_state('networkidle')   # the run log keeps the result: a reload of both windows shows it again
                assert pr.locator('#rail i.shaky').count() == 1 and pr.locator('#stage .stage-ask li.right').count() == 1
                au.reload(); au.wait_for_selector('#stage .stage-ask li.right')
                pr.bring_to_front()
                pr.keyboard.press('Escape'); au.wait_for_selector('#stage .stage-ask', state='hidden')
                assert at()['ask'] is None
                pr.keyboard.press('b'); au.wait_for_function("document.getElementById('stage').classList.contains('blank')")
                assert at()['blank'] is True
                pr.keyboard.press('b'); au.wait_for_function("!document.getElementById('stage').classList.contains('blank')")
                url = pr.url
                for k in ('Alt+t', 'Alt+c', 'Alt+g', 'Alt+d', '/', 'Escape'): pr.keyboard.press(k)
                pr.wait_for_timeout(200); assert pr.url == url   # a stray key never leaves a live talk
                pr.reload(); pr.wait_for_load_state('networkidle')
                assert shown(pr)[0] == 's3' and pr.locator('#ask-card .ask-q:not([hidden])').count() == 1
                au.bring_to_front(); au.keyboard.press('d'); au.wait_for_selector('#keys-note:not([hidden])')   # keys work in the presenter window
                assert at()['beat'] == 2 and len(lr.attempts(limit=1000)) == n0 and not errs, errs
                # each answers message names its demo; a new slide takes the old slide's answers out of the audience copy
                pr.evaluate("""() => { const h = document.querySelector('section[data-sid=s3] [data-rupaka]');
                  h.querySelector('.rk-gate .opts button').click(); h.querySelector('.rk-gate button.go').click(); }""")   # the reload opened the gate again
                slug = au.evaluate("document.querySelector('section[data-sid=s3] [data-rupaka]').dataset.demo")
                au.wait_for_function(f"({verdict} || '').startsWith('You said It rises. It is It falls.')")   # s3 was revealed: the answers come again
                sent = [json.loads(m) for m in au.evaluate('heard') if '"t":"answers"' in m]
                assert sent and all(m['slug'] == slug for m in sent)
                pr.bring_to_front(); pr.keyboard.press('g'); pr.keyboard.press('2')
                au.wait_for_function("document.getElementById('stage').dataset.slide === 's2'")
                assert au.evaluate(NO_ANSWER.replace('heard.filter', '[].filter')) == [] and au.evaluate(verdict) is None
                ua = pr.evaluate('navigator.userAgent') + ' Abhyasa/0.0.12'   # Abhyasa.app: the presenter page shows its address, and opens no window
                c2 = b.new_context(user_agent=ua); ap = c2.new_page(); ap.goto(f'{base}/t/{tid}/present'); ap.wait_for_load_state('networkidle')
                ap.wait_for_selector('#aud-app:not([hidden])'); ap.mouse.click(5, 5); ap.wait_for_timeout(200)
                assert ap.locator('#app-url').inner_text() == ap.url and len(c2.pages) == 1 and ap.locator('#aud-open').is_hidden()
            finally: b.close()
    finally: srv.should_exit = True

def test_beside_and_end_in_a_browser(mk, talk_fake, lr, tmp_path):
    """In Chromium, with both windows: ⌥B shows the offer in the presenter window only, 1 opens the primer beside the slide in both
    windows in the talk type, Q asks the room about the primer, ⌥Z closes it in both, and ⌥S on the last slide ends the talk."""
    pw = pytest.importorskip('playwright.sync_api')
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr)))
    cl.post(f'/t/{tid}/start'); run = lr.run(lr.talk(tid).live); n0 = len(lr.attempts(limit=1000)); n = len(lr.talk(tid).slides)
    at = lambda: lr.run(run['id'])['at']
    srv, base = serve(cl)
    try:
        with pw.sync_playwright() as p:
            if not Path(p.chromium.executable_path).exists(): pytest.skip("Playwright's Chromium is not installed")
            b = p.chromium.launch(headless=True)
            try:
                c = b.new_context(viewport=dict(width=1440, height=900), reduced_motion='reduce')
                errs = []
                pr = c.new_page(); pr.on('pageerror', lambda e: errs.append(str(e)))
                pr.goto(f'{base}/t/{tid}/present'); pr.wait_for_load_state('networkidle')
                au = c.new_page(); au.on('pageerror', lambda e: errs.append(str(e)))
                au.set_viewport_size(dict(width=1280, height=720))
                au.goto(f'{base}/t/{tid}/audience?k={run["key"]}'); au.wait_for_load_state('networkidle')
                pr.wait_for_selector('#aud-live:not([hidden])'); pr.bring_to_front()
                pr.keyboard.press('g'); pr.keyboard.press('3'); au.wait_for_function("document.getElementById('stage').dataset.slide === 's3'")
                for bad in ('/w/x/0?a?pane=1&talk=1', '/w/x/0?a#?pane=1&talk=1', '/w/x/0?pane=1&talk=1&x=1'):   # the channel checks only is_local
                    pr.evaluate("([ch, u]) => { const b = new BroadcastChannel('abhyasa-stage:' + ch); b.postMessage({v: 1, t: 'pane', url: u}); b.close(); }",
                                [f"{tid}:{run['key']}", bad])
                au.wait_for_timeout(200); assert au.locator('#stage > iframe.stage-pane').count() == 0   # the audience window opens no such pane
                pr.keyboard.press('Alt+b'); pr.wait_for_selector('#beside-offer .bs-offer')
                assert 'Softmax' in pr.locator('#beside-offer').inner_text() and au.locator('.bs-offer').count() == 0   # the offer is for the presenter only
                pr.keyboard.press('1')
                au.wait_for_selector('#stage.beside > iframe.stage-pane')
                src = au.locator('#stage > iframe.stage-pane').get_attribute('src')
                assert src.endswith('/0?pane=1&talk=1') and at()['pane'] == src.split('?')[0]
                pr.wait_for_function("document.documentElement.classList.contains('rh-open')")
                fr = au.frame_locator('#stage > iframe.stage-pane')
                fr.locator('h1.idea').wait_for()
                assert fr.locator('#check').count() == 0 and fr.locator('#note').count() == 0 and 'Softmax' in fr.locator('h1.idea').inner_text()
                assert au.evaluate("document.querySelector('#stage > iframe.stage-pane').contentDocument.documentElement.classList.contains('talk-type')")
                au.wait_for_timeout(300); au.screenshot(path=str(tmp_path/'audience-beside.png')); pr.screenshot(path=str(tmp_path/'presenter-beside.png'))
                pr.keyboard.press('q'); au.wait_for_selector('#stage .stage-ask:not([hidden])')
                assert 'What does softmax give' in au.locator('#stage .stage-ask').inner_text() and pr.locator('#ask-side').is_visible()
                pr.keyboard.press('1'); pr.keyboard.press('r'); au.wait_for_selector('#stage .stage-ask li.right')
                assert lr.run(run['id'])['side']['main'] == 0 and 's3' not in lr.run(run['id'])['asks']   # the pane question is not the slide's
                sid = src.split('/')[2]; assert not lr.journey(sid).steps[0].get('read_at')   # the side walk of a talk keeps no read time
                pr.keyboard.press('Escape'); au.wait_for_selector('#stage .stage-ask', state='hidden')
                pr.keyboard.press('Alt+b'); pr.wait_for_timeout(200)
                assert pr.locator('#beside-offer .bs-offer').count() == 0 and 'Close the side pane first' in pr.locator('#say').inner_text()   # no nesting
                pr.keyboard.press('Alt+z')
                au.wait_for_function("!document.getElementById('stage').classList.contains('beside')")
                pr.wait_for_function("!document.documentElement.classList.contains('rh-open')")
                pr.wait_for_timeout(300)
                r = lr.run(run['id']); assert r['at']['pane'] is None and [x['slug'] for x in r['beside']] == ['softmax'] and not r.get('side')
                assert r['beside'][0]['main'] == 0 and r['beside'][0]['ask']['q'] == CHOICE['q']   # the question on the primer is kept
                pr.keyboard.press('g'); pr.keyboard.press(str(n)); au.wait_for_function(f"document.getElementById('stage').dataset.slide === 's{n}'")
                pr.wait_for_function("document.querySelector('#ask-go .act').textContent === 'End the talk'")
                pr.keyboard.press('Alt+s'); pr.wait_for_url(f'**/t/{tid}/after?run={run["id"]}')
                au.wait_for_selector('#stage .stage-pair:not([hidden])'); assert 'Thank you' in au.locator('#stage .stage-pair').inner_text()
                assert 'After the talk' in pr.locator('h1').inner_text() and 'Next time: put the Softmax primer before idea 3' in pr.content()
                pr.screenshot(path=str(tmp_path/'after.png'), full_page=True)
                assert lr.talk(tid).live is None and len(lr.attempts(limit=1000)) == n0 and not errs, errs
            finally: b.close()
    finally: srv.should_exit = True

def test_narrow_presenter_stops_at_the_last_page(mk, talk_fake, lr):
    "A presenter window with no side pane (narrow) learns the page count from the audience window, so D stops at the last page; a bad count is ignored."
    pw = pytest.importorskip('playwright.sync_api')
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr)))
    cl.post(f'/t/{tid}/start'); run = lr.run(lr.talk(tid).live)
    side = lambda: (lr.run(run['id']).get('side') or {}).get('page')
    srv, base = serve(cl)
    try:
        with pw.sync_playwright() as p:
            if not Path(p.chromium.executable_path).exists(): pytest.skip("Playwright's Chromium is not installed")
            b = p.chromium.launch(headless=True)
            try:
                c = b.new_context(viewport=dict(width=1000, height=800), reduced_motion='reduce')
                errs = []
                pr = c.new_page(); pr.on('pageerror', lambda e: errs.append(str(e)))
                pr.goto(f'{base}/t/{tid}/present'); pr.wait_for_load_state('networkidle')
                au = c.new_page(); au.on('pageerror', lambda e: errs.append(str(e)))
                au.add_init_script("(() => { const si = window.setInterval; window.setInterval = (f, t, ...a) => si(t === 700 ? () => { if (!window.__quiet) f(); } : f, t, ...a); })()")   # the count report can stop
                au.set_viewport_size(dict(width=1280, height=720))
                au.goto(f'{base}/t/{tid}/audience?k={run["key"]}'); au.wait_for_load_state('networkidle')
                pr.wait_for_selector('#aud-live:not([hidden])'); pr.bring_to_front()
                pr.keyboard.press('g'); pr.keyboard.press('3'); au.wait_for_function("document.getElementById('stage').dataset.slide === 's3'")
                pr.keyboard.press('Alt+b'); pr.wait_for_selector('#beside-offer .bs-offer'); pr.keyboard.press('1')
                au.wait_for_selector('#stage.beside > iframe.stage-pane')
                assert pr.locator('#rh-pane iframe').count() == 0   # narrow: no pane in the presenter window
                fr = au.frame_locator('#stage > iframe.stage-pane'); fr.locator('#passage').wait_for()
                long = 'Softmax turns a list of scores into weights that are above 0 and add to 1. ' * 14
                au.evaluate("(t) => { const w = document.querySelector('#stage > iframe.stage-pane').contentWindow; w.document.querySelector('#passage .md').textContent = t; w.abhyasaTalkPage.fit(); }", long)
                last = au.evaluate("document.querySelector('#stage > iframe.stage-pane').contentWindow.abhyasaTalkPage.pages") - 1
                assert 0 < last < 19
                pr.wait_for_timeout(1500)   # the audience window reports the count
                press_d = lambda k: [(pr.keyboard.press('d'), pr.wait_for_timeout(120)) for _ in range(k)]
                press_d(last + 4)
                pr.wait_for_timeout(300)
                assert side() == last, (side(), last)
                # a bad count is ignored: with the audience reports stopped, it must leave the real count as it was (a bad one would move the last page)
                au.evaluate("window.__quiet = true")
                for _ in range(last): pr.keyboard.press('a'); pr.wait_for_timeout(120)
                pr.wait_for_timeout(300); assert side() == 0
                for bad in (dict(n=-5), dict(n=0), dict(n=21), dict(n=1.5), dict(n='3'), dict(n=3, x=1)):   # the channel checks the message
                    pr.evaluate("([ch, m]) => { const b = new BroadcastChannel('abhyasa-stage:' + ch); b.postMessage({v: 1, t: 'pages', ...m}); b.close(); }", [f"{tid}:{run['key']}", bad])
                pr.wait_for_timeout(200)
                press_d(last + 4)
                pr.wait_for_timeout(300)
                assert side() == last, (side(), last)
                assert not errs, errs
            finally: b.close()
    finally: srv.should_exit = True

def test_tall_demo_keeps_14px_and_the_room_follows_the_scroll(mk, talk_fake, lr):
    "A demo that shows alone and is too tall keeps 14 px text in a taller box (`.tall`) that scrolls; the audience window follows the presenter's scroll (`demoscroll`) and ignores a bad one."
    pw = pytest.importorskip('playwright.sync_api')
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr)))
    cl.post(f'/t/{tid}/start'); run = lr.run(lr.talk(tid).live)
    srv, base = serve(cl)
    DEMO = "document.querySelector('section[data-sid=s3] [data-rupaka]')"
    info = f"(h => ({{tall: h.parentElement.classList.contains('tall'), alone: h.closest('section').classList.contains('demo-alone'), text: +h.style.zoom * parseFloat(getComputedStyle(h).fontSize)}}))({DEMO})"
    frac = f"(d => d.scrollTop / Math.max(1, d.scrollHeight - d.clientHeight))({DEMO}.parentElement)"
    try:
        with pw.sync_playwright() as p:
            if not Path(p.chromium.executable_path).exists(): pytest.skip("Playwright's Chromium is not installed")
            b = p.chromium.launch(headless=True)
            try:
                c = b.new_context(viewport=dict(width=1000, height=800), reduced_motion='reduce')
                errs = []
                pr = c.new_page(); pr.on('pageerror', lambda e: errs.append(str(e)))
                pr.goto(f'{base}/t/{tid}/present'); pr.wait_for_load_state('networkidle')
                au = c.new_page(); au.on('pageerror', lambda e: errs.append(str(e)))
                au.set_viewport_size(dict(width=1000, height=562))
                au.goto(f'{base}/t/{tid}/audience?k={run["key"]}'); au.wait_for_load_state('networkidle')
                pr.wait_for_selector('#aud-live:not([hidden])'); pr.bring_to_front()
                pr.keyboard.press('g'); pr.keyboard.press('3'); au.wait_for_function("document.getElementById('stage').dataset.slide === 's3'")
                pr.keyboard.press('d'); au.wait_for_function(f"!!{DEMO}?.rupaka"); pr.wait_for_function(f"!!{DEMO}?.rupaka")
                for x in (pr, au): assert not x.evaluate(info)['tall']   # a demo that fits is not in a tall box
                for x in (pr, au): x.evaluate(f"{DEMO}.firstElementChild.style.paddingBottom = '700px'")
                for x in (pr, au):
                    x.wait_for_function(f"{DEMO}.parentElement.classList.contains('tall')", timeout=3000)
                    got = x.evaluate(info); assert got['alone'] and got['text'] >= 13.9, got
                    assert x.evaluate(f"{DEMO}.parentElement.scrollHeight > {DEMO}.parentElement.clientHeight")
                pr.evaluate(f"(d => {{ d.scrollTop = (d.scrollHeight - d.clientHeight) / 2; }})({DEMO}.parentElement)")
                au.wait_for_function(f"Math.abs({frac} - .5) < .02", timeout=3000)
                for bad in (2, -1, 'x'):   # the channel checks the message: the audience box stays where it is
                    pr.evaluate("([ch, y]) => { const b = new BroadcastChannel('abhyasa-stage:' + ch); b.postMessage({v: 1, t: 'demoscroll', y}); b.close(); }", [f"{tid}:{run['key']}", bad])
                au.wait_for_timeout(300); assert abs(au.evaluate(frac) - .5) < .02
                pr.evaluate("([ch]) => { const b = new BroadcastChannel('abhyasa-stage:' + ch); b.postMessage({v: 1, t: 'demoscroll', y: 1}); b.close(); }", [f"{tid}:{run['key']}"])
                au.wait_for_function(f"{frac} > .98", timeout=3000)
                assert not errs, errs
            finally: b.close()
    finally: srv.should_exit = True

def test_edit_a_run_question(mk, talk_fake, lr):
    "A run question (\"What does this print?\") takes 2 to 6 options or none, never has an answer, and keeps its options in the order that you wrote."
    from abhyasa.blocks.talk.ui import KINDS
    assert KINDS['run'] == 'What does this print?'
    cl, tid = talk_of(mk, lr)
    post = lambda **kw: cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='edit', **kw))
    ask = lambda: lr.talk(tid).slides[0]['ask']
    assert post(kind='run', q='What does it print?', options='1\n2').status_code == 200                      # two options are enough
    assert ask() == dict(kind='run', q='What does it print?', options=['1', '2'])
    assert post(kind='run', q='What does it print?', options='a\nb\nc\nd', answer='1').status_code == 200   # more options: not mixed, no answer
    assert ask() == dict(kind='run', q='What does it print?', options=['a', 'b', 'c', 'd'])
    assert post(kind='run', q='What does it print?', options='').status_code == 200 and 'options' not in ask()    # free words
    assert post(kind='run', q='What does it print?', options='only one').status_code == 400
    assert post(kind='run', q='What does it print?', options='1\n2\n3\n4\n5\n6\n7').status_code == 400
    assert lr.talk(tid).slides[0]['ask']['kind'] == 'run'

def walk_started(cl, lr):
    "A walk that is started, with a check on each idea; return its id."
    jid = prep_walk(lr, walk(cl, lr)); cl.post(f'/w/{jid}/start'); return jid

def test_present_on_a_started_walk(mk, talk_fake, lr):
    "A started walk goes straight to its step: that page has Present this walk, but no new main button."
    cl = mk(); jid = walk_started(cl, lr)
    page = cl.get(f'/w/{jid}').text   # the client follows the redirect to the current step
    assert 'Present this walk' in page and 'Open the talk' not in page
    p1 = cl.get(f'/w/{jid}/1').text
    assert p1.count('Present this walk') == 1 and 'class="quiet small"' in p1   # a quiet button, not a main one
    assert f'value="{jid}"' in p1

def test_present_on_the_end_of_a_walk(mk, talk_fake, lr):
    "The last page of a walk has Present this walk; Back to Today stays the one main button."
    cl = mk(); jid = walk_started(cl, lr)
    for i in range(3): cl.post(f'/w/{jid}/{i}/next')
    page = cl.get(f'/w/{jid}/2/done').text
    assert 'You finished the walk' in page and 'Present this walk' in page and 'Back to Today' in page
    assert page.count('Present this walk') == 1

def test_present_in_the_journeys_list(mk, talk_fake, lr):
    "A walk and a plain journey each have a quiet Present on their row in Learn; the journey row makes its talk from the journey."
    cl = mk(); jid = walk_started(cl, lr); plain = journey_of(lr)
    page = cl.get('/learn').text
    assert page.count('>Present</button>') == 2 and 'Present this walk' not in page and page.count('hx-post="/talk/journey"') == 1
    assert plain in page

def test_a_walk_with_a_talk_opens_it(mk, talk_fake, lr):
    "After a talk exists for the walk: its step page and its last page show Open the talk and Make it again. Its row in Learn shows Open the talk only."
    cl = mk(); jid = walk_started(cl, lr); tid = make_talk(cl, jid)
    for i in range(3): cl.post(f'/w/{jid}/{i}/next')
    for u in (f'/w/{jid}/1', f'/w/{jid}/2/done'):
        page = cl.get(u).text
        assert 'Open the talk' in page and f'href="/t/{tid}"' in page and 'Make it again' in page and 'Present this walk' not in page, u
    row = cl.get('/learn').text.split('class="jrow lrow"')[1]
    assert f'<a href="/t/{tid}" class="quiet">Open the talk</a>' in row and 'Make it again' not in row

def test_no_present_on_a_side_walk_or_a_talk_walk(mk, talk_fake, lr):
    "A side walk (`depth`) and a walk made for a talk (`for_talk`) have no Present on their step page, last page or Learn row."
    cl = mk(); jid = walk_started(cl, lr); j = lr.journey(jid)
    side = lr.put_journey({**j, 'id': 'side-walk-ab12', 'title': 'Side walk', 'depth': 1, 'parent': dict(walk=jid, step=0)}).id
    talk = lr.put_journey({**j, 'id': 'talk-walk-ab12', 'title': 'Talk walk', 'parent': dict(**{'for': 'talk'})}).id
    for w in (side, talk):
        assert 'Present this walk' not in cl.get(f'/w/{w}/1').text and 'Present this walk' not in cl.get(f'/w/{w}/2/done').text
    assert cl.get('/learn').text.count('>Present</button>') == 1   # the walk of `jid` only

# --- maths in a slide, and the words question ---------------------------------------------------------------------

TEX = r'$1/\sqrt{d_k}$'
MATH = r'<span class="math inline">1/\sqrt{d_k}</span>'

def maths_talk(cl, lr):
    "A started talk whose first slide has maths in its title, section, points, notes, question and options; return (tid, run)."
    tid, _ = started(cl, lr); t = dict(lr.talk(tid))
    s = t['slides'][0]
    s.update(title=f'Why scale by {TEX}', section=f'Scale by {TEX}', notes=f'Say why we divide by {TEX}.', beats=['body', *s.get('beats', [])])
    s['show'] = dict(s['show'], body=[f'We divide the scores by {TEX}.', 'Large scores make softmax flat.'])
    s['ask'] = dict(s['ask'], q=f'Why divide by {TEX}?', options=[f'To keep {TEX} small', 'To add noise', 'To sort', 'To skip'])
    t['slides'][1]['title'] = f'Softmax over {TEX}'
    lr.put_talk(t); cl.post(f'/t/{tid}/end'); cl.post(f'/t/{tid}/start')
    return tid, lr.run(lr.talk(tid).live)

def test_slide_maths_is_drawn(mk, talk_fake, lr):
    "The title, the section, the points, the notes, the question, the options and the Next row of a slide have maths spans, not raw TeX."
    cl = mk(); tid, run = maths_talk(cl, lr)
    p, a = cl.get(f'/t/{tid}/present').text, cl.get(f'/t/{tid}/audience?k={run["key"]}').text
    for page in (p, a):
        assert f'Why scale by {MATH}' in page and f'Scale by {MATH}' in page
        assert f'We divide the scores by {MATH}.' in page and f'scores by {TEX}' not in page
        assert f'<h1>Why scale by {TEX}' not in page and f'Scale by {TEX}</p>' not in page
    assert f'Why divide by {MATH}?' in p and f'To keep {MATH} small' in p and f'Say why we divide by {MATH}.' in p
    assert f'Why divide by {TEX}?</p>' not in p and f'To keep {TEX} small</li>' not in p
    nxt = p[p.index('id="next"'):]; nxt = nxt[:nxt.index('</div>\n', nxt.index('next-row'))]
    assert f'Softmax over {MATH}' in nxt and f'Softmax over {TEX}' not in nxt   # the Next row
    assert f'Why divide by {MATH}?' in cl.get(f'/t/{tid}').text   # the Ask the room cell of the editor

def test_slide_text_is_safe(mk, talk_fake, lr):
    "A title or a question with HTML in it shows no script on the presenter or the audience page."
    cl = mk(); tid, _ = started(cl, lr); t = dict(lr.talk(tid)); s = t['slides'][0]
    s.update(title='Why <script>alert(1)</script> $x$', section='<img src=x onerror=alert(1)>')
    s['ask'] = dict(s['ask'], q='<iframe src="https://evil.example"></iframe> $y$?')
    lr.put_talk(t); cl.post(f'/t/{tid}/end'); cl.post(f'/t/{tid}/start'); run = lr.run(lr.talk(tid).live)
    for page in (cl.get(f'/t/{tid}/present').text, cl.get(f'/t/{tid}/audience?k={run["key"]}').text):
        assert '<script>alert' not in page and '<img src=x' not in page and '<img src="x"' not in page and '<iframe' not in page
        assert '<span class="math inline">x</span>' in page   # the maths still draws

def test_words_question_reads_well():
    "The words question names the idea as a question when the name is a question, and asks what it is when the name is a noun phrase."
    from abhyasa.talk import words_q
    assert words_q(f'Why scale by {TEX}') == f'Say in one or two sentences: Why scale by {TEX}?'
    assert words_q('How does attention work?') == 'Say in one or two sentences: How does attention work?'
    assert words_q('Softmax') == 'Say in one or two sentences: what is "Softmax"?'
    # the case of a name never changes, and only a title-case question word followed by more words makes a question
    assert words_q('CAN bus') == 'Say in one or two sentences: what is "CAN bus"?'
    assert words_q('WHO growth charts') == 'Say in one or two sentences: what is "WHO growth charts"?'
    assert words_q('Bayes?') == 'Say in one or two sentences: Bayes?'
    assert words_q('Which') == 'Say in one or two sentences: what is "Which"?' and words_q('') is None

def test_a_failed_choice_gives_a_good_words_question(lr):
    "When the model gives no choice question, the words question reads well for a name that is a question."
    from abhyasa.talk import ask_from_check
    from abhyasa.llm import Fake
    lr.put(f'Why scale by {TEX}', 'Divide the scores by the root of dk.', 'ml')
    slug = next(c.slug for c in lr.concepts() if c.name.startswith('Why scale'))
    a = ask_from_check(lr, Fake({}, dflt='not JSON'), slug)
    assert a['kind'] == 'words' and a['q'] == f'Say in one or two sentences: Why scale by {TEX}?'

def test_the_slide_model_writes_the_words_question(lr):
    "A slide with the fallback words question takes the question that the slide model writes; a question that you wrote stays."
    from abhyasa.talk import fill_slide, words_q
    from abhyasa.llm import Fake
    from talk_data import SLIDE
    ask = Fake({'You write one slide of a talk': SLIDE})
    s = dict(id='s1', kind='idea', concept='ranking', title='Ranking', show=dict(passage='Order items by a score.'), beats=['passage'], notes='',
             ask=dict(kind='words', q=words_q('Ranking'), most=80, src=dict(check='code')))
    assert fill_slide(lr, ask, s)['ask'] == dict(kind='words', q=SLIDE['ask'], most=80, src=dict(check='code'))
    mine = dict(s, ask=dict(s['ask'], q='Say how you rank two lists.'))
    assert fill_slide(lr, ask, mine)['ask']['q'] == 'Say how you rank two lists.'

def test_an_old_words_question_gets_new_words(lr):
    "A slide with a passage and a note needs no model call, but its old words question gets the words of words_q; your own question stays."
    from abhyasa.talk import fill_slide, old_words_q
    from abhyasa.llm import Fake
    none = Fake({})
    s = dict(id='s6', kind='idea', concept='nope', title=f'Why scale by {TEX}', show=dict(passage='We scale the dot products.'), beats=['passage'],
             notes='Say why.', ask=dict(kind='words', q=old_words_q(f'Why scale by {TEX}'), most=80))
    assert fill_slide(lr, none, s)['ask']['q'] == f'Say in one or two sentences: Why scale by {TEX}?' and none.calls == []
    mine = dict(s, ask=dict(s['ask'], q='Say why we divide.'))
    assert fill_slide(lr, none, mine) is mine

def test_a_short_cut_keeps_the_maths_whole():
    "The small picture of a slide cuts its text at a space, but never inside a pair of maths."
    from abhyasa.blocks.talk.ui import short
    assert short(f'We divide the scores by {TEX} here', 30) == 'We divide the scores by…'
    assert short(f'{TEX} and more words after it', 5) == f'{TEX}…'
    assert short(r'A long line with $$x + y$$ in it', 22) == 'A long line with…' and short('Plain words here', 10) == 'Plain…'

def test_the_foot_draws_the_maths_of_the_talk_title(mk, talk_fake, lr):
    "The foot of each slide shows the title of the talk with its maths drawn."
    cl = mk(); tid, _ = started(cl, lr); t = dict(lr.talk(tid)); t['title'] = f'Scaling by {TEX}'
    lr.put_talk(t)
    p = cl.get(f'/t/{tid}/present').text
    assert f'Scaling by {MATH}' in p and f'<span>Scaling by {TEX}</span>' not in p
