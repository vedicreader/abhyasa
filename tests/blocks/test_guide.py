"The guide block: the Explain button and the box on each page, the figure labels, the three tiers, and the explainer video."
import json, re, pytest

PNG = b'\x89PNG\r\n\x1a\n' + b'\0' * 64
LABELS = dict(labels=[dict(text='a', box=[90, 400, 160, 500]), dict(text='b', box=[480, 880, 540, 960])])

def test_figure_labels_are_found_once(mk, fake):
    fake.rules['You find the text labels'] = LABELS
    cl = mk()
    r = cl.post('/guide/figure?alt=A+right+triangle', content=PNG)
    assert r.json()['labels'] == {'a': [90, 400, 160, 500], 'b': [480, 880, 540, 960]}
    n = sum('You find the text labels' in sp for _, sp in fake.calls)
    assert cl.post('/guide/figure', content=PNG).json()['labels']['b'] == [480, 880, 540, 960]
    assert sum('You find the text labels' in sp for _, sp in fake.calls) == n == 1

def test_a_failed_vision_call_is_not_kept(mk, fake):
    "The first vision call fails, so the route keeps no labels: the next post of the same figure asks again and gets the labels."
    tries = []
    def flaky(p, sp):
        tries.append(p)
        if len(tries) == 1: raise RuntimeError('the model timed out')
        return LABELS
    fake.rules['You find the text labels'] = flaky
    cl = mk()
    assert cl.post('/guide/figure', content=PNG + b'flaky').json()['labels'] == {}
    assert cl.post('/guide/figure', content=PNG + b'flaky').json()['labels'] == {'a': [90, 400, 160, 500], 'b': [480, 880, 540, 960]}
    assert len(tries) == 2

def test_an_empty_first_result_is_not_kept(mk, fake):
    "While no figure has labels, an empty reply is not kept: it can come from a route that lost the picture. So the next post asks again."
    from abhyasa.settings import cfg_dir
    (cfg_dir()/'guide-figures.json').unlink(missing_ok=True)
    replies = [dict(labels=[]), LABELS]
    fake.rules['You find the text labels'] = lambda p, sp: replies.pop(0)
    cl = mk()
    assert cl.post('/guide/figure', content=PNG + b'empty').json()['labels'] == {}
    assert cl.post('/guide/figure', content=PNG + b'empty').json()['labels'] == {'a': [90, 400, 160, 500], 'b': [480, 880, 540, 960]}
    assert replies == []

def test_a_route_that_loses_pictures_says_so(mk, monkeypatch):
    "When the route of figure labels drops the picture, the figure route makes no call and its note names the model and the route."
    import abhyasa.guide as G
    monkeypatch.setattr(G, 'vision_ask', lambda ask, name='', job='': None)
    monkeypatch.setattr('abhyasa.blocks.guide.app.vision_ask', lambda ask, name='', job='': None)
    monkeypatch.setattr('abhyasa.blocks.guide.app.vision_why', lambda ask, name='': 'GPT-6.1 Sol does not get pictures on this route.')
    r = mk().post('/guide/figure', content=PNG + b'lost').json()
    assert r['labels'] == {} and r['note'] == 'GPT-6.1 Sol does not get pictures on this route.'

def test_figure_alt_passes_the_guard(mk, fake):
    "A secret in the alt text of a figure never reaches the vision call: the route sends the alt through `guard` first."
    fake.rules['You find the text labels'] = LABELS
    secret = 'sk-test1234567890abcdefXYZ'
    assert mk().post(f'/guide/figure?alt=A+triangle+{secret}', content=PNG + b'alt').status_code == 200
    ps = [p for p, sp in fake.calls if 'You find the text labels' in sp]
    assert ps and all(secret not in p and secret not in sp for p, sp in fake.calls) and '[SECRET]' in ps[-1]

WITHHELD = 'The guide did not send this, because your privacy setting withholds it. Change it in Settings.'

def test_each_route_answers_a_withheld_text_plainly(mk, fake, lr, monkeypatch):
    "With `cli.pii` refuse, the guard withholds personal data: each guide route answers with one plain line, not a 500."
    import ramabana.guard, abhyasa.blocks.guide.app as ga
    from abhyasa.guide import Withheld
    monkeypatch.setattr(ramabana.guard, 'setting', lambda k, d=None: 'refuse' if k == 'cli.pii' else d)
    fake.rules['You find the text labels'] = LABELS
    cl, pii = mk(), 'Mail jane.doe@example.com or call 415-555-0134'
    r = cl.post(f'/guide/figure?alt={pii}', content=PNG + b'pii')
    assert r.status_code == 403 and r.json() == dict(error=WITHHELD, labels={})
    assert not any('jane.doe' in p for p, sp in fake.calls)
    r = cl.post('/guide/ask', json=dict(said=f"I don't get this, {pii}", ctx={}))
    assert r.status_code == 200 and json.loads(r.text.strip().split('data: ')[-1]) == dict(error=WITHHELD)
    def withhold(*a, **kw): raise Withheld('personal data')
    monkeypatch.setattr(ga, 'file_video', withhold); monkeypatch.setattr(ga, 'find_explainer', withhold)
    slug = lr.concepts()[0].slug
    for path, data, msg in ((f'/guide/video/{slug}', dict(url='https://youtu.be/abc123def45'), WITHHELD), (f'/guide/video/{slug}/find', {}, ga.NO_QUERY)):
        r = cl.post(path, data=data)
        assert r.status_code == 200 and msg in r.text, path   # a web query that may not go says so, and asks for a link

def test_figure_route_takes_only_images(mk):
    assert mk().post('/guide/figure', content=b'<svg onload=alert(1)>').status_code == 415

GUIDE_JS = __import__('pathlib').Path(__file__).parents[2]/'abhyasa/blocks/guide/guide.js'
TEX_JS = __import__('pathlib').Path(__file__).parents[2]/'abhyasa/core/texparts.js'

def tex_parts(tex):
    import shutil, subprocess
    if not shutil.which('node'): pytest.skip('node is not installed')
    code = f"const g = require({json.dumps(str(TEX_JS))}); console.log(JSON.stringify(g.texParts({json.dumps(tex)}, 1)))"
    return json.loads(subprocess.run(['node', '-e', code], capture_output=True, text=True, check=True).stdout)

def test_formula_parts_of_ddpm():
    "The page marks the parts of the DDPM formula, so the board can point at alpha bar, its root and the noise share."
    marked, parts = tex_parts(r'q(\mathbf{x}_t\mid\mathbf{x}_0)=\mathcal{N}(\mathbf{x}_t;\sqrt{\bar\alpha_t}\mathbf{x}_0,(1-\bar\alpha_t)\mathbf{I})')
    texs = [t for t, _ in parts]
    for t in (r'\bar\alpha_t', r'\sqrt{\bar\alpha_t}', r'\mathbf{x}_0', r'(1-\bar\alpha_t)', r'\mathbf{I}'): assert t in texs, t
    assert marked.count(r'\htmlId{') == len(parts) and len({i for _, i in parts}) == len(parts)
    assert r'\htmlId{g-1-' in marked and r'\mid' in marked and r'\htmlId{g-1-0}{q}' in marked

def test_formula_parts_keep_accents_whole():
    "An accent and its symbol are one part: no id inside the bar."
    marked, parts = tex_parts(r'\hat{y} = \frac{a}{b}')
    assert [t for t, _ in parts][:1] == [r'\hat{y}'] and r'\hat{\htmlId' not in marked and r'\frac{\htmlId' in marked

def test_texparts_is_one_shared_module(mk):
    "core/texparts.js gives window.abhyasaTex and the node module, with the one KaTeX trust rule; every page loads it before guide.js, which needs it."
    import shutil, subprocess
    if not shutil.which('node'): pytest.skip('node is not installed')
    code = (f"const t = require({json.dumps(str(TEX_JS))}); const w = {{}}; global.window = w; delete require.cache[require.resolve({json.dumps(str(TEX_JS))})];"
            f"require({json.dumps(str(TEX_JS))}); console.log(JSON.stringify([Object.keys(t), Object.keys(w.abhyasaTex),"
            " t.trust({command: '\\\\htmlId', id: 'g-1-0'}), t.trust({command: '\\\\htmlId', id: 'x'}), t.trust({command: '\\\\href', id: 'g-1-0'}),"
            " t.texWrap('a+b', 2, [])]))")
    keys, wkeys, ok, bad_id, bad_cmd, wrapped = json.loads(subprocess.run(['node', '-e', code], capture_output=True, text=True, check=True).stdout)
    assert keys == wkeys == ['texParts', 'texAtoms', 'texWrap', 'trust'] and ok and not bad_id and not bad_cmd and wrapped.startswith(r'\htmlId{g-2-0}{a}')
    t = mk().get('/').text
    assert t.index('/assets/texparts.js') < t.index('/assets/guide.js')

def test_ask_streams_a_board(mk, fake):
    fake.rules['Tier: tutor'] = '\n'.join(json.dumps(o) for o in [dict(op='v', n=1, sure=0.9), dict(op='step', say='This is the passage.'), dict(op='box', at='passage')])
    ctx = dict(page='/walk/x/step/1', anchors=[dict(id='passage', kind='passage', text='Some text.')])
    r = mk().post('/guide/ask', json=dict(said="I don't get this", ctx=ctx))
    assert r.headers['content-type'].startswith('text/event-stream')
    evs = [json.loads(l[6:]) for l in r.text.splitlines() if l.startswith('data: ')]
    b = evs[-1]['board']
    assert b['tier'] == 'tutor' and b['steps'][0]['strokes'] == [dict(op='box', at='passage')]

def test_ask_streams_each_step_before_the_board(mk, fake):
    "A model that streams: each step of a sure tutor board is an event as soon as it is whole, and the whole board comes last."
    reply = '\n'.join(json.dumps(o) for o in [dict(op='v', n=1, sure=0.9), dict(op='step', say='This is the passage.'), dict(op='box', at='passage'),
                                              dict(op='step', say='Read it again.'), dict(op='underline', at='passage')])
    fake.rules['Tier: tutor'] = reply
    fake.stream = lambda p, sp='': (fake(p, sp)[i:i + 9] for i in range(0, len(reply), 9))
    ctx = dict(page='/walk/x/step/1', anchors=[dict(id='passage', kind='passage', text='Some text.')])
    evs = [json.loads(l[6:]) for l in mk().post('/guide/ask', json=dict(said="I don't get this", ctx=ctx)).text.splitlines() if l.startswith('data: ')]
    steps, b = [e for e in evs if 'step' in e], evs[-1]['board']
    assert [list(e) for e in evs] == [['wait', 'state', 'where']] + [['step', 'k', 'tier', 'point']] * 2 + [['board', 'point']]   # first: who gets the question
    assert [(e['k'], e['tier']) for e in steps] == [(1, 'tutor'), (2, 'tutor')] and [e['step'] for e in steps] == b['steps']
    assert b['steps'][1]['strokes'] == [dict(op='underline', at='passage')]

def test_warm_starts_the_guide_job_at_most_once_in_a_while(mk, monkeypatch):
    "Hyper+E posts to the warm route. The route starts the backend of the guide job only, and a second post soon after does nothing."
    from abhyasa.llm import Router
    seen = []
    monkeypatch.setattr(Router, 'warm', lambda self, jobs=None: seen.append(jobs), raising=False)
    cl = mk()
    assert [cl.post('/guide/warm').status_code for _ in range(3)] == [204] * 3
    assert seen == [['guide']]
    assert 'data-warm="/guide/warm"' in cl.get('/').text

def test_ask_needs_words(mk):
    assert mk().post('/guide/ask', json=dict(said='  ', ctx={})).status_code == 400

def test_hyper_e_and_hold_to_talk():
    "Hyper+E needs all four modifiers, and the hold ends on the keyup of a modifier: macOS sends no keyup for E while ⌘ is down."
    js = GUIDE_JS.read_text()
    assert "e.metaKey && e.altKey && e.ctrlKey && e.shiftKey" in js and "e.code !== 'KeyE'" in js
    assert "addEventListener('keyup'" in js and '/^(Meta|Alt|Control|Shift)/' in js   # macOS sends no keyup for E while ⌘ is down

# --- the explainer video ---------------------------------------------------------------------------------------------
CUES = [dict(start=0.0, end=4.0, text='Today we look at ranks.'), dict(start=42.0, end=48.0, text='A rank is the place of an item in the list.'),
        dict(start=48.0, end=52.0, text='The first item has rank one.')]

@pytest.fixture
def yt(monkeypatch):
    "fossick with no network: `read_yt` and `search_yt` give fixed videos, and the URL check passes. Each call is kept."
    calls = []
    def read_yt(url, force=False, cues=False, **kw):
        calls.append(('read', url))
        v = dict(title='Ranks in two minutes', channel='Maths Room', description='', duration=120, upload_date='20260101',
                 source=' '.join(c['text'] for c in CUES) + f' ({url})')
        return {**v, 'cues': CUES} if cues else v
    def search_yt(q, n=10, **kw):
        calls.append(('search', q))
        return [dict(id='abc123def45', title='Ranks in two minutes', channel='Maths Room', duration=120)]
    monkeypatch.setattr('fossick.core.read_yt', read_yt)
    monkeypatch.setattr('fossick.search_yt', search_yt)
    monkeypatch.setattr('abhyasa.sources.public_url', lambda u: u)
    return calls

def test_paste_a_video_on_a_concept(mk, lr, yt):
    cl = mk()
    assert 'Paste a YouTube link' in cl.get('/c/ranking').text
    t = cl.post('/guide/video/ranking', data=dict(url='https://youtu.be/abc123def45?si=x')).text
    assert 'https://www.youtube-nocookie.com/embed/abc123def45?enablejsapi=1&amp;rel=0' in t and 'autoplay' not in t
    assert 'id="guide-video"' in t and 'data-vid="abc123def45"' in t and 'Maths Room · Ranks in two minutes' in t
    assert '<summary class="mute">Transcript</summary>' in t and 'data-t="42.0"' in t
    p = lr.concept('ranking').provenance[-1]
    assert (p['src'], p['vid'], p['channel']) == ('video', 'abc123def45', 'Maths Room')
    assert 'data-vid="abc123def45"' in cl.get('/c/ranking').text

def test_a_bad_link_files_nothing(mk, lr, yt):
    t = mk().post('/guide/video/ranking', data=dict(url='https://example.com/watch?v=abc123def45')).text
    assert 'This is not a YouTube link.' in t and not yt and not any(p.get('src') == 'video' for p in lr.concept('ranking').provenance or ())

def test_the_tutor_finds_a_video(mk, lr, yt):
    t = mk().post('/guide/video/ranking/find').text
    assert 'data-vid="abc123def45"' in t and yt[0] == ('search', 'Ranking ml explained')

def test_remove_the_video(mk, lr, yt):
    cl = mk()
    cl.post('/guide/video/ranking', data=dict(url='abc123def45'))
    t = cl.post('/guide/video/ranking/drop').text
    assert 'The video is gone' in t and 'guide-video"' not in t and 'Find a video' in t

def test_the_walk_step_shows_the_video(mk, lr, yt):
    from abhyasa.core.hooks import HOOKS
    mk().post('/guide/video/ranking', data=dict(url='abc123def45'))
    f = next(f for f in HOOKS['step_needs'] if 'guide' in f.__module__)   # the hook of the guide; the walk block calls it with the step
    assert 'youtube-nocookie.com/embed/abc123def45' in to_xml(f(None, 0, lr.concept('ranking')))
    assert f(None, 0, lr.concept('reciprocal-rank-fusion')) is None and f(None, 0, None) is None

def to_xml(p):
    from fasthtml.common import to_xml as x
    return x(p)

def test_ask_points_at_a_moment_in_the_video(mk, lr, fake, yt):
    "The cues come from the vault, not from the page. The board seeks to the start of the cue and quotes it with its link."
    cl = mk()
    cl.post('/guide/video/ranking', data=dict(url='abc123def45'))
    fake.rules['Tier: tutor'] = '\n'.join(json.dumps(o) for o in [dict(op='v', n=1, sure=0.9), dict(op='step', say='The video says what a rank is.'),
                                                                  dict(op='video_at', t=45, quote='the place of an item in the list')])
    ctx = dict(page='/c/ranking', anchors=[dict(id='title', kind='title', text='Ranking')], video=dict(id='abc123def45', cues=[[0, 'made up words']]))
    r = cl.post('/guide/ask', json=dict(said="I don't get rank", ctx=ctx))
    b = [json.loads(l[6:]) for l in r.text.splitlines() if l.startswith('data: ')][-1]['board']
    assert b['steps'][0]['strokes'] == [dict(op='video_at', t=42.0, quote='the place of an item in the list', link='https://www.youtube.com/watch?v=abc123def45&t=42s')]
    assert b['sources'] == [dict(n=1, title='Maths Room · Ranks in two minutes', url='https://www.youtube.com/watch?v=abc123def45', label='video', quoted=True)]
    p = next(p for p, sp in fake.calls if 'Tier: tutor' in p)
    assert '[42 s] A rank is the place of an item in the list.' in p and 'made up words' not in p

def test_a_video_that_is_not_filed_gives_no_cues(mk, fake, yt):
    fake.rules['Tier: tutor'] = '\n'.join(json.dumps(o) for o in [dict(op='v', n=1, sure=0.9), dict(op='step', say='One.'), dict(op='video_at', t=1, quote='Today we look at ranks')])
    r = mk().post('/guide/ask', json=dict(said='Explain', ctx=dict(video=dict(id='zzz123def45'), anchors=[dict(id='title', kind='title', text='x')])))
    b = [json.loads(l[6:]) for l in r.text.splitlines() if l.startswith('data: ')][-1]['board']
    assert b['steps'][0]['strokes'] == [] and b['sources'] == []

# --- stop: the page stops reading, and the model stream closes ------------------------------------------------------------
def serve(app):
    "Run `app` on a free port in a thread. Gives the base URL and a function that stops it."
    import socket, threading, time, uvicorn
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='error'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    while not srv.started: time.sleep(.05)
    def end(): srv.should_exit = True; th.join(5)
    return f'http://127.0.0.1:{port}', end

def test_a_newer_question_does_not_wait_for_the_older_stream(mk, fake):
    """The first question streams slowly and holds the backend lock, as `ramabana_stream` does. The page reads its first event and
    stops. The stream closes at its next chunk, so the second question gets its board at once, not after the rest of the first."""
    import threading, time, httpx
    reply = '\n'.join(json.dumps(o) for o in [dict(op='v', n=1, sure=0.9), dict(op='step', say='This is the passage.'), dict(op='box', at='passage'),
                                              dict(op='step', say='Read it again.'), dict(op='underline', at='passage')] + [dict(op='step', say='More.')] * 4)
    backend, calls, shut = threading.Lock(), [], []
    def stream(p, sp=''):
        with backend:
            slow = not calls; calls.append(p)
            try:
                for i in range(0, len(reply), 9):
                    if slow: time.sleep(.4)
                    yield reply[i:i + 9]
            finally: shut.append(time.monotonic())
    fake.rules['Tier: tutor'] = reply
    fake.stream = stream
    ctx = dict(page='/walk/x/step/1', anchors=[dict(id='passage', kind='passage', text='Some text.')])
    base, end = serve(mk().app)
    try:
        with httpx.Client(base_url=base, timeout=30) as cl:
            with cl.stream('POST', '/guide/ask', json=dict(said='first', ctx=ctx)) as r:
                first = next(l for l in r.iter_lines() if l.startswith('data: '))
            t0 = time.monotonic()
            evs = [json.loads(l[6:]) for l in cl.post('/guide/ask', json=dict(said='second', ctx=ctx)).text.splitlines() if l.startswith('data: ')]
            took = time.monotonic() - t0
    finally: end()
    assert first and 'board' in evs[-1] and len(evs[-1]['board']['steps']) == 6
    assert took < 3 and shut and shut[0] - t0 < 2, (took, shut)   # the first stream closed soon after the page stopped reading

# --- never caught unaware ---------------------------------------------------------------------------------------------------
def test_the_first_event_says_who_gets_the_question(mk, fake):
    "Before the model call, the route says what the guide does and where the text goes. A test model has no name: it is the tutor, hosted."
    fake.rules['Tier: tutor'] = '\n'.join(json.dumps(o) for o in [dict(op='v', n=1, sure=0.9), dict(op='step', say='One.'), dict(op='box', at='passage')])
    evs = [json.loads(l[6:]) for l in mk().post('/guide/ask', json=dict(said='what', ctx=dict(anchors=[dict(id='passage', kind='passage', text='x')]))).text.splitlines()
           if l.startswith('data: ')]
    assert evs[0] == dict(wait='Asks the tutor. It gets your question and the page text.', state='asking', where='hosted')

def test_a_routed_model_is_named_with_where_it_runs(mk, monkeypatch):
    "The page names the routed model of the guide and of a figure, with on this Mac or hosted and the company, and the speech engine."
    import html, re
    from abhyasa.llm import Router
    monkeypatch.setattr('abhyasa.blocks.guide.app.guide_ask', lambda ask: type('A', (), {'model': 'claude/sonnet'})())
    info = json.loads(html.unescape(re.search(r"data-info='([^']*)'", mk().get('/').text).group(1)))
    assert info['model'] == dict(model='Claude Sonnet', where='hosted', who='Anthropic')
    assert info['speech'] == dict(model='Gemma', where='on this Mac', who='') and info['voice'] is True

def test_a_saved_web_page_can_be_undone(mk, fake, lr, monkeypatch):
    "The web tier files a page in the vault and links it to the concept. The route says so with an Undo route, and Undo takes both away."
    import abhyasa.research, abhyasa.settings
    text = 'Home. A rank is the place of an item in a list that is sorted by score.'
    monkeypatch.setattr(abhyasa.research, 'web_search', lambda q, n: [dict(title='Ranks', href='https://example.org/ranks')])
    monkeypatch.setattr(abhyasa.research, 'web_fetch', lambda u: abhyasa.research.AttrDict(url=u, title='Ranks explained', text=text))
    on = abhyasa.settings.val
    monkeypatch.setattr(abhyasa.settings, 'val', lambda k: True if k == 'research.on' else on(k))
    weak = '\n'.join(json.dumps(o) for o in [dict(op='v', n=1, sure=0.3), dict(op='step', say='One.'), dict(op='box', at='title')])
    quoted = '\n'.join(json.dumps(o) for o in [dict(op='v', n=1, sure=0.8), dict(op='step', say='One.', src=1, quote=text[6:]), dict(op='box', at='title')])
    fake.rules.update({'Tier: tutor': weak, 'Tier: vault': weak, 'Tier: web': quoted, 'Return JSON: {"passage"': dict(passage=text[6:])})
    cl = mk()
    ctx = dict(page='/c/ranking', slug='ranking', concept='Ranking', anchors=[dict(id='title', kind='title', text='Ranking')])
    evs = [json.loads(l[6:]) for l in cl.post('/guide/ask', json=dict(said='what is a rank', ctx=ctx)).text.splitlines() if l.startswith('data: ')]
    states = [e.get('state') for e in evs if 'wait' in e]
    assert 'searching' in states and 'saving' in states and evs[-1]['board']['tier'] == 'web'
    q = next(e for e in evs if e.get('query'))
    assert q['wait'] == f'Searches the web for: "{q["query"]}"' and q['where'] == 'hosted'
    s = next(e['saved'] for e in evs if 'saved' in e)
    assert (s['title'], s['url']) == ('Ranks explained', 'https://example.org/ranks') and s['undo'].startswith('/guide/undo/')
    assert any(p.get('src') == 'web' for p in lr.concept('ranking').provenance)
    assert cl.post(s['undo']).text == 'The guide took Ranks explained out of your vault.'
    assert not any(p.get('src') == 'web' for p in lr.concept('ranking').provenance or ())
    assert cl.post(s['undo']).text == 'There is nothing to undo.'

def test_voice_off_is_kept(mk):
    from abhyasa.settings import val
    cl = mk()
    assert cl.post('/guide/voice', data=dict(on='0')).status_code == 204 and val('guide.voice') is False
    cl.post('/guide/voice', data=dict(on='1')); assert val('guide.voice') is True

def test_the_point_look_goes_to_the_page_and_the_events(mk, fake):
    "The page script and the step and board events of the ask route carry the setting guide.point, so the page and the Mac overlay draw the same look."
    from abhyasa.settings import set_val
    fake.rules['Tier: tutor'] = '\n'.join(json.dumps(o) for o in [dict(op='v', n=1, sure=0.9), dict(op='step', say='This is the passage.'), dict(op='point', at='passage')])
    fake.stream = lambda p, sp='': iter([fake(p, sp)])
    ctx = dict(page='/walk/x/step/1', anchors=[dict(id='passage', kind='passage', text='Some text.')])
    cl = mk()
    set_val('guide.point', 'dot')
    try:
        info = json.loads(re.search(r"data-info='([^']*)'", cl.get('/').text).group(1))
        evs = [json.loads(l[6:]) for l in cl.post('/guide/ask', json=dict(said="I don't get this", ctx=ctx)).text.splitlines() if l.startswith('data: ')]
        assert info['point'] == 'dot' and [e['point'] for e in evs if 'step' in e or 'board' in e] == ['dot', 'dot']
    finally: set_val('guide.point', 'tick')

def test_page_info_names_the_new_guide_model_after_a_save(mk, monkeypatch):
    "The page says which model the guide asks. A save of a model on the Settings page shows the new name on the next page, with no wait of INFO_EVERY."
    import html, json, re
    from types import SimpleNamespace
    from abhyasa.settings import val, set_val
    import abhyasa.blocks.guide.app as g
    monkeypatch.setattr(g, 'guide_ask', lambda ask: SimpleNamespace(model=val('models.guide')))
    info = lambda: json.loads(html.unescape(re.search(r"data-info='([^']*)'", cl.get('/').text)[1]))['model']['model']
    try:
        cl = mk()
        assert cl.post('/settings/model', data=dict(task='guide', model='anthropic/claude-sonnet-4-5')).status_code == 200
        first = info()
        assert cl.post('/settings/model', data=dict(task='guide', model='openai/gpt-5')).status_code == 200
        assert info() != first and 'GPT' in info().upper()
    finally: set_val('models.guide', '')
