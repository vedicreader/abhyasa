"The detour block: the needs line, the offer, the side walk beside the step, and the way back to the same place."
from walk_data import *
from pathlib import Path
import pytest
from abhyasa.core.keys import KEYS

def needs_gradients(lr):
    lr.put('Derivatives and gradients', 'The slope of a function at a point, one for each input.', 'ml', slug='gradients')
    lr.update('scaling-by-the-root-of-dk', prereqs=['softmax', 'gradients'])

def test_needs_line_and_side_walk_beside(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    page = cl.get(f'/w/{jid}/2').text
    assert 'This needs' in page and 'not learned yet' in page and '⌥B' in page
    r = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()
    sid = r['url'].split('/')[2]
    assert lr.journey(sid).parent == dict(walk=jid, step=2, idea=lr.journey(jid).steps[2]['slug']) and r['title'].startswith('Derivatives')
    pane = cl.get(r['url'] + '?pane=1').text
    from abhyasa.core import short_title
    back = short_title(lr.journey(jid).title)
    assert '<nav' not in pane and f'Back to {back}: idea 3 of 3' in pane and '⌥Z' in pane   # it names the walk that opened it
    side = cl.get(f'/w/{sid}').text
    assert f'Back to {back}' in side and f'the basics, for {back}' in side and 'enough to read' not in side   # the short lead
    assert f'src="/w/{sid}/0?pane=1"' in cl.get(f'/w/{jid}/2?rh=/w/{sid}/0').text        # a reload keeps the pane open
    for bad in ('https://evil.example/', '//evil.example/', '/\\evil.example/'):
        assert 'rh-pane' not in cl.get(f'/w/{jid}/2', params=dict(rh=bad)).text         # no pane for a URL off the app
    today = cl.get('/').text   # the side walk shows under its walk in Your journeys, with no line of its own
    assert 'Unfinished side walk' not in today and 'class="side-walks"' in today and 'Derivatives' in today

def test_side_walk_logs_from_and_comes_back(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    sid = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url'].split('/')[2]
    cl.get(f'/w/{sid}/0/check'); cl.post(f'/w/{sid}/0/answer', data=dict(answer='the slope', confidence=70))
    assert lr.attempts('gradients', limit=1)[0]['from'] == f'{jid}/2'
    r = cl.post(f'/rh/back/{sid}', follow_redirects=False)
    assert r.headers['location'] == f'/w/{jid}/2'
    page = cl.get(f'/w/{jid}/2').text
    assert 'Back on the paper' in page and 'on the way' in page
    assert sid not in cl.get('/').text.split('class="side-walks"')[0]                    # listed under its parent only
    s2 = cl.get('/start?focus=gradients', follow_redirects=False).headers['location'].split('/')[-1]
    cl.get(f'/s/{s2}')
    walk_fake.rules['You grade one answer'] = dict(correct=True, grade=9, first_error='', misconception='', feedback='Yes.')   # lesson_extra shows at a close
    assert 'You first met this on the way to' in cl.post(f'/s/{s2}/answer', data=dict(answer='slope')).text

def test_a_miss_that_names_a_gap_offers_it(mk, walk_fake, lr):
    walk_fake.rules['You grade one answer'] = dict(correct=False, grade=2, first_error='No slope.', misconception='',
                                                   feedback='Think of the slope.', gaps=['gradients'])
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    lr.walk_step(jid, 2, check=dict(way='words', kind='short', depth=2, why=''))
    cl.get(f'/w/{jid}/2/check')
    r = cl.post(f'/w/{jid}/2/answer', data=dict(answer='it is faster', confidence=70)).text
    assert 'Your answer shows a gap' in r and 'Learn this gap' in r and '⌥B' in r and 'Your place here stays' in r and 'data-add' not in r

def test_a_gap_that_is_not_on_the_shelf_is_added_on_the_click(mk, walk_fake, lr):
    "When the tutor could not add the gap at the answer, the gap line names it as said, and its button adds it (data-add) before the chooser opens."
    cl, jid = _gap_page(mk, walk_fake, lr, 'vertical movement of the line')
    cl.get(f'/w/{jid}/2/check')
    r = cl.post(f'/w/{jid}/2/answer', data=dict(answer='it is faster', confidence=70)).text
    assert not lr.concept('vertical-movement-of-a-line') and 'data-t="vertical movement of the line" data-add="1"' in r
    walk_fake.fail = False
    t = cl.post('/rh/term', data=dict(t='vertical movement of the line', at=f'{jid}/2')).text
    assert 'A quick look' in t and 'vertical-movement-of-a-line' in lr.concept('scaling-by-the-root-of-dk').gaps

def test_term_offer_and_depth_limit(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    t = cl.get('/rh/term', params=dict(t='gradients', at=f'{jid}/2')).text
    assert 'A quick look' in t and 'A side walk' in t and 'Its own course' in t
    a = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url'].split('/')[2]
    b = cl.post('/rh/open', data=dict(slug='softmax', at=f'{a}/0', how='primer')).json()['url'].split('/')[2]
    r = cl.post('/rh/open', data=dict(slug='softmax', at=f'{b}/0', how='primer')).json()
    assert r['how'] == 'course' and r['url'].startswith('/course/')                      # past the limit: only its own course
    t = cl.get('/rh/term', params=dict(t='softmax', at=f'{b}/0')).text
    assert 'Its own course' in t and 'A quick look' not in t                              # at the limit, the chooser has one choice

def test_a_concept_does_not_say_learn_it_first_on_its_own_page(mk, walk_fake, lr):
    "On the page or the step of an idea, its chooser says Pick a way to learn it, not Learn it first. On another step, the idea is one to learn first."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    c = lr.concept('gradients')
    for at in ('/c/gradients', *(f'{jid}/{k}' for k, s in enumerate(lr.journey(jid).steps) if s['slug'] == 'gradients')):
        t = cl.get('/rh/term', params=dict(t='gradients', at=at)).text
        assert f'Pick a way to learn {c.name}' in t and f'Learn {c.name} first' not in t, at
    t = cl.get('/rh/term', params=dict(t='gradients', at=f'{jid}/2')).text
    assert f'Learn {c.name} first' in t

def test_open_and_back_refuse_bad_input(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    n = len(lr.journeys())
    for d, code in [(dict(slug='gradients', at=f'{jid}/2', how='drop'), 400),     # only primer, walk or course
                    (dict(slug='gradients', at=f'{jid}/2', how='session'), 400),  # the old third way is gone: its own course took its place
                    (dict(slug='gradients', at='/c/nope', how='primer'), 404),     # no such concept page
                    (dict(slug='gradients', at='//evil.example/c/x', how='primer'), 400),
                    (dict(slug='gradients', at=f'{jid}/9', how='primer'), 404),     # no such step
                    (dict(slug='gradients', at=jid, how='primer'), 400),            # no step at all
                    (dict(slug='gradients', at=f'{jid}/x', how='primer'), 400),
                    (dict(slug='gradients', at='nope/0', how='primer'), 404),
                    (dict(slug='nope', at=f'{jid}/2', how='primer'), 404)]:
        assert cl.post('/rh/open', data=d).status_code == code, d
    assert len(lr.journeys()) == n                                                        # nothing was made
    for at in (f'{jid}/9', jid, 'nope/0', f'{jid}/-1'): assert cl.get('/rh/term', params=dict(t='gradients', at=at)).status_code in (400, 404), at
    assert cl.post('/rh/back/nope').status_code == 404 and cl.post(f'/rh/back/{jid}').status_code == 404   # a walk with no parent

def test_term_lookup_on_get_writes_nothing(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    n = len(lr.concepts())
    t = cl.get('/rh/term', params=dict(t='layer norm', at=f'{jid}/2')).text
    assert len(lr.concepts()) == n and 'not in your concepts' in t                          # a GET only finds; a POST adds it
    walk_fake.rules['The idea: layer norm'] = dict(name='Layer norm', statement='Scale each vector to mean 0 and variance 1.')
    t = cl.post('/rh/term', data=dict(t='layer norm', at=f'{jid}/2')).text
    assert 'A quick look' in t and lr.concept('layer-norm') and 'layer-norm' in lr.concept('scaling-by-the-root-of-dk').gaps

def test_walk_end_sends_done_and_the_key_is_listed(mk, walk_fake, lr):
    walk_fake.rules['You grade one answer'] = dict(correct=True, grade=9, first_error='', misconception='', feedback='Yes.')
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    sid = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url'].split('/')[2]
    cl.get(f'/w/{sid}/0/check'); cl.post(f'/w/{sid}/0/answer', data=dict(answer='the slope', confidence=90))
    end = cl.post(f'/w/{sid}/0/next', params=dict(pane=1)).text
    assert 'data-rh-done' in end and 'on the way' in end
    cl.post(f'/rh/back/{sid}')
    assert 'learned on the way today' in cl.get(f'/w/{jid}/2').text
    assert ('Walk', '⌥B', 'Learn a missing idea in a side walk') in KEYS

def test_leave_early_then_finish_updates_the_result(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    sid = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url'].split('/')[2]
    cl.post(f'/rh/back/{sid}')                                                            # ⌥Z before the side check
    assert 'looked at' in cl.get(f'/w/{jid}/2').text
    walk_fake.rules['You grade one answer'] = dict(correct=True, grade=9, first_error='', misconception='', feedback='Yes.')
    cl.get(f'/w/{sid}/0/check'); cl.post(f'/w/{sid}/0/answer', data=dict(answer='the slope', confidence=90))
    cl.post(f'/rh/back/{sid}')                                                            # finish it later, then come back again
    page = cl.get(f'/w/{jid}/2').text
    assert 'learned on the way today' in page and 'looked at' not in page                 # the needs line and the strip show the finish
    assert len(lr.journey(jid).steps[2]['detours']) == 1

def _chromium():
    "True when Playwright's bundled Chromium is installed."
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p: return Path(p.chromium.executable_path).exists()
    except Exception: return False

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_side_walk_beside_the_step_in_a_browser(mk, walk_fake, lr):
    import socket, threading, time, uvicorn
    from playwright.sync_api import sync_playwright
    walk_fake.rules['You grade one answer'] = dict(correct=True, grade=9, first_error='', misconception='', feedback='Yes.')
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    lr.walk_step(jid, 2, check=dict(way='words', kind='short', depth=2, why='')); lr.update('softmax', floor=3)
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    draft = 'Big dot products make softmax put all the weight on one key'
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page(viewport=dict(width=1400, height=900))
                pg.goto(f'http://127.0.0.1:{port}/w/{jid}/2'); pg.wait_for_selector('#check #ans')
                pg.fill('#check #ans', draft)
                pg.locator('h1.idea').click(); pg.keyboard.press('Alt+b')                 # the offer for the first unmet need
                pg.wait_for_selector('#rh-offer .rh-way')
                pg.keyboard.press('1')                                                    # a quick primer, beside the page
                pg.wait_for_function("() => document.documentElement.classList.contains('rh-open')")
                assert 'Held while you learn' in pg.locator('#check').inner_text()
                fr = pg.frame_locator('#rh-pane iframe')
                pane = pg.locator('#rh-pane iframe').element_handle().content_frame()
                pane.wait_for_function("() => document.activeElement?.id === 'ans'")             # the card is in place and ready
                fr.locator('#check #ans').fill('The slope at one point')
                fr.locator('#check #ans').press('Control+Enter')                          # answer the side check
                fr.locator('#check .check.shut').wait_for()                                # graded and closed
                fr.locator('#check .check.shut .go').press('Alt+z')                                   # back to the paper
                pg.wait_for_function("() => !document.documentElement.classList.contains('rh-open')")
                pg.wait_for_function("() => document.querySelector('.rh-needs')?.textContent.includes('learned on the way today')")
                assert pg.input_value('#check #ans') == draft                             # the draft is still in the answer box
                assert 'Back on the paper' in pg.locator('.rh-needs').inner_text()
                assert lr.journey(jid).steps[2]['detours'][0]['outcome'] in ('solid', 'fragile')
            finally: b.close()
    finally: srv.should_exit = True; th.join(5)

def test_a_failed_side_walk_or_term_shows_a_plain_line_and_logs_the_error(mk, walk_fake, lr, monkeypatch, caplog):
    "The page never shows the words of a library. The log keeps them."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    def boom(*a, **k): raise RuntimeError('litellm.APIError: 500 from upstream')
    monkeypatch.setattr('abhyasa.blocks.detour.app.detour', boom); monkeypatch.setattr('abhyasa.blocks.detour.app.look_up', boom)
    with caplog.at_level('WARNING'):
        r = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer'))
        t = cl.post('/rh/term', data=dict(t='entropy', at=f'{jid}/2'))
    assert r.status_code == 502 and 'Try again' in r.text and 'litellm' not in r.text and 'upstream' not in r.text
    assert 'req-err' in t.text and 'Try again' in t.text and 'litellm' not in t.text
    assert caplog.text.count('litellm.APIError') >= 2

def test_parent_step_is_the_one_check_for_the_parent(mk, walk_fake, lr):
    "`parent_step` gives the parent walk and step of a side walk while they are there, else (None, None)."
    from abhyasa.path import parent_step
    cl = mk(); jid = walk(cl, lr); pj = lr.journey(jid)
    side = lambda p: dict(id='side', title='Side', mode='walk', depth=1, steps=[], parent=p)
    assert parent_step(lr, side(dict(walk=jid, step=2))) == (pj, 2)
    for p in (dict(walk=jid, step=len(pj.steps)), dict(walk=jid, step=-1), dict(walk=jid, step='2'), dict(walk='gone', step=0), dict(step=0), None):
        assert parent_step(lr, side(p)) == (None, None), p
    assert parent_step(lr, None) == (None, None)

def test_history_continue_does_not_open_a_gone_parent_step(mk, walk_fake, lr):
    "A side walk whose parent step was dropped: Your learning shows the side walk itself, not a step that is not there."
    cl = mk(); jid = walk(cl, lr); pj = lr.journey(jid)
    lr.put_journey(dict(id='side-1', title='Side walk on softmax', mode='walk', depth=1, steps=[dict(slug='softmax', check=dict(kind='short'))],
                        parent=dict(walk=jid, step=len(pj.steps) + 3)))
    lr.log_session('s-side', '0 of 1 passed.', start=1., updated=1., journey='side-1', log=[], open=dict(id='q'))
    page = cl.get('/learning').text
    assert f'/w/{jid}/{len(pj.steps) + 3}' not in page

def test_a_side_walk_row_opens_beside_its_parent_step(mk, walk_fake, lr):
    "On Home, a side walk opens in the pane beside the step that opened it. With no parent step, it opens its own page."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    sid = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url'].split('/')[2]
    side = cl.get('/').text.split('class="side-walks"')[1]
    assert f'href="/w/{jid}/2?rh=/w/{sid}/0"' in side, side[:400]
    assert f'src="/w/{sid}/0?pane=1"' in cl.get(f'/w/{jid}/2?rh=/w/{sid}/0').text
    j = lr.journey(sid); lr.put_journey({**j, 'parent': dict(walk=jid, step=99), 'depth': 1})
    assert f'href="/w/{sid}"' in cl.get('/').text                                  # the parent step is gone: its own page

def _gap_page(mk, walk_fake, lr, gap):
    "A started walk whose step 3 has a short check, and an answer that the grader marks as a miss with gap `gap`. The lesson is long, so the gap line is far below the title."
    walk_fake.rules['You grade one answer'] = dict(correct=False, grade=2, first_error='No slope.', misconception='', feedback='Think of the slope.', gaps=[gap])
    walk_fake.rules['Teach the smallest step'] = '\n\n'.join(['Draw the line through two points, then look at where it crosses the axes.'] * 12)
    walk_fake.fail = True   # while it is set, the tutor cannot add the gap: the try at the answer fails, so the card names the gap as said
    walk_fake.rules['The idea: vertical movement of the line'] = lambda p, sp: {} if walk_fake.fail else dict(
        name='Vertical movement of a line', statement='A change of the bias moves the line up or down.', size=0)
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    lr.walk_step(jid, 2, check=dict(way='words', kind='short', depth=2, why=''))
    return cl, jid

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
@pytest.mark.parametrize('gap,how', [('gradients', 'click'), ('gradients', 'key'), ('vertical movement of the line', 'click')])
def test_learn_this_gap_opens_the_chooser_under_the_gap_line(mk, walk_fake, lr, gap, how):
    """After a miss and a lesson, Learn this gap (a click, or ⌥B after the card swapped in) opens the chooser under the gap line, in view,
    with the tutor's pick first and in focus. A gap that is not in your concepts yet is added first (a POST), then the chooser opens."""
    import socket, threading, time, uvicorn
    from playwright.sync_api import sync_playwright
    cl, jid = _gap_page(mk, walk_fake, lr, gap)
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True, args=['--mute-audio'])
            try:
                pg = b.new_page(viewport=dict(width=1200, height=800), reduced_motion='reduce')
                errs, reqs = [], []
                pg.on('pageerror', lambda e: errs.append(str(e)))
                pg.on('request', lambda r: reqs.append((r.method, r.url.split('?')[0].split(str(port))[1])))
                pg.goto(f'http://127.0.0.1:{port}/w/{jid}/2'); pg.wait_for_selector('#check #ans')
                pg.fill('#check #ans', 'it is faster'); pg.locator('#check #ans').press('Control+Enter')
                pg.wait_for_selector('#check .rh-gapline .rh-gap')
                pg.locator('#idk').click(); pg.wait_for_selector('#check .go-on')                       # Teach me: the lesson swaps the card in again
                g = pg.locator('#check .rh-gapline .rh-gap')
                g.scroll_into_view_if_needed(); n = len(reqs); walk_fake.fail = False
                if how == 'click': g.click()
                else: pg.evaluate("document.activeElement.blur()"); pg.keyboard.press('Alt+b')
                pg.wait_for_selector('#check .rh-gapline + #rh-offer .rh-offer-card .rh-way.pick')
                assert reqs[n:][0] == (('POST' if ' ' in gap else 'GET'), '/rh/term'), reqs[n:]
                assert pg.locator('.rh-needs #rh-offer').count() == 0 and pg.locator('#rh-offer').count() == 1   # one box, under the gap line
                assert pg.evaluate("(() => { const r = document.querySelector('#rh-offer .rh-way.pick').getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; })()")
                pg.wait_for_function("() => document.activeElement?.matches('.rh-way.pick')")             # Next idea does not take the focus back
                assert [w.get_attribute('data-how') for w in pg.locator('#rh-offer .rh-way').all()] == ['primer', 'walk', 'course']
                if ' ' in gap: assert lr.concept('vertical-movement-of-a-line') and 'vertical-movement-of-a-line' in lr.concept('scaling-by-the-root-of-dk').gaps
                pg.keyboard.press('Escape'); assert pg.locator('#rh-offer .rh-offer-card').count() == 0
                assert not errs, errs
            finally: b.close()
    finally: srv.should_exit = True; th.join(5)

def test_needs_line_counts_the_walk(mk, walk_fake, lr):
    "Step 1 is done in this walk and step 3 needs it: the line says done at idea 1, with no Learn it. Closed shaky, it says review it."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    j = lr.journey(jid); first, third = j.steps[0]['slug'], j.steps[2]['slug']
    lr.update(third, prereqs=[first]); lr.update(first, floor=2)   # a check at depth 2 leaves the floor under the depth of a ready need
    assert 'not learned yet' in cl.get(f'/w/{jid}/2').text
    lr.walk_step(jid, 0, done=dict(outcome='solid', at=1.))
    line = cl.get(f'/w/{jid}/2').text.split('class="rh-line"')[1].split('rh-offer')[0]
    assert 'done at idea 1' in line and 'not learned yet' not in line and 'Learn it' not in line, line
    lr.walk_step(jid, 0, done=dict(outcome='fragile', at=1.))
    line = cl.get(f'/w/{jid}/2').text.split('class="rh-line"')[1].split('rh-offer')[0]
    assert 'shaky: review it' in line and f'href="/w/{jid}/0"' in line and 'Learn it' not in line, line

def side_of_four(cl, lr):
    "A started paper walk whose step 3 opened a side walk of 4 ideas on gradients; the first 3 are done."
    jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    for n in ('Slope', 'Rate of change', 'Partial derivative'): lr.put(n, f'{n} is one idea about change.', 'ml')
    slugs = ['slope', 'rate-of-change', 'partial-derivative', 'gradients']
    lr.put_journey(dict(id='side4', title='Gradients', mode='walk', depth=1, slug='gradients', started=time.time(),
                        parent=dict(walk=jid, step=2, idea=lr.journey(jid).steps[2]['slug']),
                        steps=[dict(slug=s, status='todo', check=dict(way='words', kind='short', depth=2, why='')) for s in slugs]))
    for k in range(3): lr.walk_step('side4', k, done=dict(outcome='solid', at=time.time()))
    return jid

def test_last_idea_of_a_side_walk_goes_back_to_the_main_idea(mk, walk_fake, lr):
    "After the 4th check of a 4-idea side walk, the main button is Back to the main idea, not Next idea, and it lands on the main idea with what you learned."
    walk_fake.rules['You grade one answer'] = dict(correct=True, grade=9, first_error='', misconception='', feedback='Yes.')
    cl = mk(); jid = side_of_four(cl, lr)
    main = lr.concept(lr.journey(jid).steps[2]['slug']).name
    cl.get('/w/side4/3/check')
    card = cl.post('/w/side4/3/answer', data=dict(answer='the slope in each direction', confidence=90)).text
    assert f'Back to the main idea: {main}' in card and 'Next idea' not in card and 'data-act="back"' in card
    r = cl.post('/w/side4/3/next', follow_redirects=False)
    assert r.headers['location'] == f'/w/{jid}/2'
    page = cl.get(f'/w/{jid}/2').text
    assert 'Back on the paper' in page and 'on the way' in page and lr.journey(jid).steps[2]['detours'][0]['outcome'] == 'solid'
    assert 'data-rh-done' in cl.post('/w/side4/3/next', params=dict(pane=1)).text   # in the side pane: the end note, which closes the pane

def test_a_gap_learned_in_a_side_walk_has_a_tick(mk, walk_fake, lr):
    "A miss names a gap, a side walk on it ends well, then you come back: the gap line has a tick and no Learn it, and Try the check again opens a new check."
    walk_fake.rules['You grade one answer'] = dict(correct=False, grade=2, first_error='No slope.', misconception='', feedback='Think of the slope.', gaps=['gradients'])
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    lr.walk_step(jid, 2, check=dict(way='words', kind='short', depth=2, why=''))
    cl.get(f'/w/{jid}/2/check')
    cl.post(f'/w/{jid}/2/answer', data=dict(answer='it is faster', confidence=70))
    card = cl.post(f'/w/{jid}/2/giveup', data=dict(confidence=0)).text
    assert 'Your answer shows a gap' in card and 'Try the check again' not in card
    sid = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url'].split('/')[2]
    walk_fake.rules['You grade one answer'] = dict(correct=True, grade=9, first_error='', misconception='', feedback='Yes.')
    cl.get(f'/w/{sid}/0/check'); cl.post(f'/w/{sid}/0/answer', data=dict(answer='the slope', confidence=90))
    cl.post(f'/rh/back/{sid}')
    card = cl.get(f'/w/{jid}/2/check').text
    assert '✓' in card and 'learned in a side walk' in card and 'Your answer shows a gap' not in card and 'Learn this gap' not in card.split('rh-gaps')[1], card
    assert 'Next idea' in card and 'data-act="try-again"' in card and f'hx-post="/w/{jid}/2/again"' in card
    assert '✓' in cl.get(f'/w/{jid}/2').text.split('rh-strip')[1][:300]   # the strip of the return has the same tick
    old = lr.journey(jid).steps[2]['qid']
    again = cl.post(f'/w/{jid}/2/again').text
    s = lr.journey(jid).steps[2]
    assert s['done'] is None and s['qid'] and s['qid'] != old and 'id="send"' in again   # a fresh, open check
