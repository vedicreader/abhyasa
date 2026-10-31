"The helpers of the spec test (`test_flows.py`): the spec, a parsed page, the page id of an app path, and the builder of each state."
import json, re, time
from pathlib import Path
from urllib.parse import urlsplit
import lxml.html
from fastcore.basics import AttrDict
from starlette.routing import Match

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

def b_course_going(lr, cl, mp):
    goal_walk(lr, 1)
    return '/', {}

def b_reviews_due(lr, cl, mp):
    due(lr, 'ranking', 'reciprocal-rank-fusion')
    return '/', dict(n=2)

BUILD = {('home', 'course_going'): b_course_going, ('home', 'reviews_due'): b_reviews_due}

# --- the drivers of the workflows ------------------------------------------------------------------------------------

def d_continue(lr, cl, mp):
    "On a page that is not the place, Continue in the top bar opens the idea that you used last."
    two_walks(lr)
    pg = page(cl, '/concepts')
    a = pg.acts['continue'][0]
    assert a.get('href') == '/w/wb/1', a.get('href')
    assert route_of(a.get('href')) == 'idea'
    page(cl, a.get('href'))

DRIVE = {'continue': d_continue}
