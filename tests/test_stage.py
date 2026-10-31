"The stage bundle: the message checks in node, the key rows, the assets, and the two windows in a headless browser."
import json, shutil, subprocess, pytest
from pathlib import Path
from abhyasa.core.stage import STAGE_CASES, STAGE_TYPES, STAGE_V, STAGE_KEYS, stage_assets

JS = Path(__file__).parents[1]/'abhyasa'/'core'/'stage.js'
HARNESS = ("const s = require(process.argv[1]); const cs = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
           "process.stdout.write(JSON.stringify(cs.map(([m]) => s.valid(m))));")
no_node = pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')

def node(code, *args, stdin=''):
    "The JSON that `code` writes, with `s` as the stage module."
    r = subprocess.run(['node', '-e', f"const s = require(process.argv[1]); process.stdout.write(JSON.stringify({code}));", str(JS), *args],
                       input=stdin, capture_output=True, text=True, check=True)
    return json.loads(r.stdout)

@no_node
def test_each_case_in_node():
    r = subprocess.run(['node', '-e', HARNESS, str(JS)], input=json.dumps(STAGE_CASES), capture_output=True, text=True, check=True)
    assert json.loads(r.stdout) == [ok for _, ok in STAGE_CASES]

def test_cases_cover_each_type():
    assert STAGE_V == 1 and {m['t'] for m, ok in STAGE_CASES if ok} == set(STAGE_TYPES)

@no_node
def test_js_table_has_the_same_types():
    assert node('s.types()') == list(STAGE_TYPES) and node('s.V') == STAGE_V

@no_node
def test_more_bad_messages():
    "A deep or odd message, a pane path with a control character, a join with no code, and a type that a host adds later."
    bad = [dict(v=1, t='demo', slug='x', state=dict(a=[[[[[[[[[[1]]]]]]]]]]), gates={}), dict(v=1, t='pane', url='/w/x\n'),
           dict(v=1, t='join', url='http://192.168.1.23:5180/j/K7PQ2M', code=None), dict(v=1, t='point', x=.5), dict(v=1, t='point', off=True, id='a'),
           dict(v=1, t='demo', slug='x', state={}, gates=dict(hot='open')), dict(v=1, t='result', slide='s3', kind='choice', rounds=[], right=9, main=None),
           dict(v=1, t='go', slide='s4', beat=2.5), dict(v=1, t='go', slide='s4', beat=True), dict(v='1', t='go', slide='s4', beat=2), None, 'go',
           *(dict(v=1, t='demo', slug='x', state={}, gates={k: 'done'}) for k in PROTO),
           *(dict(v=1, t='demo', slug='x', state={k: 1}, gates={}) for k in PROTO),
           dict(v=1, t='demo', slug='x', state=dict(a=[dict(prototype=1)]), gates={})]
    assert node('JSON.parse(process.argv[2]).map(s.valid)', json.dumps(bad)) == [False] * len(bad)
    assert node("[s.valid({v: 1, t: 'go', slide: 's1', beat: NaN}), s.valid({v: 1, t: 'go', slide: 's1', beat: 1, constructor: 1})]") == [False, False]
    assert node("(s.add('card', {text: m => typeof m === 'string'}), [s.valid({v: 1, t: 'card', text: 'a'}), s.valid({v: 1, t: 'card', text: 1})])") == [True, False]
    with pytest.raises(subprocess.CalledProcessError): node("s.add('go', {})")   # a type that is there stays as it is
    for f in ["{__proto__: () => true}", "{text: 1}", "[]"]:
        with pytest.raises(subprocess.CalledProcessError): node(f"s.add('card', {f})")

PROTO = ['__proto__', 'constructor', 'prototype']

@no_node
def test_added_type_is_a_frozen_copy():
    "A change to the caller's objects after `add` does not change the type."
    code = ("(() => { const f = {text: m => typeof m === 'string'}, need = ['text']; s.add('card', f, need);"
            " f.text = () => true; f.more = () => true; need.push('more');"
            " return [s.valid({v: 1, t: 'card', text: 'a'}), s.valid({v: 1, t: 'card', text: 1}), s.valid({v: 1, t: 'card', text: 'a', more: 1})] })()")
    assert node(code) == [True, False, False]

@no_node
def test_is_local_matches_pane_py():
    from abhyasa.core.pane import is_local
    urls = ['/w/a/0', '/', '//evil.example', '/\\evil', 'https://evil.example/', 'javascript:alert(1)', '/a\tb', '/a\x7f', 'w/a', '']
    assert node('JSON.parse(process.argv[2]).map(s.isLocal)', json.dumps(urls)) == [is_local(u) for u in urls]

def test_stage_keys_add_no_alt_key():
    "The ⌥ keys of the talk are ones that the app has now: ⌥S, ⌥B and ⌥Z keep their meaning."
    from abhyasa.core.keys import KEYS
    alt = {k for _, k, _ in KEYS if k.startswith('⌥')}
    assert {k for _, k, _ in STAGE_KEYS if k.startswith('⌥')} <= alt

def test_assets_are_served(mk):
    cl, h = mk(), [x.attrs for x in stage_assets()]
    assert 'prefers-reduced-motion' in cl.get(h[0]['href']).text and 'abhyasaStage' in cl.get(h[1]['src']).text

def _chromium():
    "True when Playwright's bundled Chromium is installed."
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p: return Path(p.chromium.executable_path).exists()
    except Exception: return False

SETUP = """([css, js, name, fade]) => new Promise(ok => {
  const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = css; document.head.appendChild(l);
  const s = document.createElement('script'); s.src = js; s.onload = ok; document.head.appendChild(s);
}).then(() => {
  const el = document.createElement('div'); el.className = 'stage'; el.dataset.title = 'Attention <b>in short</b>';
  el.innerHTML = '<h1 id="t">A title</h1><p class="passage" id="scale">Scale by the root of dk.</p>';
  Object.assign(el.style, {position: 'fixed', left: '0', top: '0', width: '640px', height: '360px', zIndex: 9});
  document.body.appendChild(el);
  window.got = []; window.st = el; window.ch = abhyasaStage.channel(name);
  for (const t of abhyasaStage.types()) ch.on(t, m => got.push(m));
})"""

@pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")
def test_stage_in_a_browser(mk):
    "Two windows of one run: valid messages pass, bad ones and another run's are dropped; the dot, the lit id, the blank screen, the pane, the keys and the laser."
    import socket, threading, time, uvicorn
    from playwright.sync_api import sync_playwright
    cl = mk(); css, js = (x.attrs.get('href') or x.attrs.get('src') for x in stage_assets())
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    base = f'http://127.0.0.1:{port}'
    bad = [m for m, ok in STAGE_CASES if not ok]
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                ctx = b.new_context(viewport=dict(width=1280, height=720), reduced_motion='no-preference')
                pre, aud, old = ctx.new_page(), ctx.new_page(), ctx.new_page()
                for pg, name in [(pre, 't1:KEY'), (aud, 't1:KEY'), (old, 't1:OLD')]:
                    pg.goto(base + '/keys'); pg.wait_for_load_state(); pg.evaluate(SETUP, [css, js, name, 200])
                aud.evaluate("() => { window.drawn = []; window.au = abhyasaStage.audience(st, {ch, fade: 200, draw: m => drawn.push(m.t)}) }")
                pre.wait_for_function("() => got.some(m => m.t === 'hello')")
                assert aud.evaluate("() => document.querySelector('.stage-blank').textContent") == 'Attention <b>in short</b>'   # text, not HTML

                # the sender throws on a bad message; a raw post of each bad case, and a message of another run, are dropped
                assert pre.evaluate("() => { try { ch.send({t: 'eval', code: 'alert(1)'}); return 'sent' } catch (e) { return e.message } }") == 'not a valid stage message'
                pre.evaluate("bad => { const bc = new BroadcastChannel('abhyasa-stage:t1:KEY'); bad.forEach(m => bc.postMessage(m)); bc.close() }", bad)
                old.evaluate("() => ch.send({t: 'go', slide: 's9', beat: 1})")
                pre.evaluate("() => { ch.send({t: 'go', slide: 's4', beat: 2}); ch.send({t: 'pane', url: '/keys'}); ch.send({t: 'point', id: 'scale'}) }")
                aud.wait_for_function("() => drawn.includes('go') && st.classList.contains('beside')")
                assert aud.evaluate("() => got.filter(m => m.t !== 'here').map(m => m.t)") == ['go', 'pane', 'point']
                assert old.evaluate("() => got") == []   # the old window takes nothing from the new run either
                assert aud.evaluate("() => [document.querySelector('iframe.stage-pane').getAttribute('src'), document.getElementById('scale').classList.contains('lit')]") == ['/keys', True]
                pre.evaluate("() => ch.send({t: 'pane', url: null})")
                aud.wait_for_function("() => !st.classList.contains('beside') && !document.querySelector('iframe.stage-pane')")

                # the output of a run reaches the audience, as data for textContent; a run question too
                pre.evaluate("() => { ch.send({t: 'ask', slide: 's5', ask: {kind: 'run', q: 'What does this print?'}}); ch.send({t: 'output', slide: 's5', text: '2 <b>x</b>'}) }")
                aud.wait_for_function("() => drawn.includes('output')")
                assert aud.evaluate("() => [drawn.includes('ask'), got.find(m => m.t === 'output').text]") == [True, '2 <b>x</b>']

                # the blank screen, and the dot that fades after `fade` ms
                pre.evaluate("() => { ch.send({t: 'blank', on: true}); ch.send({t: 'point', x: .5, y: .25}) }")
                aud.wait_for_function("() => st.classList.contains('blank') && document.querySelector('.stage-dot.on')")
                assert aud.evaluate("() => getComputedStyle(document.querySelector('.stage-blank')).display") == 'grid'
                assert aud.evaluate("() => document.querySelector('.stage-dot').style.left") == '50%'
                aud.wait_for_function("() => !document.querySelector('.stage-dot.on')")
                assert aud.evaluate("() => getComputedStyle(document.querySelector('.stage-dot')).transitionDuration") != '0s'

                # the audience says it is there every 2 s
                pre.wait_for_function("() => got.some(m => m.t === 'here')", timeout=5000)

                # keys: only with html.talk, not in a text box, not in the demo (Esc still comes), not with ⌥
                pre.evaluate("""() => { window.hit = []; const k = n => () => hit.push(n);
                  document.body.insertAdjacentHTML('beforeend', '<input id="box"><div data-rupaka><button id="demo">demo</button></div>');
                  document.body.insertAdjacentHTML('beforeend', '<button id="btn" onclick="hit.push(\\'click\\')">b</button>');
                  window.pr = abhyasaStage.presenter(st, ch, {keys: {KeyD: k('d'), Escape: k('esc'), '3': k('3'), 'Shift+KeyC': k('C'), Space: k('space')}}) }""")
                pre.keyboard.press('KeyD')
                pre.evaluate("() => document.documentElement.classList.add('talk')")
                pre.keyboard.press('KeyD'); pre.keyboard.press('Digit3'); pre.keyboard.press('Shift+KeyC'); pre.keyboard.press('Alt+KeyD')
                pre.focus('#box'); pre.keyboard.press('KeyD')
                pre.focus('#demo'); pre.keyboard.press('KeyD'); pre.keyboard.press('Escape')
                assert pre.evaluate('() => hit') == ['d', '3', 'C', 'esc']
                # a held key does not repeat, and a focused button does not take Space from the talk
                pre.evaluate("() => document.dispatchEvent(new KeyboardEvent('keydown', {code: 'KeyD', key: 'd', repeat: true, bubbles: true}))")
                pre.focus('#btn'); pre.keyboard.press('Space')
                assert pre.evaluate('() => hit') == ['d', '3', 'C', 'esc', 'space']
                pre.evaluate("() => document.activeElement.blur()")

                # the laser: off sends nothing; on, a move sends a point at most once a frame, and leaving sends off
                pre.mouse.move(100, 100); pre.wait_for_timeout(100)
                assert not aud.evaluate("() => document.querySelector('.stage-dot.on')")
                assert pre.evaluate('() => pr.laser()') is True
                aud.evaluate("() => { window.pts = []; ch.on('point', m => pts.push(m)) }")
                pre.evaluate("() => { for (let i = 0; i < 50; i++) st.dispatchEvent(new PointerEvent('pointermove', {clientX: 100 + i, clientY: 90})) }")
                aud.wait_for_function("() => pts.length")
                pre.wait_for_timeout(150)
                assert aud.evaluate("() => pts") == [dict(v=1, t='point', x=round(149 / 640, 4), y=.25)]   # 50 moves in one frame: one message
                pre.mouse.move(320, 180)
                aud.wait_for_function("() => pts.some(m => m.x === .5 && m.y === .5)")
                pre.mouse.move(900, 600)
                aud.wait_for_function("() => pts.length && pts.at(-1).off === true && !document.querySelector('.stage-dot.on')")
                aud.wait_for_function("() => getComputedStyle(document.querySelector('.stage-dot')).opacity === '0'", timeout=3000)   # after the fade

                # with reduced motion, nothing fades
                aud.emulate_media(reduced_motion='reduce')
                assert aud.evaluate("() => [getComputedStyle(document.querySelector('.stage-dot')).transitionDuration, getComputedStyle(document.querySelector('.stage-blank')).animationName]") == ['0s', 'none']
            finally: b.close()
    finally: srv.should_exit = True; th.join(5)
