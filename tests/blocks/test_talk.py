"The talk block: make a talk from a walk, change its slides, and find it again."
from talk_data import *
from abhyasa.settings import val
import pytest
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

def test_talks_on_your_learning_and_search(mk, talk_fake, lr):
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr)))
    page = cl.get('/learning').text
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
