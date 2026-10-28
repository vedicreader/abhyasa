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
    assert lr.journey(sid).parent == dict(walk=jid, step=2) and r['title'].startswith('Derivatives')
    pane = cl.get(r['url'] + '?pane=1').text
    assert '<nav' not in pane and 'Back to the paper: idea 3 of 3' in pane and '⌥Z' in pane
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
    assert sid not in cl.get('/journeys').text.split('Side walks')[0]                    # listed under its parent only
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
    assert 'Your answer points at' in r and '⌥B' in r

def test_term_offer_and_depth_limit(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    t = cl.get('/rh/term', params=dict(t='gradients', at=f'{jid}/2')).text
    assert 'A quick primer' in t and 'A short side walk' in t and 'Its own session' in t
    a = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url'].split('/')[2]
    b = cl.post('/rh/open', data=dict(slug='softmax', at=f'{a}/0', how='primer')).json()['url'].split('/')[2]
    r = cl.post('/rh/open', data=dict(slug='softmax', at=f'{b}/0', how='primer')).json()
    assert r['how'] == 'session'                                                          # past the limit: only its own session
    t = cl.get('/rh/term', params=dict(t='softmax', at=f'{b}/0')).text
    assert 'Its own session' in t and 'A quick primer' not in t                           # at the limit, the offer has one choice

def test_open_and_back_refuse_bad_input(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    n = len(lr.journeys())
    for d, code in [(dict(slug='gradients', at=f'{jid}/2', how='drop'), 400),     # only primer, walk or session
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
    assert len(lr.concepts()) == n and 'not on your shelf' in t                          # a GET only finds; a POST adds it
    walk_fake.rules['The idea: layer norm'] = dict(name='Layer norm', statement='Scale each vector to mean 0 and variance 1.')
    t = cl.post('/rh/term', data=dict(t='layer norm', at=f'{jid}/2')).text
    assert 'A quick primer' in t and lr.concept('layer-norm') and 'layer-norm' in lr.concept('scaling-by-the-root-of-dk').gaps

def test_walk_end_sends_done_and_the_key_is_listed(mk, walk_fake, lr):
    walk_fake.rules['You grade one answer'] = dict(correct=True, grade=9, first_error='', misconception='', feedback='Yes.')
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    sid = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url'].split('/')[2]
    cl.get(f'/w/{sid}/0/check'); cl.post(f'/w/{sid}/0/answer', data=dict(answer='the slope', confidence=90))
    end = cl.post(f'/w/{sid}/0/next', params=dict(pane=1)).text
    assert 'data-rh-done' in end and 'on the way' in end
    cl.post(f'/rh/back/{sid}')
    assert 'learned on the way today' in cl.get(f'/w/{jid}/2').text
    assert ('Walk', '⌥B', 'Learn beside: learn a missing idea in the side pane') in KEYS

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
    from abhyasa.journey import parent_step
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
