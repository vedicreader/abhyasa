"The guide block: the Explain button and the box on each page, the figure labels, the three tiers, and the explainer video."
import json, pytest

PNG = b'\x89PNG\r\n\x1a\n' + b'\0' * 64
LABELS = dict(labels=[dict(text='a', box=[90, 400, 160, 500]), dict(text='b', box=[480, 880, 540, 960])])

def test_each_page_has_the_explain_button(mk):
    t = mk().get('/').text
    assert 'id="guide-go"' in t and '>Explain<' in t and 'id="guide-box"' in t and 'guide.js' in t
    assert 'aria-label="What do you not understand?"' in t

def test_figure_labels_are_found_once(mk, fake):
    fake.rules['You find the text labels'] = LABELS
    cl = mk()
    r = cl.post('/guide/figure?alt=A+right+triangle', content=PNG)
    assert r.json()['labels'] == {'a': [90, 400, 160, 500], 'b': [480, 880, 540, 960]}
    n = sum('You find the text labels' in sp for _, sp in fake.calls)
    assert cl.post('/guide/figure', content=PNG).json()['labels']['b'] == [480, 880, 540, 960]
    assert sum('You find the text labels' in sp for _, sp in fake.calls) == n == 1

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
    import abhyasa.guide, abhyasa.blocks.guide.app as ga
    from abhyasa.guide import Withheld
    monkeypatch.setattr(abhyasa.guide, 'pii_policy', lambda: ('refuse', False))
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
    for path, data in ((f'/guide/video/{slug}', dict(url='https://youtu.be/abc123def45')), (f'/guide/video/{slug}/find', {})):
        r = cl.post(path, data=data)
        assert r.status_code == 200 and WITHHELD in r.text, path

def test_figure_route_takes_only_images(mk):
    assert mk().post('/guide/figure', content=b'<svg onload=alert(1)>').status_code == 415

GUIDE_JS = __import__('pathlib').Path(__file__).parents[2]/'abhyasa/blocks/guide/guide.js'

def tex_parts(tex):
    import shutil, subprocess
    if not shutil.which('node'): pytest.skip('node is not installed')
    code = f"const g = require({json.dumps(str(GUIDE_JS))}); console.log(JSON.stringify(g.texParts({json.dumps(tex)}, 1)))"
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

def test_ask_streams_a_board(mk, fake):
    fake.rules['Tier: tutor'] = '\n'.join(json.dumps(o) for o in [dict(op='v', n=1, sure=0.9), dict(op='step', say='This is the passage.'), dict(op='box', at='passage')])
    ctx = dict(page='/walk/x/step/1', anchors=[dict(id='passage', kind='passage', text='Some text.')])
    r = mk().post('/guide/ask', json=dict(said="I don't get this", ctx=ctx))
    assert r.headers['content-type'].startswith('text/event-stream')
    evs = [json.loads(l[6:]) for l in r.text.splitlines() if l.startswith('data: ')]
    b = evs[-1]['board']
    assert b['tier'] == 'tutor' and b['steps'][0]['strokes'] == [dict(op='box', at='passage')]

def test_ask_needs_words(mk):
    assert mk().post('/guide/ask', json=dict(said='  ', ctx={})).status_code == 400

def test_hyper_e_and_hold_to_talk():
    "Hyper+E needs all four modifiers; a hold of 300 ms or more talks through the voice block's mic, a tap opens the box."
    js = GUIDE_JS.read_text()
    assert "e.metaKey && e.altKey && e.ctrlKey && e.shiftKey" in js and "e.code !== 'KeyE'" in js
    assert 'HOLD = 300' in js and "getElementById('mic-float')" in js and 'abhyasaMic(' in js
    assert "addEventListener('keyup'" in js and '/^(Meta|Alt|Control|Shift)/' in js   # macOS sends no keyup for E while ⌘ is down

def test_keys_table_names_the_guide_key():
    from abhyasa.core.keys import KEYS
    assert ('Guide', '⌃⌥⇧⌘E', 'Explain this: hold to talk, tap to type (Caps+E)') in KEYS

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
