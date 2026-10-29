"The mirrored demo: the audience copy of a rupaka demo follows the presenter copy through the rupaka 0.0.5 host API."
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

# The page settles each prediction as the talk page does: it files nothing.
TALK = "document.addEventListener('rk-predict', e => { e.preventDefault(); e.detail.settle(true); })"

def _two(pg, spec):
    "Two copies of `spec` on `pg`, with the stage script and the talk page's catch of each prediction."
    pg.set_content(page([spec, spec])); pg.add_script_tag(content=JS); pg.evaluate(f'() => {{ {TALK}; }}')
    pg.wait_for_function("document.querySelectorAll('[data-rupaka][data-rk-ready]').length === 2")

def test_mirror_needs_rupaka_006():
    "With no `Rupaka.open` (rupaka 0.0.5 and older), `mirror` throws an error that names the rupaka version."
    spec = gallery()['softmax-temperature']
    with pw.sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page(); _two(pg, spec)
            got = pg.evaluate("""() => { delete Rupaka.open;
              try { abhyasaStage.mirror(document.querySelector('[data-rupaka]')); return 'no error'; } catch (e) { return e.message; } }""")
            assert 'rupaka 0.0.6' in got
        finally: b.close()

def test_mirror_follows_the_presenter_copy():
    "The presenter picks at the gate; the snapshot has the inputs, the done gate and the pick, and the audience copy draws the same verdict."
    spec = gallery()['softmax-temperature']
    with pw.sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page(); _two(pg, spec)
            pg.evaluate("() => { const [a, b] = document.querySelectorAll('[data-rupaka]'); window.ma = abhyasaStage.mirror(a); window.mb = abhyasaStage.mirror(b); }")
            pg.click('[data-rupaka]:first-of-type .rk-gate .opts button:nth-child(2)'); pg.click('[data-rupaka]:first-of-type .rk-gate .go')
            got = pg.evaluate("""() => {
              const [a, b] = document.querySelectorAll('[data-rupaka]'), s = ma.snapshot(), v = n => n.querySelector('.rk-gate .verdict');
              mb.apply(s.state, s.gates, s.pick);
              return {s, valid: abhyasaStage.valid({v: 1, t: 'demo', slug: 'x', ...s}), pre: v(a).textContent, aud: v(b).textContent,
                      shown: !v(b).hidden, log: b.rupaka.st.log ?? null};
            }""")
            assert got['s'] == dict(state=dict(logits=[3, 1.5, 1, -1], t=1), gates=dict(hot='done'), pick=dict(hot=1)) and got['valid']
            assert got['pre'].startswith('You said It falls') and got['aud'] == got['pre'] and got['shown'] and got['log'] is None
        finally: b.close()

def test_mirror_details():
    "apply sets only what changed and fires no gate; a gate with no pick shows no verdict; watch waits 50 ms; the audience gate is inert."
    spec = gallery()['softmax-temperature']
    with pw.sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page(); _two(pg, spec)
            got = pg.evaluate("""async () => {
              const [a, b] = document.querySelectorAll('[data-rupaka]'), ma = abhyasaStage.mirror(a), mb = abhyasaStage.mirror(b), r = {};
              let draws = 0, predicts = 0;
              b.rupaka.on(() => draws++); b.addEventListener('rk-predict', () => predicts++);
              r.open = ma.snapshot();   // a gate that is not done is not sent
              mb.apply({t: 1, logits: [3, 1.5, 1, -1]}, {});
              r.same = draws;   // no key changed: no draw
              mb.apply({t: 3, p: 'x', gate: {}, _: 9}, {nope: 'done', hot: 'open'}, {hot: 0});
              r.after = {draws, state: Rupaka.state(b), p: Array.isArray(b.rupaka.st.p), gate: b.rupaka.st.gate.hot};
              const cap = () => [...b.querySelectorAll('[data-rk-after="hot"]')].every(n => n.style.display !== 'none' && !n.hidden);
              r.capBefore = cap();
              mb.apply({}, {hot: 'done'});
              r.capAfter = cap(); r.gate = b.rupaka.st.gate.hot; r.verdict = b.querySelector('.rk-gate .verdict').hidden;
              mb.apply({}, {hot: 'done'}, {hot: 9}); r.far = b.querySelector('.rk-gate .verdict').hidden;   // an index past the options: no verdict
              r.predicts = predicts; r.log = b.rupaka.st.log ?? null;
              r.inert = [...b.querySelectorAll('.rk-gate')].map(n => n.inert); r.presenterInert = [...a.querySelectorAll('.rk-gate')].map(n => n.inert);
              a.querySelector('.rk-gate .opts button').click(); a.querySelector('.rk-gate .go').click();   // the slider shows after the gate
              const seen = []; ma.watch(s => seen.push(s.state.t));
              const inp = a.querySelector('.rk-slider input');
              for (const t of [1.1, 1.2, 1.3, 1.4]) { inp.value = t; inp.dispatchEvent(new Event('input', {bubbles: true})); }
              await new Promise(ok => setTimeout(ok, 20)); r.soon = [...seen];
              await new Promise(ok => setTimeout(ok, 120)); r.late = [...seen];
              return r;
            }""")
            assert got['open'] == dict(state=dict(logits=[3, 1.5, 1, -1], t=1), gates={}, pick={}) and got['same'] == 0
            assert got['after'] == dict(draws=1, state=dict(logits=[3, 1.5, 1, -1], t=3), p=True, gate='open')   # only the input keys; an open gate and an unknown gate do nothing
            assert not got['capBefore'] and got['capAfter'] and got['gate'] == 'done' and got['verdict'] and got['far']
            assert got['predicts'] == 0 and got['log'] is None   # no rk-predict and no log in the audience copy
            assert got['inert'] == [True] and got['presenterInert'] == [False]
            assert got['soon'] == [1.1] and got['late'] == [1.1, 1.4]   # the first change at once, then the last one after 50 ms
        finally: b.close()

def test_mirror_room_copy_has_no_verdict():
    "A room copy with no answer at the gate (as room_spec makes it) closes the gate with a pick but draws no verdict."
    spec = gallery()['softmax-temperature']
    room = {**spec, 'blocks': [{k: v for k, v in x.items() if k != 'answer'} for x in spec['blocks']]}
    with pw.sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page(); pg.set_content(page([spec, room])); pg.add_script_tag(content=JS)
            pg.wait_for_function("document.querySelectorAll('[data-rupaka][data-rk-ready]').length === 2")
            got = pg.evaluate("""() => { const b = document.querySelectorAll('[data-rupaka]')[1], m = abhyasaStage.mirror(b);
              m.apply({}, {hot: 'done'}, {hot: 1}); const v = b.querySelector('.rk-gate .verdict');
              return [b.rupaka.st.gate.hot, v.hidden, v.textContent]; }""")
            assert got == ['done', True, '']
            # after R the answers come: the done gate draws the verdict of the presenter's pick
            got = pg.evaluate("""() => { const b = document.querySelectorAll('[data-rupaka]')[1], m = abhyasaStage.mirror(b);
              m.apply({}, {hot: 'done'}, {hot: 1}); m.reveal({hot: {is: 'It falls'}, nope: {is: 1}});
              const v = b.querySelector('.rk-gate .verdict'); return [v.hidden, v.textContent]; }""")
            assert got[0] is False and got[1].startswith('You said It falls. That is right.')
        finally: b.close()

def test_mirror_answers_only_for_done_gates():
    "The presenter copy gives the answers of its done gates only; the audience copy takes an answer only for a gate that is done there."
    spec = gallery()['softmax-temperature']
    room = {**spec, 'blocks': [{k: v for k, v in x.items() if k != 'answer'} for x in spec['blocks']]}
    with pw.sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page(); pg.set_content(page([spec, room])); pg.add_script_tag(content=JS); pg.evaluate(f'() => {{ {TALK}; }}')
            pg.wait_for_function("document.querySelectorAll('[data-rupaka][data-rk-ready]').length === 2")
            got = pg.evaluate("""() => { const [a, b] = document.querySelectorAll('[data-rupaka]'), ma = abhyasaStage.mirror(a), mb = abhyasaStage.mirror(b), r = {};
              r.before = ma.answers();
              a.querySelector('.rk-gate .opts button').click(); a.querySelector('.rk-gate .go').click();
              r.after = ma.answers();
              mb.reveal(r.after);   // the gate is open here: no answer goes into the copy
              r.open = [b.rupaka.st.gate.hot, 'answer' in b.rupaka.spec.blocks[2]];
              const s = ma.snapshot(); mb.apply(s.state, s.gates, s.pick); mb.reveal(r.after);
              r.verdict = b.querySelector('.rk-gate .verdict').textContent;
              return r; }""")
            assert got['before'] == {} and got['after'] == dict(hot={'is': 'It falls'}) and got['open'] == ['open', False]
            assert got['verdict'].startswith('You said It rises. It is It falls.')
        finally: b.close()

def test_mirror_forgets_the_answers_on_a_new_slide():
    "forget closes the verdicts that reveal drew in the audience copy, and the gate stays done; a later reveal draws the verdict again. No answer goes into the spec."
    spec = gallery()['softmax-temperature']
    room = {**spec, 'blocks': [{k: v for k, v in x.items() if k != 'answer'} for x in spec['blocks']]}
    with pw.sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page(); pg.set_content(page([spec, room])); pg.add_script_tag(content=JS)
            pg.wait_for_function("document.querySelectorAll('[data-rupaka][data-rk-ready]').length === 2")
            got = pg.evaluate("""() => { const b = document.querySelectorAll('[data-rupaka]')[1], m = abhyasaStage.mirror(b), r = {};
              const v = () => (n => n.hidden ? null : n.textContent)(b.querySelector('.rk-gate .verdict')), has = () => 'answer' in b.rupaka.spec.blocks[2];
              m.apply({}, {hot: 'done'}, {hot: 1}); m.reveal({hot: {is: 'It falls'}}); r.shown = [has(), v()];
              m.forget(); r.gone = [has(), v(), b.rupaka.st.gate.hot];
              m.forget(); r.twice = has();   // a second forget does nothing
              m.reveal({hot: {is: 'It falls'}}); r.back = [has(), v()];
              return r; }""")
            assert got['shown'][0] is False and got['shown'][1].startswith('You said It falls. That is right.')   # rupaka never keeps the answer in the spec
            assert got['gone'] == [False, None, 'done'] and got['twice'] is False
            assert got['back'][0] is False and got['back'][1].startswith('You said It falls. That is right.')
        finally: b.close()

def test_mirror_opens_a_gate_again():
    "After Try another in the presenter copy, the snapshot has no done gate and no pick, and the audience copy opens the gate again with no verdict and no answer."
    spec = gallery()['softmax-temperature']
    spec = {**spec, 'blocks': [{**x, 'again': True} if x.get('type') == 'gate' else x for x in spec['blocks']]}
    room = {**spec, 'blocks': [{k: v for k, v in x.items() if k != 'answer'} for x in spec['blocks']]}
    with pw.sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page(); pg.set_content(page([spec, room])); pg.add_script_tag(content=JS); pg.evaluate(f'() => {{ {TALK}; }}')
            pg.wait_for_function("document.querySelectorAll('[data-rupaka][data-rk-ready]').length === 2")
            got = pg.evaluate("""() => { const [a, b] = document.querySelectorAll('[data-rupaka]'), ma = abhyasaStage.mirror(a), mb = abhyasaStage.mirror(b), r = {};
              const sync = () => { const s = ma.snapshot(); mb.apply(s.state, s.gates, s.pick); return s; };
              const after = () => [...b.querySelectorAll('[data-rk-after="hot"]')].some(n => n.style.display !== 'none' && !n.hidden);
              a.querySelector('.rk-gate .opts button:nth-child(2)').click(); a.querySelector('.rk-gate .go').click();
              r.done = sync().gates; mb.reveal(ma.answers());
              r.shut = [b.rupaka.st.gate.hot, !b.querySelector('.rk-gate .verdict').hidden, 'answer' in b.rupaka.spec.blocks[2], after()];
              [...a.querySelectorAll('.rk-gate button')].find(x => x.textContent === 'Try another').click();
              const s = sync(); r.snap = [s.gates, s.pick, ma.answers()];
              r.open = [b.rupaka.st.gate.hot, b.querySelector('.rk-gate .verdict').hidden, 'answer' in b.rupaka.spec.blocks[2], after()];
              a.querySelector('.rk-gate .opts button').click(); a.querySelector('.rk-gate .go').click(); sync();   // a new pick closes it again
              r.again = [b.rupaka.st.gate.hot, b.querySelector('.rk-gate .verdict').hidden];
              return r; }""")
            assert got['done'] == dict(hot='done') and got['shut'] == ['done', True, False, True]
            assert got['snap'] == [{}, {}, {}] and got['open'] == ['open', True, False, False]
            assert got['again'] == ['done', True]   # no answer in the room copy now: the verdict waits for R again
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
                aud.evaluate("() => ch.on('demo', x => m.apply(x.state, x.gates, x.pick))")
                pre.evaluate(f"() => m.watch(s => ch.send({{t: 'demo', slug: {json.dumps(spec['id'])}, ...s}}))")
                # the presenter picks at the gate; the talk page settles it and files nothing
                pre.click('.rk-gate .opts button:nth-child(2)'); pre.click('.rk-gate .go')
                aud.wait_for_function("() => host.rupaka.st.gate.hot === 'done'")
                v = "() => host.querySelector('.rk-gate .verdict').textContent"
                assert aud.evaluate(v).startswith('You said It falls') and aud.evaluate(v) == pre.evaluate(v)   # the audience sees the presenter's pick
                pre.evaluate("() => { const i = host.querySelector('.rk-slider input'); i.value = 2.5; i.dispatchEvent(new Event('input', {bubbles: true})); }")
                aud.wait_for_function("() => host.rupaka.st.t === 2.5")
                assert aud.evaluate("() => host.querySelector('.rk-caption').textContent") == pre.evaluate("() => host.querySelector('.rk-caption').textContent")
                assert aud.evaluate("() => [predicts, host.querySelector('.rk-gate').inert, host.rupaka.st.log ?? null]") == [[], True, None]
                assert pre.evaluate("() => [predicts, got.length]") == [['hot'], 0]   # one catch in the presenter window; nothing came back
            finally: b.close()
    finally: srv.should_exit = True; th.join(5)
