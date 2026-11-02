"The helpers of the spec test (`test_flows.py`): the spec, a parsed page, the page id of an app path, and the builder of each state."
import json, re, time
from pathlib import Path
from urllib.parse import urlsplit
import lxml.html
from fastcore.basics import AttrDict
from starlette.routing import Match
from abhyasa.path import walk_from_topic
from abhyasa.models import Fake
from abhyasa.learner import job_start
from walk_data import walk

SPEC = json.loads((Path(__file__).parent/'data'/'flows.json').read_text())

def check_spec(spec):
    "Each page has a path, states, entries and exits; each exit is a page id or `nav`; each step of a workflow names a page."
    pages = spec['pages']
    for pid, v in pages.items():
        assert {'path', 'states', 'entries', 'exits'} <= set(v), pid
        assert all(x.split()[0] in (*pages, 'nav') for x in v['exits']), (pid, v['exits'])
    for wid, w in spec['workflows'].items():
        assert all(s['page'].split()[0] in pages or s['page'].startswith('any') for s in w['steps']), wid

def _pat(path): return re.compile('^' + re.sub(r'\{\w+\}', '[^/?#]+', path.replace('{i}', r'\d+')) + '/?$')

ROUTES = [(pid, _pat(v['path'])) for pid, v in SPEC['pages'].items()] + [(pid, _pat(p)) for pid, v in SPEC['pages'].items() for p in (v.get('tabs') or {}).values() if p.startswith('/')]

def route_of(href):
    "The page id of an app link, or None for a link to a part, a file or a route that is not a page."
    u = urlsplit(href)
    if u.scheme or u.netloc or not u.path.startswith('/'): return None
    return next((pid for pid, p in ROUTES if p.match(u.path)), None)

def norm(s): return ' '.join((s or '').split())

def has_route(app, path, method):
    "Whether `app` has a route for `method` on `path`."
    scope = dict(type='http', path=urlsplit(path).path, method=method.upper(), root_path='')
    return any(r.matches(scope)[0] == Match.FULL for r in app.routes)

class Pg:
    "A page as a person sees it: the parts, the actions, the visible text, the links of the page body, and the main buttons."
    def __init__(self, cl, url, html):
        self.cl, self.url, self.doc = cl, url, lxml.html.fromstring(html)
        for el in self.doc.xpath('//*[@hx-get][@hx-trigger="load"]'):   # what a browser loads at once, such as the check card
            r = cl.get(el.get('hx-get'))
            if r.status_code == 200 and r.text.strip():
                for x in lxml.html.fragments_fromstring(r.text):
                    if isinstance(x, str): el.text = (el.text or '') + x
                    else: el.append(x)
        shown = lambda e: not e.xpath('ancestor-or-self::*[@hidden]')
        self.parts = [e.get('data-part') for e in self.doc.xpath('//*[@data-part]') if shown(e)]
        self.acts = {}
        for e in self.doc.xpath('//*[@data-act]'):
            if shown(e): self.acts.setdefault(e.get('data-act'), []).append(e)
        body = self.doc.find('.//body')
        body = body if body is not None else self.doc
        for e in body.xpath('.//script|.//style|.//template'): e.drop_tree()
        self.text = norm(body.text_content())
        main = self.doc.find('.//main')
        self.links = [a.get('href') for a in (main if main is not None else self.doc).xpath('.//a[@href][not(ancestor::*[contains(@class, "crumbs")])]')]
        self.primary = [e for e in self.doc.xpath('//*[@data-main]') if shown(e)]   # `Primary` marks it; `Page` takes the mark off the ones that it demotes

    def has(self, x, ctx=None):
        kind, _, v = x.partition(':')
        word = v.split()[0] if v.split() else ''
        if kind == 'part': return word in self.parts
        if kind == 'act': return word in self.acts
        if kind == 'one': return self.parts.count(word) == 1
        if kind == 'label': return norm(v.format(**(ctx or {}))) in self.text
        raise AssertionError(f'the spec item {x!r} is not part:, act:, one: or label:')

    def works(self, act):
        "Whether each element of `act` goes somewhere: a link that answers, or a form or an htmx call that names a route of the app."
        for e in self.acts[act]:
            if not self._works(e): return False
        return True

    def _works(self, e):
        app = self.cl.app
        for k in ('hx-post', 'hx-get'):
            for x in [e, *e.xpath('ancestor::*'), *e.xpath('.//*')]:
                if x.get(k): return has_route(app, x.get(k), k[3:])
        f = next(iter(e.xpath('ancestor-or-self::form') or e.xpath('.//form')), None)
        if f is not None and f.get('action'): return has_route(app, f.get('action'), f.get('method') or 'get')
        if e.tag == 'a' and e.get('href'):
            r = self.cl.get(e.get('href'), follow_redirects=False)
            return r.status_code == 200 or 300 <= r.status_code < 400
        return False

def page(cl, url):
    "GET `url`, check that it answers 200, and parse it."
    r = cl.get(url)
    assert r.status_code == 200, (url, r.status_code)
    return Pg(cl, url, r.text)

# --- the data of each state --------------------------------------------------------------------------------------------

STEP = dict(way='words', kind='short', depth=2)

def done(lr, jid, *ix, outcome='solid'):
    "Close steps `ix` of walk `jid` with `outcome`, and raise the floor of their concepts, as a check does."
    j = lr.journey(jid)
    for i in ix:
        lr.walk_step(jid, i, done=dict(outcome=outcome, at=time.time()))
        lr.update(j.steps[i]['slug'], floor=4, seen=1, last=time.time(), stability=5., due=time.time() + 5 * 86400)
    return lr.journey(jid)

def goal_walk(lr, done_=0):
    "A goal walk of three ideas, as the Start box makes it, with the first `done_` ideas done."
    for n, pre in (('Noise', []), ('Denoise', ['noise']), ('Sample', ['denoise'])): lr.put(n, f'{n} a picture.', 'ml', prereqs=pre)
    lr.put_journey(dict(id='gw', title='Diffusion for comics', goal='Fine-tune diffusion for comics', mode='walk', source=None, started=time.time(), created=1.,
                        steps=[dict(slug=s, status='todo', check=dict(STEP)) for s in ('noise', 'denoise', 'sample')], chips=[], chip_counts={}))
    return done(lr, 'gw', *range(done_)) if done_ else lr.journey('gw')

def due(lr, *slugs):
    "Make the concepts `slugs` seen and due for a review now."
    for s in slugs: lr.update(s, floor=2, seen=1, last=time.time() - 9 * 86400, stability=1., due=time.time() - 60)

def two_walks(lr):
    "Walk A and walk B of two ideas each, both started; B was used last."
    now = time.time()
    for jid, at in (('wa', now - 600), ('wb', now - 60)):
        lr.put_journey(dict(id=jid, title=f'Walk {jid[-1].upper()}', mode='walk', goal='learn ranking', started=at - 60, here=dict(step=1, at=at),
                            steps=[dict(slug='ranking', status='todo', check=dict(STEP)), dict(slug='reciprocal-rank-fusion', status='todo', check=dict(STEP))]))
    return 'wa', 'wb'

def b_home_empty(lr, cl, mp): return '/', {}

def b_home_going(lr, cl, mp):
    two_walks(lr)
    return '/', {}

def b_course_going(lr, cl, mp):
    goal_walk(lr, 1)
    return '/', {}

def b_home_starting(lr, cl, mp):
    "A goal walk is being made: its job row runs, as the Start box writes it."
    job_start(lr, 'build:goal1', 'build', title='Fine-tune diffusion for comics', said='Planning the walk')
    return '/', dict(said='Planning the walk')

def b_reviews_due(lr, cl, mp):
    due(lr, 'ranking', 'reciprocal-rank-fusion')
    return '/', dict(n=2)

PLAN = dict(title='Softmax and attention', subject='ml', steps=[dict(name=n, statement=f'{n} is one idea.', slug='', why='The goal.', needs=[], ways=['words'])
                                                                for n in ('Softmax', 'Attention', 'Keys')])

def paper(lr, cl):
    "A walk of three ideas from the attention paper, made through the app, each with its passage."
    return walk(cl, lr)

def topic(lr, **kv):
    "A topic walk of three ideas that research looks at: the first has a source, the second has none, the third waits."
    j = walk_from_topic(lr, Fake({'You plan a learning path': PLAN}), 'learn softmax and attention')
    now = time.time()
    lr.walk_step(j.id, 0, research='found', research_at=now - 40, read=dict(text='Softmax turns scores into weights.', researched=True, src='web', url='https://example.org/s'))
    lr.walk_step(j.id, 1, research='none', research_at=now - 20)
    lr.walk_step(j.id, 2, research='pending', research_at=now - 60)
    return lr.merge_journey(j.id, research_start=now - 60, research_beat=now - 12, gather=[dict(tool='web_search', target='softmax', at=now - 30, outcome='read')], **kv).id

def running(lr, jid):
    "The research of walk `jid` runs now: its job row says so. No fake is needed."
    job_start(lr, f'walk:{jid}:research', 'research', title=lr.journey(jid).title, said='Looking for sources', url=f'/w/{jid}#sources', obj=f'walk:{jid}')

def started(cl, jid):
    assert cl.post(f'/w/{jid}/start', follow_redirects=False).status_code == 303
    return jid

def b_walk_new(lr, cl, mp): return f'/w/{paper(lr, cl)}', {}

def b_walk_going(lr, cl, mp):
    jid = started(cl, paper(lr, cl)); done(lr, jid, 0)
    return f'/w/{jid}', dict(n=2, total=3)

def b_walk_researching(lr, cl, mp):
    jid = topic(lr); running(lr, jid)
    return f'/w/{jid}', dict(have=1, total=3, has='has')   # one idea has a source

def b_walk_research_ended(lr, cl, mp):
    jid = topic(lr, research_end=time.time())
    return f'/w/{jid}', {}

def b_walk_finished(lr, cl, mp):
    jid = started(cl, paper(lr, cl)); done(lr, jid, 0, 2); done(lr, jid, 1, outcome='fragile')
    return f'/w/{jid}', {}

def b_walk_side(lr, cl, mp):
    jid = paper(lr, cl)
    lr.put_journey(dict(id='side', title='Softmax first', mode='walk', parent=dict(walk=jid, step=1, slug='softmax'), depth=1, slug='ranking',
                        steps=[dict(slug='ranking', status='todo', check=dict(STEP))]))
    from abhyasa.core import short_title
    return '/w/side', dict(parent=short_title(lr.journey(jid).title))   # Back to names the walk that opened it

def lock(cl, jid, *slugs):
    "Lock the ideas `slugs` of walk `jid` with the Lock toggle of the plan."
    for s in slugs: assert cl.post(f'/w/{jid}/edit', data=dict(slug=s, act='lock')).status_code == 200

def b_walk_locked(lr, cl, mp):
    jid = paper(lr, cl); ss = [s['slug'] for s in lr.journey(jid).steps]
    lock(cl, jid, ss[0], ss[2])
    return f'/w/{jid}', {}

def b_course_locked(lr, cl, mp):
    "The course of the goal walk, with the stage of the walk locked on the course page, and one planned stage that Fix the rest plans again."
    from abhyasa.path import join_course
    goal_walk(lr); cid = join_course(lr, 'gw').id
    lr.change_course(cid, lambda c: c.stages.append(dict(key='s9', name='An old plan', makes='', ideas=['Old'], foundation=False, skip_if='', short=False, walk=None, status='planned')))
    assert cl.post(f'/course/{cid}/lock', data=dict(key=lr.course(cid).stages[0]['key'], on='1')).status_code == 200
    return f'/course/{cid}', {}

def b_walk_empty(lr, cl, mp):
    lr.put_journey(dict(id='none', title='An empty source', mode='walk', steps=[]))
    return '/w/none', {}

def b_idea_reading(lr, cl, mp):
    jid = started(cl, paper(lr, cl)); lr.walk_step(jid, 1, check=dict(STEP))   # a short check: the code check goes (step 7)
    return f'/w/{jid}/1', {}

def intercept_step(lr, cl, floor=0):
    "A started paper walk whose step 1 has a check on the intercept, a concept on the shelf at depth `floor`."
    jid = started(cl, paper(lr, cl))
    lr.put('Intercept', 'The intercept is the point where a line crosses the y axis.', 'maths')
    if floor: lr.update('intercept', floor=floor)
    lr.walk_step(jid, 1, check=dict(STEP, q='Slide the line up. How does the intercept change?'))
    return f'/w/{jid}/1', {}

def b_idea_new_words(lr, cl, mp): return intercept_step(lr, cl)
def b_idea_words_known(lr, cl, mp): return intercept_step(lr, cl, floor=4)

def b_idea_last_done(lr, cl, mp):
    "A side walk of 4 ideas from step 3 of a paper walk, all done: the last idea goes back to the main idea."
    jid = started(cl, paper(lr, cl)); main = lr.journey(jid).steps[2]['slug']
    lr.put_journey(dict(id='side4', title='Side walk', mode='walk', depth=1, slug='ranking', started=time.time(), parent=dict(walk=jid, step=2, idea=main),
                        steps=[dict(slug=s, status='todo', check=dict(STEP), done=dict(outcome='solid', at=time.time())) for s in ('ranking', 'softmax', 'reciprocal-rank-fusion', 'ranking')]))
    return '/w/side4/3', {}

def b_idea_done(lr, cl, mp):
    jid = started(cl, paper(lr, cl)); lr.walk_step(jid, 1, check=dict(STEP)); done(lr, jid, 1)
    return f'/w/{jid}/1', {}

def needs_data(lr, cl):
    "A started paper walk whose step 1 is a notebook check that names EPISODES and IMAGES, with no folder for either."
    from abhyasa.contract import _GOOD, validate_nb_spec
    jid = started(cl, paper(lr, cl))
    data = [dict(name=n, path='', need=True, what=w) for n, w in (('EPISODES', 'Text of the comic episodes.'), ('IMAGES', 'Your comic panel images.'))]
    lr.walk_step(jid, 1, check=dict(way='code', kind='notebook', depth=4, why=''), nb=validate_nb_spec({**_GOOD, 'data': data}))
    return jid

def b_idea_notebook(lr, cl, mp): return f'/w/{needs_data(lr, cl)}/1', {}

def b_idea_notebook_no_spec(lr, cl, mp):
    "A started paper walk whose step 1 is a notebook check with no spec: no job writes it, and a load starts none."
    jid = started(cl, paper(lr, cl))
    mp.setattr('abhyasa.path.nb_spec', lambda *a, **kw: None)
    lr.walk_step(jid, 1, check=dict(way='code', kind='notebook', depth=4, why=''), nb=None, nb_why=None)
    return f'/w/{jid}/1', {}

def b_walk_needs_data(lr, cl, mp): return f'/w/{needs_data(lr, cl)}', {}

def b_concept_in_walk(lr, cl, mp):
    jid = started(cl, paper(lr, cl)); j = lr.journey(jid)
    return f"/c/{j.steps[1]['slug']}", {'walk title': j.title}

def b_concept_alone(lr, cl, mp):
    paper(lr, cl)   # a walk to add the idea to
    return '/c/ranking', {}

def b_library_concepts(lr, cl, mp): return '/library', {}

def b_library_sources(lr, cl, mp):
    paper(lr, cl)
    return '/library/sources', {}

def b_you(lr, cl, mp):
    jid = started(cl, paper(lr, cl)); done(lr, jid, 0)
    return '/you', {}

def rabbit_step(lr, cl):
    "A started walk on the paper whose step 3 needs gradients, which you did not learn."
    jid = started(cl, paper(lr, cl))
    lr.put('Derivatives and gradients', 'The slope of a function at a point.', 'ml', slug='gradients')
    lr.update('scaling-by-the-root-of-dk', prereqs=['softmax', 'gradients']); lr.walk_step(jid, 2, check=dict(STEP))
    return jid

def b_idea_own_course(lr, cl, mp):
    from abhyasa.path import course_from
    jid = rabbit_step(lr, cl); course_from(lr, 'gradients', dict(walk=jid, step=2))
    return f'/w/{jid}/2', {}

def b_course_from_rabbit(lr, cl, mp):
    from abhyasa.path import course_from
    jid = rabbit_step(lr, cl)
    return f"/course/{course_from(lr, 'gradients', dict(walk=jid, step=2)).id}", {}

BUILD = {('home', 'empty'): b_home_empty, ('home', 'going'): b_home_going, ('idea', 'reading'): b_idea_reading, ('idea', 'new_words'): b_idea_new_words, ('idea', 'words_known'): b_idea_words_known, ('idea', 'done'): b_idea_done, ('idea', 'last_done'): b_idea_last_done, ('home', 'course_going'): b_course_going, ('home', 'reviews_due'): b_reviews_due, ('home', 'starting'): b_home_starting,
         ('walk', 'new'): b_walk_new, ('walk', 'going'): b_walk_going, ('walk', 'researching'): b_walk_researching, ('walk', 'research_ended'): b_walk_research_ended,
         ('walk', 'finished'): b_walk_finished, ('walk', 'side_walk'): b_walk_side, ('walk', 'empty'): b_walk_empty, ('walk', 'locked'): b_walk_locked,
         ('course', 'stage_locked'): b_course_locked, ('course', 'from_rabbit'): b_course_from_rabbit, ('idea', 'own_course'): b_idea_own_course,
         ('idea', 'notebook'): b_idea_notebook, ('idea', 'notebook_no_spec'): b_idea_notebook_no_spec, ('walk', 'needs_data'): b_walk_needs_data,
         ('concept', 'in_a_walk'): b_concept_in_walk, ('concept', 'not_in_a_walk'): b_concept_alone,
         ('library', 'concepts'): b_library_concepts, ('library', 'sources'): b_library_sources, ('you', 'any'): b_you}

# --- the drivers of the workflows ------------------------------------------------------------------------------------

def d_continue(lr, cl, mp, fake):
    "On a page that is not the place, Continue in the top bar opens the idea that you used last."
    two_walks(lr)
    pg = page(cl, '/library')
    a = pg.acts['continue'][0]
    assert a.get('href') == '/w/wb/1', a.get('href')
    assert route_of(a.get('href')) == 'idea'
    page(cl, a.get('href'))

def d_find_sources(lr, cl, mp, fake):
    "From an idea, the title in the outline opens the walk page; its sources part has the research line with Stop and Show what it did."
    jid = started(cl, topic(lr)); running(lr, jid)
    a = page(cl, f'/w/{jid}/1').acts['walk'][0]
    assert a.get('href') == f'/w/{jid}'
    pg = page(cl, a.get('href'))
    assert pg.has('part:sources') and pg.has('label:1 of 3 ideas has a source.') and pg.works('stop') and pg.works('show-log')
    assert cl.post(f'/w/{jid}/gather/stop').status_code == 200

def d_finish_walk(lr, cl, mp, fake):
    "Next idea on the last idea opens the walk page in its finished state; Review the weak ideas starts a review."
    jid = started(cl, paper(lr, cl)); done(lr, jid, 0); done(lr, jid, 1, outcome='fragile')
    r = cl.post(f'/w/{jid}/2/next', follow_redirects=False)
    assert r.headers['location'] == f'/w/{jid}'
    pg = page(cl, r.headers['location'])
    assert pg.has('part:result') and pg.has('label:You finished the walk.') and not pg.has('act:start')
    go = pg.acts['review'][0].get('href')
    assert cl.get(go, follow_redirects=False).headers['location'].startswith('/s/')

def change(cl, jid, words):
    "Send `words` to the box at the top of the walk, and ask again until the tutor made the changes. Gives the last answer."
    r = cl.post(f'/w/{jid}/improve', data=dict(words=words))
    for _ in range(200):
        if 'improve-wait' not in r.text: return r
        time.sleep(.05); r = cl.get(re.search(r'hx-get="([^"]+)"', r.text)[1].replace('&amp;', '&'))
    raise AssertionError('the tutor made no change')

def d_improve_walk(lr, cl, mp, fake):
    "Change the plan in place with Undo; then the box: the tutor makes the change at once, says what changed, and one Undo takes it back."
    jid = paper(lr, cl)
    cl.post(f'/w/{jid}/edit', data=dict(slug='softmax', act='skip'))
    assert lr.journey(jid).steps[1]['status'] == 'skip'
    cl.post(f'/w/{jid}/undo')
    assert lr.journey(jid).steps[1]['status'] == 'todo'
    fake.rules['You propose changes to one learning walk'] = dict(changes=[dict(op='easier', idea='softmax', why='Less to do.')])
    assert page(cl, f'/w/{jid}').works('change')
    d = lr.journey(jid).steps[1]['check'].get('depth', 2)
    r = change(cl, jid, 'Make the walk simpler.')
    e = lr.edits('walk', jid)[0]
    assert lr.journey(jid).steps[1]['check']['depth'] == max(1, d - 1) and e.who == 'tutor' and e.what == 'Improved the walk: 1 change.' and 'What changed' in r.text
    cl.post(f'/w/{jid}/undo', data=dict(step=e.id))
    assert lr.journey(jid).steps[1]['check'].get('depth', 2) == d

def d_lock_and_fix(lr, cl, mp, fake):
    """Lock two ideas; "fix the rest" in the box: the tutor leaves the locked ideas out and keeps them byte for byte, and Undo takes it back.
    A hand edit unlocks an idea, and Undo locks it again. On the course page, a locked stage and its walk stay after Fix the rest."""
    jid = paper(lr, cl); ss = [s['slug'] for s in lr.journey(jid).steps]
    lock(cl, jid, ss[0], ss[2])
    pg = page(cl, f'/w/{jid}')
    assert pg.has('label:Locked') and pg.works('lock') and pg.works('change')
    was = [json.dumps(s, sort_keys=True) for s in lr.journey(jid).steps]
    fake.rules['You redo the ideas of one learning walk'] = dict(changes=[dict(op='remove', idea=ss[0], why='x'), dict(op='harder', idea=ss[1], why='A real test.')])
    r = change(cl, jid, 'fix the rest, and make it harder')
    assert 'Made the check of' in r.text and 'Removed' not in r.text
    now = [json.dumps(s, sort_keys=True) for s in lr.journey(jid).steps]
    assert (now[0], now[2]) == (was[0], was[2]) and now[1] != was[1] and lr.edits('walk', jid)[0].what == 'Fixed the rest of the walk: 1 change.'
    cl.post(f'/w/{jid}/undo')
    assert [json.dumps(s, sort_keys=True) for s in lr.journey(jid).steps] == was
    cl.post(f'/w/{jid}/edit', data=dict(slug=ss[0], act='skip'))
    assert 'locked' not in lr.journey(jid).steps[0]
    cl.post(f'/w/{jid}/undo')
    assert lr.journey(jid).steps[0]['locked'] is True
    url, _ = b_course_locked(lr, cl, mp); cid = url.split('/')[-1]
    keep = json.dumps(lr.course(cid).stages[0], sort_keys=True)
    fake.rules['You plan a course to one learner'] = dict(title='x', makes='x', stages=[dict(name='Your comic data', makes='captions.jsonl', ideas=['Captions'])])
    assert page(cl, url).works('fix')
    r = cl.post(f'/course/{cid}/fix')
    for _ in range(200):
        if 'HX-Redirect' in r.headers: break
        time.sleep(.05); r = cl.get(f'/course/{cid}/job?k=plan')
    c = lr.course(cid)
    assert json.dumps(c.stages[0], sort_keys=True) == keep and [s['name'] for s in c.stages][1:] == ['Your comic data']

def events(cl, said, ctx, thread=None):
    "The events of one question to the guide."
    r = cl.post('/guide/ask', json=dict(said=said, ctx=ctx, **({'thread': thread} if thread else {})))
    return [json.loads(l[6:]) for l in r.text.splitlines() if l.startswith('data: ')]

def d_explain(lr, cl, mp, fake):
    """Caps+E on an idea page: the board has its steps, with a side-panel row made from the words on the page, and it ends with the Show offer.
    Then "yes" is Show: one show event with the card for the Show slot, no board, and one ask row."""
    jid = started(cl, paper(lr, cl)); slug = lr.journey(jid).steps[1]['slug']
    page(cl, f'/w/{jid}/1')
    ctx = dict(page=f'/w/{jid}/1', slug=slug, anchors=[dict(id='code1', kind='code', text='weights = softmax(scores)')])
    fake.rules['Tier: tutor'] = '\n'.join(json.dumps(o) for o in [dict(op='v', n=1, sure=0.9), dict(op='step', say='Softmax turns the scores into weights.'),
        dict(op='panel', head='Scores to weights'), dict(op='row', cells=['scores'], to='weights', at=dict(a='code1', text='softmax(scores)')),
        dict(op='step', say='Say show me to see it move.')])
    evs = events(cl, 'what does this line do', ctx)
    b = evs[-1]['board']
    assert len(b['steps']) == 2 and [s['op'] for s in b['steps'][0]['strokes']] == ['panel', 'row']
    evs = events(cl, 'yes', ctx, [dict(said='what does this line do', says=[s['say'] for s in b['steps']])])
    assert [list(e) for e in evs] == [['show']] and 'ask-card' in evs[0]['show']['html']
    a = lr.asks(concept=slug)[0]
    assert a.where == 'guide' and 'softmax(scores)' in a.ask

def d_rabbit(lr, cl, mp, fake):
    """I don't get X: Learn it in the stuck row opens the chooser with the pick first; a quick look is a side walk of the step whose end
    reports back; a big selected term opens its own course with the step as its origin; Enough: go back returns to the step; and on a
    concept page, the side walk goes back to the concept page."""
    fake.rules['You grade one answer'] = dict(correct=True, grade=9, first_error='', misconception='', feedback='Yes.')
    fake.rules['The idea: diffusion model'] = dict(name='Diffusion model', statement='A model that learns to undo noise, step by step.', size=8)
    jid = rabbit_step(lr, cl); at = f'{jid}/2'
    card = cl.get(f'/w/{jid}/2/check').text
    t = re.search(r'class="[^"]*rh-stuck[^"]*" data-t="([^"]+)"|data-t="([^"]+)"[^>]*class="[^"]*rh-stuck', card)
    term = t[1] or t[2]
    offer = cl.get('/rh/term', params=dict(t=term, at=at)).text
    assert re.findall(r'data-how="(\w+)"[^>]*class="rh-way', offer)[0] == 'primer'
    r = cl.post('/rh/open', data=dict(slug=term, at=at, how='primer')).json(); sid = r['url'].split('/')[2]
    assert route_of(r['url']) == 'idea' and lr.journey(sid).parent['walk'] == jid
    cl.get(f'/w/{sid}/0/check'); cl.post(f'/w/{sid}/0/answer', data=dict(answer='the slope', confidence=90))
    assert 'data-rh-done' in cl.post(f'/w/{sid}/0/next', params=dict(pane=1)).text
    assert cl.post(f'/rh/back/{sid}', follow_redirects=False).headers['location'] == f'/w/{jid}/2'
    assert page(cl, f'/w/{jid}/2').has('label:learned on the way today')
    cl.post('/rh/term', data=dict(t='diffusion model', at=at))
    r = cl.post('/rh/open', data=dict(slug='diffusion-model', at=at, how='course')).json()
    assert route_of(r['url']) == 'course'
    pg = page(cl, r['url'])
    assert pg.has('part:origin') and pg.works('go-back') and lr.course(r['url'].split('/')[2]).origin['walk'] == jid
    assert page(cl, f'/w/{jid}/2').has('act:own-course')
    assert cl.post(f"{r['url']}/back", follow_redirects=False).headers['location'] == f'/w/{jid}/2'
    r = cl.post('/rh/open', data=dict(slug='gradients', at='/c/gradients', how='primer')).json(); sid = r['url'].split('/')[2]
    assert cl.post(f'/rh/back/{sid}', follow_redirects=False).headers['location'] == '/c/gradients'

DRIVE = {'rabbit': d_rabbit, 'explain': d_explain, 'continue': d_continue, 'find_sources': d_find_sources, 'finish_walk': d_finish_walk, 'improve_walk': d_improve_walk, 'lock_and_fix': d_lock_and_fix}
