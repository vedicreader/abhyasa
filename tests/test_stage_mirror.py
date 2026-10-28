"The mirrored demo: the audience copy of a rupaka demo follows the presenter copy, on the rupaka 0.0.3 store."
import json, pytest
from pathlib import Path
from rupaka.render import page
from rupaka.spec import gallery

pw = pytest.importorskip('playwright.sync_api')
JS = (Path(__file__).parents[1]/'abhyasa'/'core'/'stage.js').read_text()

def _chromium():
    "True when Playwright's bundled Chromium is installed."
    try:
        with pw.sync_playwright() as p: return Path(p.chromium.executable_path).exists()
    except Exception: return False

pytestmark = pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")

def test_mirror_follows_the_presenter_copy():
    spec = gallery()['softmax-temperature']
    with pw.sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page(); pg.set_content(page([spec, spec])); pg.add_script_tag(content=JS)
            pg.wait_for_function("document.querySelectorAll('[data-rupaka][data-rk-ready]').length === 2")
            got = pg.evaluate("""() => {
              const [a, b] = document.querySelectorAll('[data-rupaka]'), ma = abhyasaStage.mirror(a), mb = abhyasaStage.mirror(b);
              a.rupaka.set('t', 2); mb.apply(ma.snapshot().state, {});
              a.rupaka.st.gate.hot = 'done'; mb.apply(ma.snapshot().state, ma.snapshot().gates);
              return {t: b.rupaka.st.t, gate: b.rupaka.st.gate.hot, keys: Object.keys(ma.snapshot().state).sort()};
            }""")
            assert got == dict(t=2, gate='done', keys=['logits', 't'])
        finally: b.close()

def test_mirror_details():
    "Only the input keys and the done gates; apply sets only what changed, fires no gate, and makes the gate inert; watch waits 50 ms; Rupaka.set wins when it is there."
    spec = gallery()['softmax-temperature']
    with pw.sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page(); pg.set_content(page([spec, spec])); pg.add_script_tag(content=JS)
            pg.wait_for_function("document.querySelectorAll('[data-rupaka][data-rk-ready]').length === 2")
            got = pg.evaluate("""async () => {
              const [a, b] = document.querySelectorAll('[data-rupaka]'), ma = abhyasaStage.mirror(a), mb = abhyasaStage.mirror(b), r = {};
              let sets = 0, predicts = 0;
              b.rupaka.on(() => sets++); b.addEventListener('rk-predict', () => predicts++);
              a.rupaka.st.gate.hot = 'pending';
              r.pending = ma.snapshot().gates;   // a gate that is not done is not sent
              r.valid = abhyasaStage.valid({v: 1, t: 'demo', slug: spec_slug, ...ma.snapshot()});
              mb.apply({t: 1, logits: [3, 1.5, 1, -1]}, {});
              r.same = sets;   // no key changed: no draw
              mb.apply({t: 3, p: 'x', gate: {}, _: 9}, {nope: 'done', hot: 'open'});
              r.after = {sets, t: b.rupaka.st.t, p: Array.isArray(b.rupaka.st.p), gate: b.rupaka.st.gate.hot, nope: Object.hasOwn(b.rupaka.st.gate, 'nope')};
              const cap = () => [...b.querySelectorAll('[data-rk-after="hot"]')].every(n => n.style.display !== 'none' && !n.hidden);
              r.capBefore = cap();
              mb.apply({}, {hot: 'done'});
              r.capAfter = cap(); r.gate = b.rupaka.st.gate.hot; r.predicts = predicts; r.log = b.rupaka.st.log ?? null;
              r.inert = [...b.querySelectorAll('.rk-gate')].map(n => n.inert); r.presenterInert = [...a.querySelectorAll('.rk-gate')].map(n => n.inert);
              const seen = []; ma.watch(s => seen.push(s.state.t));
              for (const t of [1.1, 1.2, 1.3, 1.4]) a.rupaka.set('t', t);
              await new Promise(ok => setTimeout(ok, 20)); r.soon = [...seen];
              await new Promise(ok => setTimeout(ok, 120)); r.late = [...seen];
              const calls = []; Rupaka.set = (el, s) => calls.push(['set', el === b, s]); Rupaka.settle = (el, g, pick) => calls.push(['settle', el === b, g, pick]);
              mb.apply({t: 2}, {hot: 'done'});
              delete Rupaka.set; delete Rupaka.settle;
              r.calls = calls;
              return r;
            }""".replace('spec_slug', json.dumps(spec['id'])))
            assert got['pending'] == {} and got['valid'] and got['same'] == 0
            assert got['after'] == dict(sets=1, t=3, p=True, gate='open', nope=False)   # only the input keys; an open gate and an unknown gate do nothing
            assert not got['capBefore'] and got['capAfter'] and got['gate'] == 'done'
            assert got['predicts'] == 0 and got['log'] is None   # no rk-predict and no pick in the audience copy
            assert got['inert'] == [True] and got['presenterInert'] == [False]
            assert got['soon'] == [1.1] and got['late'] == [1.1, 1.4]   # the first change at once, then the last one after 50 ms
            assert got['calls'] == [['set', True, {'t': 2}]]   # the gate is done already, so it is not new
        finally: b.close()

def test_mirror_with_no_gates():
    "A store with no gate table: apply with a gate does not throw, and the snapshot has no gates."
    spec = gallery()['softmax-temperature']
    with pw.sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page(); pg.set_content(page([spec])); pg.add_script_tag(content=JS)
            pg.wait_for_function("document.querySelectorAll('[data-rupaka][data-rk-ready]').length === 1")
            got = pg.evaluate("""() => {
              const a = document.querySelector('[data-rupaka]'), m = abhyasaStage.mirror(a);
              delete a.rupaka.st.gate;
              m.apply({t: 2}, {hot: 'done'});
              return {t: a.rupaka.st.t, gates: m.snapshot().gates};
            }""")
            assert got == dict(t=2, gates={})
        finally: b.close()

SETUP = """([rk, js, name, spec]) => Promise.all([rk, js].map(src => new Promise(ok => {
  const s = document.createElement('script'); s.src = src; s.onload = ok; document.head.appendChild(s);
}))).then(() => {
  const host = document.createElement('div'); host.dataset.rupaka = ''; host.dataset.talkDemo = '';
  document.body.appendChild(host); Rupaka.mount(host, spec);
  window.host = host; window.ch = abhyasaStage.channel(name); window.m = abhyasaStage.mirror(host);
  window.got = []; ch.on('demo', x => got.push(x));
  window.predicts = []; host.addEventListener('rk-predict', e => { predicts.push(e.detail.gate); e.preventDefault(); e.detail.settle(true); });
})"""

def test_mirror_over_the_channel(mk):
    "Two windows of one run: the presenter's moves reach the audience copy as `demo` messages, and the audience copy sends nothing back."
    import socket, threading, time, uvicorn
    from abhyasa.core.stage import stage_assets
    cl = mk(); js = next(x.attrs['src'] for x in stage_assets() if x.attrs.get('src'))
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(cl.app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    end = time.monotonic() + 10
    while not srv.started:
        assert time.monotonic() < end, 'the server did not start in 10 s'
        time.sleep(.05)
    base, spec = f'http://127.0.0.1:{port}', gallery()['softmax-temperature']
    try:
        with pw.sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                ctx = b.new_context(viewport=dict(width=1280, height=720))
                pre, aud = ctx.new_page(), ctx.new_page()
                for pg in (pre, aud): pg.goto(base + '/keys'); pg.wait_for_load_state(); pg.evaluate(SETUP, ['/rupaka/rupaka.js', js, 't1:KEY', spec])
                aud.evaluate("() => ch.on('demo', x => m.apply(x.state, x.gates))")
                pre.evaluate(f"() => m.watch(s => ch.send({{t: 'demo', slug: {json.dumps(spec['id'])}, ...s}}))")
                # the presenter picks at the gate; the talk page settles it and files nothing
                pre.click('.rk-gate .opts button:nth-child(2)'); pre.click('.rk-gate .go')
                aud.wait_for_function("() => host.rupaka.st.gate.hot === 'done'")
                pre.evaluate("() => host.rupaka.set('t', 2.5)")
                aud.wait_for_function("() => host.rupaka.st.t === 2.5")
                assert aud.evaluate("() => host.querySelector('.rk-caption').textContent") == pre.evaluate("() => host.querySelector('.rk-caption').textContent")
                assert aud.evaluate("() => [predicts, host.querySelector('.rk-gate').inert, host.rupaka.st.log ?? null]") == [[], True, None]
                assert pre.evaluate("() => [predicts, got.length]") == [['hot'], 0]   # one catch in the presenter window; nothing came back
            finally: b.close()
    finally: srv.should_exit = True; th.join(5)
