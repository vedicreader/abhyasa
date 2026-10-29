"The page frame, shared pieces, and block assets served with a content hash."
import hashlib, html, re, time, nh3
from contextvars import ContextVar
from pathlib import Path
from fasthtml.common import *
from mdhtml import md2mdhtml, mdhtml2html
from abhyasa.core.cfg import RouteOverrides
from abhyasa.core.hooks import run
from abhyasa.core.pane import PaneHost, is_local, is_web, pane_url, pane_link
from abhyasa.model import DEPTHS

__all__ = ['Cites', 'WebSource', 'ASSETS', 'asset_js', 'asset_css', 'serve_assets', 'HDRS', 'THEMES', 'MODES', 'look', 'look_attrs', 'look_before', 'Page', 'SubTabs', 'in_talk', 'Crumbs', 'clean_html', 'md_html', 'Md', 'Inline', 'DepthBar', 'Spin', 'when', 'ago', 'doc_title',
           'meta', 'n_of', 'moved_words', 'one_main', 'Primary', 'Secondary', 'Quiet', 'OUTCOMES', 'Tag', 'Msg', 'FirstError', 'Confidence', 'Check', 'Empty', 'Part', 'Onward']

_here = Path(__file__).parent
ASSETS = {}   # name -> (text, media type)

def _asset(path, mime):
    p = Path(path)
    txt = p.read_text()
    ASSETS[p.name] = (txt, mime)
    return f'/assets/{p.name}?v={hashlib.sha1(txt.encode()).hexdigest()[:10]}'

for _f in (_here/'fonts').glob('*.woff2'): ASSETS[_f.name] = (_f.read_bytes(), 'font/woff2')   # base.css names them; local, so it works offline

def asset_js(path, **kw):
    "A `Script` for a block's own .js file."
    return Script(src=_asset(path, 'text/javascript'), **kw)

def asset_css(path, **kw):
    "A `Link` for a block's own .css file, so a block keeps its styles beside its code."
    return Link(rel='stylesheet', href=_asset(path, 'text/css'), **kw)

def serve_assets(app):
    "The one route that serves every registered asset; immutable, since the URL has the hash."
    @app.get('/assets/{name}')
    def asset(name:str):
        if name not in ASSETS: return Response('not found', status_code=404)
        txt, mime = ASSETS[name]
        return Response(txt, media_type=mime, headers={'Cache-Control': 'public, max-age=31536000, immutable'})
    app.router.routes.insert(0, app.router.routes.pop())   # before fast_app's own `/{fname}.{ext:static}` route
    from starlette.staticfiles import StaticFiles
    app.mount('/vendor', StaticFiles(directory=_here/'vendor'), name='vendor')   # htmx, KaTeX and d3, pinned, so the app works offline
    app.router.routes.insert(0, app.router.routes.pop())

def HDRS():
    "Headers for every page: the base theme, KaTeX, and the core script."
    return (Meta(charset='utf-8'), Meta(name='viewport', content='width=device-width, initial-scale=1'),
            Script(src='/vendor/htmx.min.js'), Script(src='/vendor/fasthtml.js'),
            asset_css(_here/'base.css'), asset_css(_here/'themes.css'),
            Link(rel='stylesheet', href='/vendor/katex.min.css'), Script(src='/vendor/katex.min.js', defer=True),
            asset_css(_here/'pane.css'), asset_js(_here/'core.js'), asset_js(_here/'grip.js'), asset_js(_here/'pane.js'))

THEMES = dict(paper='Warm paper, umber accent', ink='Calm, high contrast, dark first', manuscript='Palm leaf, saffron accent',
              clear='System font, plain and bright', sage='Soft green-grey, low glare', signal='Silver panels, orange controls')   # themes.css has the colours
MODES = ('auto', 'light', 'dark')

def look() -> tuple:
    "The theme and the mode from the settings; an unknown name gives the default."
    from abhyasa.voice import settings
    s = settings().get('look') or {}
    t, m = s.get('theme'), s.get('mode')
    return t if t in THEMES else 'paper', m if m in MODES else 'auto'

def look_attrs() -> dict:
    "The attributes on <html> that set the theme and the mode."
    t, m = look()
    return {'data-theme': t, 'data-mode': m}

_req = ContextVar('abhyasa_req', default=None)   # the request of this page, so `Page` can read `pane` and `rh` with no route change

async def look_before(req):
    "Beforeware: each page starts in the theme from the settings. Async, so the request it keeps is seen by the handler."
    _req.set(req)
    req.htmlkw.update(look_attrs())

def Crumbs(crumbs):
    "Where you are: the links up to this page. The last one is the parent, where Esc goes."
    if not crumbs: return ''
    out = []
    for i, (t, h) in enumerate(crumbs):
        last = i == len(crumbs) - 1
        out += [A(('← ' if last and len(crumbs) == 1 else '') + t, href=h, cls='up' if last else None, title='Esc' if last else None), Span('›', cls='sep')]
    return Div(*out[:-1], cls='crumbs', role='navigation', aria_label='Where you are')

def in_talk() -> bool:
    "Whether this page is in the side pane of a talk (`pane=1&talk=1`): it draws in the talk type, with no check."
    req = _req.get()
    q = req.query_params if req is not None else {}
    return q.get('pane') == '1' and q.get('talk') == '1'

_GEAR = ('<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 '
         '1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1'
         'a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3'
         'l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>')

def SubTabs(tab:str, sub:str):
    "The row of sub-tabs under the title of a page in `tab`, with `sub` in force; ⌥1, ⌥2 and ⌥3 pick them (core.js). Empty when the tab has none."
    rows = sorted(RouteOverrides.subtabs.get(tab, ()), key=lambda x: x[2])
    if not rows: return ''
    return Nav(*[A(t, href=h, role='tab', cls='on' if t == sub else None, title=f'⌥{i}' if i < 4 else None)(aria_selected='true' if t == sub else 'false')
                 for i, (t, h, _) in enumerate(rows, 1)], cls='subtabs', role='tablist', aria_label=tab)

def Page(title, *c, on='', sub='', wide=False, extra=(), crumbs=(), pane=False):
    """A whole page: the top bar (the four tabs, with `on` in force, what other blocks add (`nav_extra`), the search and the gear), the crumbs,
    the sub-tabs of `on` with `sub` in force, then `c`.
    In the side pane (`pane`, or `pane=1` in the request) it has no nav and no crumbs. With a local `rh` in the request, the side pane is open."""
    req = _req.get()
    q = req.query_params if req is not None else {}
    one_main(c)
    if pane or q.get('pane') == '1':
        if req is not None: req.htmlkw['class'] = 'in-pane talk-type' if in_talk() else 'in-pane'
        return (Title(f'{title} · abhyasa'), *extra, Main(*c, cls='wide' if wide else ''), *run('page_extra'), *((asset_js(_here/'talktype.js'),) if in_talk() else ()))
    rh = q.get('rh')
    side = ''
    if req is not None and is_local(rh):
        req.htmlkw['class'] = 'rh-open'   # drawn open, so it does not flash closed on a reload
        side = next(iter(run('pane_title', rh)), '')
    nav = [A(t, href=h, cls='on' if t == on else '', aria_current='page' if t == on else None) for t, h, _ in sorted(RouteOverrides.nav, key=lambda x: x[2])]
    g = RouteOverrides.gear
    here = g is not None and req is not None and req.url.path == g
    gear = A(NotStr(_GEAR), href=g, aria_label='Settings', title='Settings', cls='gear on' if here else 'gear', aria_current='page' if here else None) if g else ''
    return (Title(f'{title} · abhyasa'), *extra, Nav(A('abhyasa', href='/', cls='brand'), *nav, Span(cls='nav-gap'), *run('nav_extra'),
            A('Search ', Kbd('/'), href='/search', cls='nav-search'),   # beside the side pane, in place of the box (pane.css)
            Form(Input(type='search', name='q', placeholder='Search what you learned  /', aria_label='Search'), action='/search'), gear, aria_label='Main'),
            Main(Crumbs(crumbs), SubTabs(on, sub), Narrow(rh, side), *c, cls='wide' if wide else ''), PaneHost(rh, side), *run('page_extra'))

def Narrow(rh, title=''):
    "Under 1100 px the side pane does not show: one line over the title names the side walk that is open, and opens it (pane.css shows it)."
    if not is_local(rh): return ''
    said = ('You have a side walk open: ', B(title), '. Open it →') if title else ('You have a side page open. Open it →',)
    return A(*said, href=rh, data_pane=pane_url(rh), cls='rh-back rh-narrow')

# Learner text, model text and vault text are not trusted. Markdown is rendered here as Leela does it (mdhtml with dollar maths),
# then nh3 keeps only the tags and attributes that markdown can mean. `core.js` draws each `.math` with KaTeX.
_TAGS = set('a b blockquote br code del div em h1 h2 h3 h4 h5 h6 hr i img li ol p pre s span strong sub sup table tbody td th thead tr ul'.split())
_DROP = set('script style iframe frame object embed video audio form button meta base link noscript template svg math select textarea title'.split())
_ATTRS = {'*': {'class'}, 'a': {'href', 'title'}, 'img': {'src', 'alt', 'title'}, 'td': {'align'}, 'th': {'align'}, 'ol': {'start'}}

_IMG = re.compile(r'^data:image/(png|jpeg|gif|webp|avif);base64,', re.I)

def _attr(tag, attr, val):
    "The value of `attr` to keep, or None: images from inline data only, no data: link, and only the classes the renderer gives."
    if attr in ('src', 'href'):
        v = re.sub(r'[\x00-\x20]+', '', val)
        if attr == 'src': return v if _IMG.match(v) else None   # no request from text: an image is inline data only, else its alt text
        if v.lower().startswith('data:'): return None
    if attr != 'class': return val
    return ' '.join(t for t in val.split() if t in ('math', 'inline', 'display') or t.startswith('language-')) or None

def clean_html(h, imgs=()):
    """`h` cut to what markdown means: no scripts, frames, media, forms, handlers or styles; links only to http, https and mailto; no relative URL.
    An image `src` that is one of the local paths in `imgs` stays: the page made each one and checked that its file is there."""
    def f(t, a, v):   # with `imgs`, nh3 lets relative URLs through, so a link must name its scheme here
        if a == 'src' and v in imgs: return v
        if a == 'href' and not re.match(r'(https?|mailto):', re.sub(r'[\x00-\x20]+', '', v), re.I): return None
        return _attr(t, a, v)
    return nh3.clean(h, tags=_TAGS, clean_content_tags=_DROP, attributes=_ATTRS, attribute_filter=f if imgs else _attr,
                     url_schemes={'http', 'https', 'mailto', 'data'}, url_relative='pass_through' if imgs else 'deny', link_rel='noopener noreferrer')

def md_html(s, imgs=()):
    "Safe HTML for markdown `s`: `$…$` is a `span.math`, `$$…$$` a `.math.display`, and a code fence a `pre` that keeps its lines. `imgs` as in `clean_html`."
    s = str(s or '')
    try: h = str(mdhtml2html(md2mdhtml(s, math='dollars', frontmatter=False), refs='ids', auto_ids=False, hl=None))
    except Exception: h = f'<p>{html.escape(s)}</p>'
    return clean_html(h, imgs)

def Md(s, cls='', imgs=(), **kw):
    "Markdown with maths, rendered and cleaned here; `core.js` draws the maths. `imgs`: the local image paths that may show."
    return Div(NotStr(md_html(s, imgs)), cls=f'md {cls}'.strip(), **kw)

def Inline(s, cls=''):
    "A short text with maths as a `span`, with no block tags, for a name inside a link or a list item; `core.js` draws the maths."
    h = md_html(s).strip()
    m = re.fullmatch(r'<p>(.*)</p>', h, re.S)
    return Span(NotStr(m.group(1)) if m and '<p>' not in m.group(1) else html.escape(str(s or '')), cls=cls)

def DepthBar(floor, asked=None):
    "Five marks: filled to the floor, the asked depth marked."
    return Span(*[I(cls='f' if d <= floor else 'a' if d == asked else '') for d in range(1, 6)], cls='depth',
                title=(f'level: {DEPTHS[floor]}' if floor else 'not learned yet') + (f', asked at {DEPTHS[asked]}' if asked else ''))

def Spin(txt='thinking…'): return Span(txt, cls='spin htmx-indicator')

def when(t):
    "A short time until `t`."
    if not t: return 'not scheduled'
    d = (t - time.time()) / 86400
    if d <= 0: return 'due now'
    return f'in {d*24:.0f} h' if d < 1 else f'in {d:.0f} d'

def ago(t):
    "A short time since `t`: today at 14:05, yesterday, Mon 20 Oct."
    if not t: return ''
    lt, now = time.localtime(t), time.localtime()
    days = (time.mktime(now[:3] + (0, 0, 0) + now[6:]) - time.mktime(lt[:3] + (0, 0, 0) + lt[6:])) / 86400
    if days < 1: return time.strftime('today at %H:%M', lt)
    if days < 2: return time.strftime('yesterday at %H:%M', lt)
    return time.strftime('%a %d %b' if days < 300 else '%d %b %Y', lt)

def doc_title(t):
    "The title of a vault document as the page shows it: an old walk title `Journey: …` shows as `Walk: …`. The stored title stays."
    return 'Walk: ' + t[len('Journey: '):] if isinstance(t, str) and t.startswith('Journey: ') else t

# --- shared pieces (design review, section 5): a block uses these and does not make its own copy -----------------------

def meta(*parts) -> str:
    "A meta line: the parts that are not empty, joined with ` · `."
    return ' · '.join(str(p) for p in parts if p not in (None, '', 0, False))

def n_of(n:int, word:str, plural:str=None) -> str:
    "A count with the right plural: `1 idea`, `3 ideas`, `0 ideas`."
    return f"{n} {word if n == 1 else plural or word + 's'}"

def moved_words(m) -> tuple:
    """What a sitting did to one concept (a row of `tutor.moved`), as `(said, count)`. A pass never reads as "nothing happened":
    `recall → explain`, `stays at recall` for a concept seen before, else `first pass`, `on the way to recall`, or `not yet`.
    `count` is `2 of 3 passed`, or empty when `said` already tells it."""
    b, a, n, ok = m['before'], m['after'], m['asked'], m['passed']
    if a != b: said = f"{DEPTHS[b]} → {DEPTHS[a]}"
    elif b: said = f"stays at {DEPTHS[a]}"
    elif not ok: said = 'not yet'
    else: said = 'first pass' if ok == 1 else f"on the way to {DEPTHS[2]}"
    return said, f"{ok} of {n} passed" if n > 1 or b else ''

def _btn(c, cls, href=None, **kw):
    cls = ' '.join(x for x in (cls, kw.pop('cls', '')) if x)
    return A(*c, href=href, cls=f'btn {cls}'.strip(), **kw) if href else Button(*c, cls=cls or None, **kw)

def Primary(label, key='⌥S', href=None, focus=False, rank=5, **kw):
    """The main action of a view: the one filled button, with its key (⌥S). A link when `href` is given. `focus` puts the cursor
    on it when the page loads, with no focus ring until you use a key (core.js).
    A card or a view picks its own main button and draws only one. For a page made from hooks, `Page` keeps the `Primary` with
    the lowest `rank` that shows (the first one on a tie) and draws the others as `Secondary`, so the hook order does not matter."""
    return _btn((label, ' ', Kbd(key)) if key else (label,), 'go', href, data_main=str(rank), **({'data_focus': '1'} if focus else {}), **kw)

def _mains(c, hidden=False, out=None):
    "The `Primary` buttons in `c` that show: not inside a part with `hidden`."
    out = [] if out is None else out
    for x in c:
        if isinstance(x, (list, tuple)): _mains(x, hidden, out)
        elif isinstance(x, FT):
            h = hidden or x.attrs.get('hidden') not in (None, False)
            if 'data-main' in x.attrs and not h: out.append(x)
            _mains(x.children, h, out)
    return out

def _demote(b):
    "Draw a `Primary` as a `Secondary`: no fill, no key, no focus."
    b.attrs['class'] = ' '.join(k for k in b.attrs.get('class', '').split() if k != 'go') or None
    if b.attrs['class'] is None: b.attrs.pop('class')
    for k in ('data-focus', 'data-main'): b.attrs.pop(k, None)
    b.children = tuple(x for x in b.children if not (isinstance(x, FT) and x.tag == 'kbd'))
    if len(b.children) > 1 and b.children[-1] == ' ': b.children = b.children[:-1]

def one_main(c):
    "Keep one filled button in the page `c`: the shown `Primary` with the lowest rank. Return `c`."
    ms = _mains(c)
    if len(ms) > 1:
        keep = min(ms, key=lambda b: int(b.attrs['data-main']))
        for b in ms:
            if b is not keep: _demote(b)
    return c

def Secondary(label, *c, href=None, **kw):
    "A second action: a raised button with no fill. `c` can hold the one key that the page names."
    return _btn((label, *c), '', href, **kw)

def Quiet(label, *c, href=None, small=False, **kw):
    "A third action: flat and muted, such as `Skip this idea`."
    return _btn((label, *c), 'quiet small' if small else 'quiet', href, **kw)

OUTCOMES = dict(solid=('Solid', 'ok'), fragile=('Right, but shaky', 'ok'), misconception=('A misconception', 'no'), gap=('A gap', 'no'),
                skipped=('Skipped', 'skip'), nudge=('Not yet', 'no'))   # the outcome of a check -> its word and its colour

def Tag(outcome, said='', **kw):
    "The outcome of a check as one small word, in one colour map: `ok` for a pass, `no` for a miss, muted for a skip."
    t, k = OUTCOMES.get(outcome, ('Closed', 'no'))
    return Span(t + (f' · {said}' if said else ''), cls=f'tag {k}', **kw)

def Msg(label, *c, cls='', **kw):
    "One message in the thread of a check: a small label, then its text."
    return Li((Span(label, cls='lbl') if label else '') if isinstance(label, str) else label, *c, cls=f'm {cls}'.strip(), **kw)

def FirstError(text):
    "The first error in an answer, in one style for the walk and the session."
    return Div(Span('First error: ', cls='k'), Md(text), cls='err') if text else ''

def Confidence(keys=False):
    "Five steps for how sure you are. With `keys`, ⌥1 to ⌥5 pick one (the session binds them)."
    return Div(Span('Sure?', cls='lbl'), *[Label(Input(type='radio', name='confidence', value=v, **({'id': f'c{i + 1}'} if keys else {})), Span(f'{v}%'),
                                                 **({'title': f'⌥{i + 1}'} if keys else {})) for i, v in enumerate((10, 30, 50, 70, 90))],
               cls='steps', role='radiogroup', aria_label='How sure you are', **({'id': 'conf'} if keys else {}))

def Check(head, q=None, *thread, foot='', thread_id=None, shut=False, cls='', **kw):
    """The check card of the walk and the session: one raised card with the head (what is checked, and why), the question,
    the thread so far (`Msg` items), and the foot (the answer box, or Next). `thread_id` keeps an empty thread as a swap target."""
    q = Md(q, cls='q') if isinstance(q, str) else q
    th = Ol(*thread, cls='thread', id=thread_id) if thread or thread_id else ''
    return Section(head, q if q is not None else '', th, foot, cls=' '.join(x for x in ('check', 'shut' if shut else '', cls) if x), **kw)

def Onward(label, href):
    "A quiet text link on a row of a list, such as `Continue →`: it shows on hover and focus (base.css). The current row has the button."
    return A(f'{label} →', href=href, cls='onward')

def Empty(text, action=None, cls=''):
    "The one empty state: a muted line and at most one link. Never a box."
    return P(text, *((' ', action) if action is not None else ()), cls=f'mute empty {cls}'.strip())

def Part(label, *c, more=None, more_label='More', **kw):
    "A section of a page: the small H2 label, the content, and an optional closed `More` part in one style."
    return Section(H2(label), *c, Details(Summary(more_label), *more, cls='more') if more else '', **kw)

def WebSource(r, cls='src web'):
    """The line under a passage from the web (`research`): `From the web: <site> · <title>`. The title opens the copy in your vault
    in the side pane, and `Open the page` opens the original page in a new tab."""
    site, title = r.get('site') or '', r.get('title') or r.get('site') or 'the page'
    doc = f"/v/{r.get('shelf')}/{r.get('doc_id')}" if r.get('shelf') and r.get('doc_id') else ''
    name = pane_link(title, doc, title) if is_local(doc) else Span(title)
    out = A('Open the page', href=r['url'], target='_blank', rel='noopener noreferrer', cls='web-open') if is_web(r.get('url')) else ''
    return Span('From the web: ', *([site, ' · '] if site else []), name, *([' · ', out] if out else []), cls=cls)

def Cites(links, label='From your sources'):
    "Links to passages in your own sources: a vault document, a session, a notebook, a verse. A page of this app opens in the side pane."
    if not links: return ''
    def href(l):
        if l.get('url', '').startswith('http'): return l['url']
        if l.get('src', '').startswith('vault:'): return f"/v/{l['src'][6:]}/{str(l.get('ref', '')).split('#')[0]}"
    where = lambda s: 'in your vault' if str(s).startswith('vault:') else s   # a shelf name is a machine name
    link = lambda l, h: pane_link(l['title'], h, l['title']) if is_local(h) else A(l['title'], href=h) if h else Span(l['title'])
    item = lambda l: Li(link(l, href(l)), ' ', Span(where(l['src']), cls='mute'))
    return Div(Span(label, cls='lbl'), Ul(*map(item, links), cls='plain cites'), cls='cites')
