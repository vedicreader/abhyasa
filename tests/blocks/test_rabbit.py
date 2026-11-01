"""Rabbit holes: "I don't get X" at three depths (a quick look, a side walk, its own course), from the stuck row, the concept page
and a selected term; the tutor's pick by the size of the gap; the course that keeps its origin; and the pane beside the Explain panel."""
from walk_data import *
import re, socket, threading, time, uvicorn
import pytest
from test_detour import needs_gradients, _chromium
from test_course import follow, LEVEL

BIG = dict(name='Diffusion model', statement='A model that learns to undo noise, step by step, to make new pictures.', size=8)

def step(cl, lr):
    "A started walk on the paper: step 3 needs Softmax (learned) and gradients (not learned), with a short check."
    jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    lr.walk_step(jid, 2, check=dict(way='words', kind='short', depth=2, why='')); lr.update('softmax', floor=3)
    return jid

def pick(html):
    "The depths of the chooser in the order shown: the tutor's pick first."
    return re.findall(r'data-how="(\w+)"[^>]*class="rh-way', html)

def test_the_pick_comes_first_by_the_size_of_the_gap(mk, walk_fake, lr):
    "No gap: a quick look. A chain of two: a side walk. A big topic, by its size or by a long chain: its own course. Each has its reason."
    cl = mk(); jid = step(cl, lr); at = f'{jid}/2'
    t = cl.get('/rh/term', params=dict(t='gradients', at=at)).text
    assert pick(t) == ['primer', 'walk', 'course'] and 'needs no other idea' in t
    lr.put('Slope of a line', '', 'ml', slug='slope'); lr.update('gradients', prereqs=['slope'])
    assert pick(cl.get('/rh/term', params=dict(t='gradients', at=at)).text)[0] == 'walk'
    lr.update('gradients', size=8)
    t = cl.get('/rh/term', params=dict(t='gradients', at=at)).text
    assert pick(t) == ['course', 'primer', 'walk'] and 'a big topic: 8 ideas that you have not learned yet' in t
    lr.update('gradients', size=0)
    for k in range(5): lr.put(f'Part {k}', f'Part {k} of the slope.', 'ml', slug=f'p{k}', prereqs=[f'p{k + 1}'] if k < 4 else [])
    lr.update('slope', prereqs=['p0'])
    assert pick(cl.get('/rh/term', params=dict(t='gradients', at=at)).text)[0] == 'course'   # a chain longer than a side walk

def test_stuck_row_has_learn_it_and_opens_a_quick_look_and_a_side_walk(mk, walk_fake, lr):
    "The stuck row of the open check ends with Learn it for the first idea you did not learn. A quick look and a side walk open as side walks of the step."
    cl = mk(); jid = step(cl, lr)
    card = cl.get(f'/w/{jid}/2/check').text
    row = card.split('class="row acts"')[1]
    assert row.index('Teach me' if 'Teach me' in row else "I don't know") < row.index('rh-stuck') and 'data-t="gradients"' in row
    for how, n in (('primer', 1), ('walk', None)):
        r = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how=how)).json()
        sid = r['url'].split('/')[2]
        assert r['how'] == how and r['url'] == f'/w/{sid}/0' and lr.journey(sid).parent['walk'] == jid and lr.journey(sid).depth == 1
        if n: assert len(lr.journey(sid).steps) == n

def test_the_side_walk_end_reports_back_to_the_step(mk, walk_fake, lr):
    "The end of the side walk names what you learned; the way back keeps the outcome on the step, and the needs line says so."
    walk_fake.rules['You grade one answer'] = dict(correct=True, grade=9, first_error='', misconception='', feedback='Yes.')
    cl = mk(); jid = step(cl, lr)
    sid = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url'].split('/')[2]
    cl.get(f'/w/{sid}/0/check'); cl.post(f'/w/{sid}/0/answer', data=dict(answer='the slope', confidence=90))
    end = cl.post(f'/w/{sid}/0/next', params=dict(pane=1)).text
    assert 'data-rh-done' in end and 'You learned <b>Derivatives and gradients</b> on the way' in end
    assert cl.post(f'/rh/back/{sid}', follow_redirects=False).headers['location'] == f'/w/{jid}/2'
    assert lr.journey(jid).steps[2]['detours'][0]['outcome'] in ('solid', 'fragile')
    assert 'learned on the way today' in cl.get(f'/w/{jid}/2').text

def test_concept_page_offers_each_depth_and_comes_back(mk, walk_fake, lr):
    "On a concept page, I don't get this opens the chooser. The side walk goes back to the concept page; its own course names the page as its origin."
    walk_fake.rules['You grade one answer'] = dict(correct=True, grade=9, first_error='', misconception='', feedback='Yes.')
    cl = mk(); step(cl, lr)
    page = cl.get('/c/gradients').text
    assert 'rh-ask rh-page' in page and 't get this' in page and 'data-at="/c/gradients"' in page and 'detour.js' in page
    t = cl.get('/rh/term', params=dict(t='gradients', at='/c/gradients')).text
    assert pick(t) == ['primer', 'walk', 'course'] and 'Your place stays: this page.' in t
    r = cl.post('/rh/open', data=dict(slug='gradients', at='/c/gradients', how='primer')).json()
    sid = r['url'].split('/')[2]
    assert lr.journey(sid).parent == dict(page='/c/gradients') and lr.journey(sid).depth == 1
    assert 'Back to Derivatives and gradients' in cl.get(f'/w/{sid}/0').text       # the way back names the concept
    cl.get(f'/w/{sid}/0/check'); cl.post(f'/w/{sid}/0/answer', data=dict(answer='the slope', confidence=90))
    end = cl.post(f'/w/{sid}/0/next', params=dict(pane=1)).text
    assert 'data-rh-done' in end and 'href="/c/gradients"' in end
    assert cl.post(f'/rh/back/{sid}', follow_redirects=False).headers['location'] == '/c/gradients'
    r = cl.post('/rh/open', data=dict(slug='gradients', at='/c/gradients', how='course')).json()
    c = lr.course(r['url'].split('/')[2])
    assert r['how'] == 'course' and c.origin['page'] == '/c/gradients'
    assert 'href="/c/gradients"' in cl.get(r['url']).text.split('data-part="origin"')[1][:600]

def test_a_selected_big_term_opens_its_own_course_linked_both_ways(mk, walk_fake, lr):
    """A selected term that is not on the shelf is added with its size; the tutor picks its own course. The course keeps the step as
    its origin and gets the data of the walk. The step links to the course, and Enough: go back returns to the step."""
    walk_fake.rules['The idea: diffusion model'] = BIG
    cl = mk(); jid = step(cl, lr); lr.merge_journey(jid, data=[dict(path='~/pics', note='My comic pages.')])
    assert 'not in your concepts' in cl.get('/rh/term', params=dict(t='diffusion model', at=f'{jid}/2')).text
    t = cl.post('/rh/term', data=dict(t='diffusion model', at=f'{jid}/2')).text
    assert pick(t)[0] == 'course' and 'a big topic: 8 ideas' in t
    r = cl.post('/rh/open', data=dict(slug='diffusion-model', at=f'{jid}/2', how='course')).json()
    cid = r['url'].split('/')[2]
    c = lr.course(cid)
    assert (c.title, c.origin['walk'], c.origin['step'], c.data) == ('Diffusion model', jid, 2, [dict(path='~/pics', note='My comic pages.')])
    assert cl.post('/rh/open', data=dict(slug='diffusion-model', at=f'{jid}/2', how='course')).json()['url'] == r['url']   # one course for one place
    page = cl.get(r['url']).text
    o = page.split('data-part="origin"')[1][:800]
    assert 'as its own course, from' in o and f'href="/w/{jid}/2"' in o and 'Enough: go back' in o
    assert page.index('Where you start') < page.index('You are here')                  # no stage yet: the level check comes first
    assert 'You reached your goal' not in page and 'Then abhyasa plans the stages.' in page
    s = cl.get(f'/w/{jid}/2').text
    assert 'You are learning <b>Diffusion model</b> as its own course.' in s and f'href="/course/{cid}"' in s
    assert cl.post(f'/course/{cid}/back', follow_redirects=False).headers['location'] == f'/w/{jid}/2'
    assert 'Back from the course <b>Diffusion model</b>: no stage yet.' in cl.get(f'/w/{jid}/2').text

def test_the_course_depth_uses_the_level_check(mk, walk_fake, lr):
    "The course from a rabbit hole asks where you start, as any course does. The job is held, so the pending part shows first."
    walk_fake.rules['The idea: diffusion model'] = BIG
    hold = threading.Event()
    walk_fake.rules['You find out what one learner knows'] = lambda p, sp: (hold.wait(5), LEVEL)[1]
    cl = mk(); jid = step(cl, lr)
    cl.post('/rh/term', data=dict(t='diffusion model', at=f'{jid}/2'))
    cid = cl.post('/rh/open', data=dict(slug='diffusion-model', at=f'{jid}/2', how='course')).json()['url'].split('/')[2]
    r = cl.post(f'/course/{cid}/level')
    assert 'course-pending' in r.text
    hold.set()
    assert 'Do you know how a neural network learns?' in follow(cl, r).text

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_the_pane_and_the_explain_panel_share_the_right_side(mk, walk_fake, lr):
    "With the Explain panel open, a side walk opens in the pane; the panel moves into the page, the strip keeps out of the pane, and both come back on close."
    from playwright.sync_api import sync_playwright
    cl = mk(); jid = step(cl, lr)
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    steps = [dict(say='Look at the scale.', strokes=[dict(op='panel', title='scaling', head='Divide by the root of dk', cols=['dk', 'scale']), dict(op='row', cells=['64'], to='8')])]
    box = "s => { const r = document.querySelector(s)?.getBoundingClientRect(); return r && [r.left, r.right]; }"
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True, args=['--mute-audio'])
            try:
                pg = b.new_page(viewport=dict(width=1280, height=900), reduced_motion='reduce')
                pg.goto(f'http://127.0.0.1:{port}/w/{jid}/2'); pg.wait_for_selector('#check #ans'); pg.wait_for_function('window.abhyasaBoard')
                pg.evaluate("ss => abhyasaBoard.play({steps: ss, tier: 'tutor', sources: []}, {quiet: true, auto: false})", steps)
                pg.wait_for_selector('#board-panel')
                assert not pg.evaluate("document.getElementById('board-panel').classList.contains('inline')")   # at the top right first
                pg.evaluate("document.activeElement.blur()"); pg.keyboard.press('Alt+b')
                pg.wait_for_selector('#rh-offer .rh-way'); pg.keyboard.press('1')
                pg.wait_for_function("() => document.documentElement.classList.contains('rh-open')")
                pg.wait_for_function("() => document.getElementById('board-panel').classList.contains('inline')")
                pane, panel, strip = pg.evaluate(box, '#rh-pane'), pg.evaluate(box, '#board-panel'), pg.evaluate(box, '#guide-strip')
                assert panel[1] <= pane[0] and (strip is None or strip[1] <= pane[0] + 1), (pane, panel, strip)
                pg.keyboard.press('Alt+z')
                pg.wait_for_function("() => !document.documentElement.classList.contains('rh-open')")
                pg.wait_for_function("() => !document.getElementById('board-panel').classList.contains('inline')")   # back at the top right
            finally: b.close()
    finally: srv.should_exit = True; th.join(5)

def test_a_finished_course_offers_the_way_back_as_the_main_button(mk, walk_fake, lr):
    "When each stage of the course is done, Go back to the step is the one main button."
    from abhyasa.course import course_from
    cl = mk(); jid = step(cl, lr)
    c = course_from(lr, 'gradients', dict(walk=jid, step=2))
    lr.put_journey(dict(id='k1', title='Gradients', mode='walk', started=time.time(), steps=[dict(slug='gradients', status='todo', check=dict(way='words', kind='short', depth=2))]))
    lr.walk_step('k1', 0, done=dict(outcome='solid', at=time.time())); lr.update('gradients', floor=4, seen=1)
    lr.change_course(c.id, lambda c: c.stages.append(dict(key='s1', name='Gradients', makes='', ideas=[], foundation=False, skip_if='', short=False, walk='k1', status='ready')))
    lr.merge_journey('k1', course=c.id, stage='s1')
    o = cl.get(f'/course/{c.id}').text.split('data-part="origin"')[1][:900]
    assert 'You finished this course.' in o and re.search(r'<button [^>]*class="go"[^>]*data-act="go-back"|<button [^>]*data-act="go-back"[^>]*class="go"', o)
