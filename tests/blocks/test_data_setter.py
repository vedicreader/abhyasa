"The folder setter: a notebook step names its data (EPISODES), and you pick or paste its folder on the idea page, the walk page or the course page."
import os, re, pytest
from pathlib import Path
import lxml.html
from starlette.testclient import TestClient
import abhyasa.blocks.add.app as add_app
import abhyasa.path as walk_engine
from abhyasa.contract import _GOOD, validate_nb_spec
from test_my_data import course_walk, episodes

EPS = dict(name='EPISODES', path='', need=True, what='Text of the comic episodes. Short caption lines are taken from it and used as prompts.')
IMGS = dict(name='IMAGES', path='', need=True, what='Folder of your own Indian comic panel images. Name the folder you want to use.')

def needs(lr, jid='gw', i=1):
    "Step `i` of walk `jid` is a notebook step that needs EPISODES and IMAGES, with no folder for either."
    lr.walk_step(jid, i, nb=validate_nb_spec({**_GOOD, 'data': [EPS, IMGS]}))

def picker(monkeypatch, cl, path):
    "The folder chooser of this Mac is faked: it gives `path`. The client comes from this Mac."
    monkeypatch.setattr(add_app, 'can_pick', lambda: True)
    monkeypatch.setattr(add_app, 'choose_folder', lambda say='': [str(path)] if path else [])
    return TestClient(cl.app, client=('127.0.0.1', 50000))

def set_data(cl, name, what='', **kw):
    "Press Pick a folder (`pick='1'`) or Use it (`path=`) in the setter of `name`, as htmx does."
    return cl.post('/learn/data', data=dict(jid='gw', name=name, what=what, **kw), headers={'HX-Request': 'true'})

def test_set_episodes_on_the_idea_page(mk, lr, tmp_path, monkeypatch):
    "Pick a folder for EPISODES on the idea page: it goes under Your data with that name, the spec that Leela reads has the path, and the setter says so."
    home, c = episodes(tmp_path, monkeypatch), course_walk(lr)
    (comics := home.parent/'comics').mkdir()
    needs(lr)
    cl = picker(monkeypatch, mk(), comics)
    card = cl.get('/w/gw/1/check').text
    assert 'This step needs 2 folders on this Mac:' in card and card.count('data-act="set-data"') == 2 and 'Pick a folder' in card and 'or paste a path' in card
    r = set_data(cl, 'EPISODES', EPS['what'], pick='1')
    assert r.status_code == 200 and re.sub(r'<[^>]+>', '', r.text).split() == ['EPISODES:', '~/comics', '✓', 'Change'] and 'HX-Trigger' not in r.headers
    row = dict(path='~/comics', note=EPS['what'], name='EPISODES')
    assert lr.course(c.id).data == [row] and lr.journey('gw').data == [row]   # on the course, and so on each of its walks
    spec = validate_nb_spec(lr.journey('gw').steps[1]['nb'])                 # the hand-off: Leela opens the step and reads this spec
    assert [(d['name'], d['path'], d['need']) for d in spec['data']] == [('EPISODES', '~/comics', False), ('IMAGES', '', True)]
    card = cl.get('/w/gw/1/check').text
    assert 'This step needs 1 folder on this Mac:' in card and 'data-name="EPISODES"' not in card and 'data-name="IMAGES"' in card

def test_the_missing_line_goes_when_each_name_has_a_folder(mk, lr, tmp_path, monkeypatch):
    "A pasted path sets IMAGES. When no name is missing, the page gets `data-done`, and the card has no missing line."
    home, _ = episodes(tmp_path, monkeypatch), course_walk(lr)
    (home.parent/'comics').mkdir(); (home.parent/'panels').mkdir()
    needs(lr)
    cl = mk()
    assert 'HX-Trigger' not in set_data(cl, 'EPISODES', path=str(home.parent/'comics')).headers
    r = set_data(cl, 'IMAGES', IMGS['what'], path='~/panels')
    assert r.headers.get('HX-Trigger') == 'data-done' and '~/panels' in r.text
    card = cl.get('/w/gw/1/check').text
    assert 'This step needs' not in card and 'data-act="set-data"' not in card and '~/comics' in card and '~/panels' in card
    assert walk_engine.missing_data(lr.journey('gw')) == []

def test_a_bad_path_gives_one_plain_reason(mk, lr, tmp_path, monkeypatch):
    "A path outside the home folder, no path, and a pick from another computer each give one plain line, and keep nothing."
    episodes(tmp_path, monkeypatch); course_walk(lr); needs(lr)
    cl = mk()
    errs = lambda r: [e.text_content() for e in lxml.html.fromstring(r.text).xpath('//*[contains(@class, "req-err")]')]
    assert errs(set_data(cl, 'EPISODES', path='/etc')) == ['abhyasa cannot use this folder: the path is not in your home folder.']
    assert errs(set_data(cl, 'EPISODES', path='~/nothing')) == ['abhyasa finds no folder at this path.']
    assert errs(set_data(cl, 'EPISODES', path='  ')) == [add_app.DATA_EMPTY]
    monkeypatch.setattr(add_app, 'can_pick', lambda: True)
    assert errs(set_data(cl, 'EPISODES', pick='1')) == [add_app.NOT_HERE]     # the test client is not 127.0.0.1
    assert not lr.journey('gw').get('data')

def test_a_cancel_keeps_the_setter(mk, lr, tmp_path, monkeypatch):
    "Cancel in the folder chooser gives the setter again, with no line and no change."
    episodes(tmp_path, monkeypatch); course_walk(lr); needs(lr)
    cl = picker(monkeypatch, mk(), None)
    r = set_data(cl, 'EPISODES', EPS['what'], pick='1')
    assert 'data-act="set-data"' in r.text and 'req-err' not in r.text and not lr.journey('gw').get('data')

def test_the_course_list_asks_for_each_name_once(mk, lr, tmp_path, monkeypatch):
    "The course list has one short line for each missing name, with no doubled stop. Set it opens the setter in place, and the line goes when it is set."
    home, c = episodes(tmp_path, monkeypatch), course_walk(lr)
    (home.parent/'comics').mkdir()
    needs(lr)
    cl = mk()
    pg = lxml.html.fromstring(cl.get(f'/course/{c.id}').text)
    lines = [' '.join(li.text_content().split()) for li in pg.xpath('//li[contains(@class, "setup")][.//*[@data-act="set-data"]]')]
    assert lines == ['EPISODES: the text of the comic episodes. Set its folder. Set it', 'IMAGES: your own Indian comic panel images. Set its folder. Set it']
    assert not any('..' in x or 'Folder of' in x for x in lines)
    go = pg.xpath('//li[contains(@class, "setup")]//button[@data-act="set-data"]')[0].get('hx-get')
    form = cl.get(go).text
    assert 'name="name" value="EPISODES"' in form and 'or paste a path' in form
    assert '~/comics' in set_data(cl, 'EPISODES', path='~/comics').text
    page = cl.get(f'/course/{c.id}').text
    assert 'EPISODES: the text' not in page and 'IMAGES: your own' in page

def test_the_walk_page_lists_the_names_with_no_folder(mk, lr, tmp_path, monkeypatch):
    "Your data on the walk page has a setter for each name that a step needs and that has no folder. A walk with no course keeps the folder on the walk."
    home = episodes(tmp_path, monkeypatch)
    (home.parent/'comics').mkdir()
    course_walk(lr); lr.merge_journey('gw', course=None)   # a walk on its own
    needs(lr)
    cl = mk()
    part = lxml.html.fromstring(cl.get('/w/gw').text).xpath('//*[@data-part="data"]')[0]
    assert 'The steps need 2 more folders on this Mac:' in part.text_content()
    assert [f.get('data-name') for f in part.xpath('.//*[@data-act="set-data"]')] == ['EPISODES', 'IMAGES']
    set_data(cl, 'EPISODES', path='~/comics')
    assert lr.journey('gw').data == [dict(path='~/comics', note='', name='EPISODES')]
    part = lxml.html.fromstring(cl.get('/w/gw').text).xpath('//*[@data-part="data"]')[0]
    assert [f.get('data-name') for f in part.xpath('.//*[@data-act="set-data"]')] == ['IMAGES'] and '~/comics' in part.text_content()

def test_change_gives_a_new_folder_for_the_same_name(mk, lr, tmp_path, monkeypatch):
    "Change opens the setter again. A second folder for EPISODES takes the place of the first: one row for one name. A row with no name still works."
    home, c = episodes(tmp_path, monkeypatch), course_walk(lr)
    (home.parent/'comics').mkdir(); (home.parent/'comics2').mkdir()
    needs(lr)
    walk_engine.add_data(lr, c.id, str(home))   # an older row, with no name: it is RAMAYANA
    cl = mk()
    r = set_data(cl, 'EPISODES', path='~/comics')
    change = lxml.html.fromstring(r.text).xpath('//button[text()="Change"]')[0].get('hx-get')
    assert 'data-act="set-data"' in cl.get(change).text
    set_data(cl, 'EPISODES', path='~/comics2')
    assert [(d['path'], d.get('name')) for d in lr.course(c.id).data] == [('~/ramayana', None), ('~/comics2', 'EPISODES')]
    names = {d['name']: d['path'] for d in lr.journey('gw').steps[1]['nb']['data']}
    assert names['EPISODES'] == '~/comics2' and names['RAMAYANA'] == '~/ramayana'

@pytest.mark.parametrize('first', ['/w/gw', '/course/{cid}'])
def test_two_stored_names_for_one_folder_join_on_the_first_read(mk, lr, tmp_path, monkeypatch, first):
    "Two stored specs name the same images IMAGES and COMIC_IMAGES. The first read of the walk or the course joins them: the pages ask for one image folder."
    episodes(tmp_path, monkeypatch); c = course_walk(lr)
    lr.walk_step('gw', 0, check=dict(way='code', kind='notebook', depth=3), nb=validate_nb_spec({**_GOOD, 'data': [IMGS]}))
    lr.walk_step('gw', 1, nb=validate_nb_spec({**_GOOD, 'task': 'Load COMIC_IMAGES.', 'data': [EPS, {**IMGS, 'name': 'COMIC_IMAGES', 'what': IMGS['what'].upper()}]}))
    assert [d['name'] for d in walk_engine.missing_data(lr.journey('gw'))] == ['IMAGES', 'EPISODES', 'COMIC_IMAGES']
    cl = mk()
    assert cl.get(first.format(cid=c.id)).status_code == 200
    s1 = lr.journey('gw').steps[1]['nb']
    assert (s1['task'], s1['data'][1]['name'], s1['data'][1]['what']) == ('Load IMAGES.', 'IMAGES', IMGS['what'].upper())   # only the name changes
    part = lxml.html.fromstring(cl.get('/w/gw').text).xpath('//*[@data-part="data"]')[0]
    assert [f.get('data-name') for f in part.xpath('.//*[@data-act="set-data"]')] == ['IMAGES', 'EPISODES']
    pg = lxml.html.fromstring(cl.get(f'/course/{c.id}').text)
    assert [li.text_content().split(':')[0].strip() for li in pg.xpath('//li[contains(@class, "setup")][.//*[@data-act="set-data"]]')] == ['IMAGES', 'EPISODES']

def _chromium():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p: return Path(p.chromium.executable_path).exists()
    except Exception: return False

SHOT = os.getenv('ABHYASA_SHOT', '')   # a path: the browser check keeps a picture of the setter there

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_the_setter_in_a_browser_at_1280(mk, lr, tmp_path, monkeypatch):
    "At 1280 px the setter fits in the card. Pick a folder sets EPISODES in place, and a pasted path sets IMAGES, so the card loads again with no missing line."
    import socket, threading, time, uvicorn
    from playwright.sync_api import sync_playwright
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH', os.getenv('PLAYWRIGHT_BROWSERS_PATH') or str(Path.home()/'Library'/'Caches'/'ms-playwright'))
    home, _ = episodes(tmp_path, monkeypatch), course_walk(lr)
    (home.parent/'comics').mkdir(); (home.parent/'panels').mkdir()
    needs(lr)
    cl = mk()
    monkeypatch.setattr(add_app, 'can_pick', lambda: True)
    monkeypatch.setattr(add_app, 'choose_folder', lambda say='': [str(home.parent/'comics')])
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page(viewport=dict(width=1280, height=900))
                pg.goto(f'http://127.0.0.1:{port}/w/gw/1'); pg.wait_for_selector('form[data-name="EPISODES"]')
                card, eps = pg.locator('#check').bounding_box(), pg.locator('form[data-name="EPISODES"]')
                box = eps.bounding_box()
                assert box['x'] >= card['x'] and box['x'] + box['width'] <= card['x'] + card['width'] + 1   # it fits in the card
                assert pg.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert eps.locator('[data-act="pick-data"]').is_visible() and eps.locator('input[name=path]').is_visible()
                eps.scroll_into_view_if_needed()
                if SHOT: pg.locator('[data-part="data-need"]').screenshot(path=SHOT)
                eps.locator('[data-act="pick-data"]').click()
                pg.wait_for_selector('.data-set.done[data-name="EPISODES"]')
                assert ' '.join(pg.locator('.data-set.done').inner_text().split()) == 'EPISODES: ~/comics ✓ Change'
                imgs = pg.locator('form[data-name="IMAGES"]')
                imgs.locator('input[name=path]').fill('~/panels'); imgs.locator('input[name=path]').press('Enter')
                pg.wait_for_function("!document.querySelector('[data-part=\"data-need\"]')")
                assert '~/panels' in pg.locator('#check').inner_text() and '~/comics' in pg.locator('#check').inner_text()
            finally: b.close()
    finally: srv.should_exit = True; th.join(5)
