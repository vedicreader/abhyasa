"Show it in 3D: the 3D route gives a card with a scene, a failed explainer gives the 2D demo, three.js comes from rupaka beside rupaka.js, and a scene draws in a headless browser."
import json, re, socket, threading, time, pytest
from rupaka.spec import gallery
from abhyasa.demo import scene_example, REFUSED
from test_show_me import svc, aid_of

SCENE = {**scene_example(), 'id': 'ranking-3d'}
BAD = {**SCENE, 'blocks': [{**SCENE['blocks'][0], 'steps': ['One line.']}]}

def wait_3d(cl, slug):
    "Wait for each 3D explainer job on `slug`; their keys."
    ks = [k for k in svc(cl)['tutor'].jobs if k.startswith(f'{slug}:3d')]
    for k in ks: svc(cl)['tutor'].jobs[k].result(timeout=60)
    return ks

def test_a_3d_ask_gives_a_card_with_the_scene(mk, fake, lr):
    fake.rules['You design one 3D explainer'] = SCENE
    cl = mk()
    r = cl.post('/demo/ask', data=dict(where='concept', concept='ranking', said='show it in 3D')).text
    assert '3D explainer' in r and 'You asked for 3D' in r and 'Show a 2D demo' not in r and 'while the 3D explainer builds' in r   # the 2D demo comes under it, with no link
    assert len(wait_3d(cl, 'ranking')) == 1
    a = lr.asked(aid_of(r))
    assert a.kind == 'explainer'   # the record of the ask, as for a 2D ask
    d = lr.demo_for('ranking', aim='3d', key=a.key)
    assert d and d.spec['mode'] == 'learn' and lr.asks('ranking')[0].slug == d.slug
    card = cl.get(f'/demo/asked/{a.id}').text
    assert 'How an F-35B hovers' in card and 'data-rupaka' in card and 'scene' in card
    assert [k for k in svc(cl)['tutor'].jobs if k.startswith('ranking#')]   # the 2D demo builds while the 3D explainer builds, so Show is never silent
    for k in [k for k in svc(cl)['tutor'].jobs if k.startswith('ranking')]: svc(cl)['tutor'].jobs[k].result(timeout=60)
    ready = cl.post('/demo/ask', data=dict(where='concept', concept='ranking', said='show it in 3D')).text
    assert ready.count('class="lbl"') == 1 and 'while the 3D explainer builds' not in ready and 'Show a 2D demo' not in ready   # one label; no line that is not true now

def test_show_it_in_3d_under_a_2d_demo_asks_for_the_explainer(mk, fake, lr):
    fake.rules['You design one 3D explainer'] = SCENE
    cl = mk()
    r = cl.post('/demo/ask', data=dict(where='concept', concept='ranking', said='', kind='3d')).text
    assert '3D explainer' in r and 'You asked for 3D. The scene builds one step at a time.' in r
    wait_3d(cl, 'ranking')
    assert lr.asks('ranking')[0].kind == 'explainer' and 'How an F-35B hovers' in cl.get(f'/demo/asked/{aid_of(r)}').text

def test_a_failed_3d_explainer_says_so_and_gives_the_2d_demo(mk, fake, lr):
    fake.rules['You design one 3D explainer'] = BAD
    cl = mk()
    r = cl.post('/demo/ask', data=dict(where='concept', concept='ranking', said='show the ranks in 3D')).text
    wait_3d(cl, 'ranking')
    a = lr.asked(aid_of(r))
    out = cl.get(f'/demo/asked/{a.id}').text
    assert REFUSED in out and lr.demo_for('ranking', aim='3d', key=a.key) is None
    for k in [k for k in svc(cl)['tutor'].jobs if k.startswith('ranking#')]: svc(cl)['tutor'].jobs[k].result(timeout=60)
    two = cl.get(f'/demo/asked/{a.id}?kind=demo').text
    assert 'data-rupaka' in two and 'A 3D explainer: watch' not in two

def test_three_js_is_served_beside_rupaka_js(mk, lr):
    cl = mk()
    r = cl.get('/rupaka/three.js')
    assert r.status_code == 200 and r.headers['content-type'].startswith('text/javascript') and 'RupakaTHREE' in r.text
    d = lr.put_demo(gallery()['reciprocal-rank-fusion'], 'reciprocal-rank-fusion')
    page = cl.get(f"/demo/asked/{lr.put_ask('reciprocal-rank-fusion', where='concept').id}").text
    assert '/rupaka/rupaka.js' in page and 'three.js' not in page   # rupaka loads it only when a scene mounts

# --- in a headless browser ---------------------------------------------------------------------------------------------

def _chromium():
    try:
        from playwright.sync_api import sync_playwright
        from pathlib import Path
        with sync_playwright() as p: return Path(p.chromium.executable_path).exists()
    except Exception: return False

DRAWN = """() => { const cv = document.querySelector('.demo-card canvas'), c = document.createElement('canvas');
  c.width = cv.width; c.height = cv.height; const g = c.getContext('2d'); g.drawImage(cv, 0, 0);
  const px = g.getImageData(0, 0, c.width, c.height).data, seen = new Set();
  for (let i = 0; i < px.length; i += 4 * 97) seen.add(`${px[i]},${px[i + 1]},${px[i + 2]}`);
  return seen.size; }"""

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_a_3d_card_draws_a_scene_and_steps_forward(mk, lr):
    "A 2D demo page loads no three.js. The 3D card mounts a scene: its canvas draws more than a blank fill, and Next moves to step 2."
    import uvicorn
    from playwright.sync_api import sync_playwright
    flat = lr.put_demo(gallery()['reciprocal-rank-fusion'], 'reciprocal-rank-fusion')
    d = lr.put_demo(SCENE, 'ranking', aim='3d')
    flat_a, d_a = lr.put_ask('reciprocal-rank-fusion', where='concept'), lr.put_ask('ranking', where='concept', kind='explainer')   # a demo shows as the card of its ask
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(mk().app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True, args=['--enable-unsafe-swiftshader'])
            try:
                pg = b.new_page(viewport=dict(width=1000, height=900))
                urls = []
                pg.on('request', lambda r: urls.append(r.url))
                pg.goto(f'http://127.0.0.1:{port}/demo/asked/{flat_a.id}'); pg.wait_for_selector('.rk')
                assert not [u for u in urls if 'three.js' in u] and pg.evaluate('!window.RupakaTHREE')
                pg.goto(f'http://127.0.0.1:{port}/demo/asked/{d_a.id}')
                pg.wait_for_selector('[data-rk-gl="ready"]', timeout=30000)
                assert [u for u in urls if '/rupaka/three.js' in u]
                assert 'How an F-35B hovers' in pg.inner_text('.demo-card')
                pg.wait_for_function('document.querySelector("[data-rk-still]")?.dataset.rkStill === "1"', timeout=15000)
                assert pg.evaluate(DRAWN) > 8   # more than a blank fill: the floor, the bodies and their ink
                assert pg.inner_text('.demo-card .count') == 'Step 1 of 6'
                pg.click('.demo-card .bar button:last-child')
                pg.wait_for_function('document.querySelector(".demo-card .count").textContent === "Step 2 of 6"', timeout=5000)
            finally: b.close()
    finally:
        srv.should_exit = True; th.join(5)

def test_show_it_in_3d_keeps_the_seeded_2d_demo(mk, fake, lr):
    """"yes, show me it move" makes a 2D demo from the values of the page. Show it in 3D on that card asks for the 3D explainer with the same values,
    puts it in the card above the 2D demo, and takes the button away. The 2D demo stays, and no second 2D job starts."""
    import html as H
    fake.rules['You design one 3D explainer'] = SCENE
    cl = mk(); t = svc(cl)['tutor']
    ctx = dict(page='/c/ranking', slug='ranking', anchors=[dict(id='code1', kind='code', text='assert rrf([1, 2], k=60) == 0.032')])
    ev = [json.loads(l[6:]) for l in cl.post('/guide/ask', json=dict(said='yes, show me it move', ctx=ctx)).text.splitlines() if l.startswith('data: ')][0]
    for k in list(t.jobs): t.jobs[k].result(timeout=60)
    card = ev['show']['html']
    aid = re.search(r'data-ask="([0-9a-f]{12})"', card)[1]
    assert f'id="three-{aid}"' in card and f'id="three-btn-{aid}"' in card
    btn = [json.loads(H.unescape(v)) for v in re.findall(r"hx-vals='([^']*)'", card) if '"3d"' in v][0]
    r = cl.post('/demo/ask', data=btn).text
    assert '3D explainer' in r and 'The tutor makes a demo' not in r and f'id="three-btn-{aid}"' in r and 'hx-swap-oob' in r   # only the 3D part; the button goes
    assert sorted(k.split('#')[0] for k in t.jobs) == ['ranking', 'ranking:3d']   # one 2D job and one 3D job
    asks = lr.asks('ranking')
    assert {a.ask for a in asks} == {'it move Values from the page: assert rrf([1, 2], k=60) == 0.032'}   # every job of the ask has the values
