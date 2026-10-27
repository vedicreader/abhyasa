"The page frame, shared pieces, and block assets served with a content hash."
import hashlib, html, re, time, nh3
from pathlib import Path
from fasthtml.common import *
from mdhtml import md2mdhtml, mdhtml2html
from abhyasa.core.cfg import RouteOverrides
from abhyasa.core.hooks import run
from abhyasa.model import DEPTHS, GOAL

__all__ = ['Cites', 'ASSETS', 'asset_js', 'asset_css', 'serve_assets', 'HDRS', 'THEMES', 'MODES', 'look', 'look_attrs', 'look_before', 'Page', 'Crumbs', 'clean_html', 'md_html', 'Md', 'DepthBar', 'Spin', 'when', 'ago']

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
            asset_js(_here/'core.js'))

THEMES = dict(paper='Warm paper, umber accent', ink='Calm, high contrast, dark first', manuscript='Palm leaf, saffron accent',
              clear='System font, plain and bright', sage='Soft green-grey, low glare')   # themes.css has the colours
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

def look_before(req):
    "Beforeware: each page starts in the theme from the settings."
    req.htmlkw.update(look_attrs())

def Crumbs(crumbs):
    "Where you are: the links up to this page. The last one is the parent, where Esc goes."
    if not crumbs: return ''
    out = []
    for i, (t, h) in enumerate(crumbs):
        last = i == len(crumbs) - 1
        out += [A(('← ' if last and len(crumbs) == 1 else '') + t, href=h, cls='up' if last else None, title='Esc' if last else None), Span('›', cls='sep')]
    return Div(*out[:-1], cls='crumbs', role='navigation', aria_label='Where you are')

def Page(title, *c, on='', wide=False, extra=(), crumbs=()):
    "A whole page: the header with the blocks' nav links, what other blocks add (`nav_extra`), a search box, the crumbs, then `c`."
    nav = [A(t, href=h, cls='on' if t == on else '') for t, h, _ in sorted(RouteOverrides.nav, key=lambda x: x[2])]
    return (Title(f'{title} · abhyasa'), *extra, Nav(A('abhyasa', href='/', cls='brand'), *nav, Span(cls='nav-gap'), *run('nav_extra'),
            Form(Input(type='search', name='q', placeholder='Search what you learned  /', aria_label='Search'), action='/search')),
            Main(Crumbs(crumbs), *c, cls='wide' if wide else ''), *run('page_extra'))

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

def clean_html(h):
    "`h` cut to what markdown means: no scripts, frames, media, forms, handlers or styles; links only to http, https and mailto; no relative URL."
    return nh3.clean(h, tags=_TAGS, clean_content_tags=_DROP, attributes=_ATTRS, attribute_filter=_attr,
                     url_schemes={'http', 'https', 'mailto', 'data'}, url_relative='deny', link_rel='noopener noreferrer')

def md_html(s):
    "Safe HTML for markdown `s`: `$…$` is a `span.math`, `$$…$$` a `.math.display`, and a code fence a `pre` that keeps its lines."
    s = str(s or '')
    try: h = str(mdhtml2html(md2mdhtml(s, math='dollars', frontmatter=False), refs='ids', auto_ids=False, hl=None))
    except Exception: h = f'<p>{html.escape(s)}</p>'
    return clean_html(h)

def Md(s, cls='', **kw):
    "Markdown with maths, rendered and cleaned here; `core.js` draws the maths."
    return Div(NotStr(md_html(s)), cls=f'md {cls}'.strip(), **kw)

def DepthBar(floor, asked=None):
    "Five marks: filled to the floor, the asked depth marked."
    return Span(*[I(cls='f' if d <= floor else 'a' if d == asked else '') for d in range(1, 6)], cls='depth',
                title=f'floor {DEPTHS[floor]}' + (f', asked at {DEPTHS[asked]}' if asked else ''))

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

def Cites(links, label='From your sources'):
    "Links to passages in your own sources: a vault document, a session, a notebook, a verse."
    if not links: return ''
    def href(l):
        if l.get('url', '').startswith('http'): return l['url']
        if l.get('src', '').startswith('vault:'): return f"/v/{l['src'][6:]}/{str(l.get('ref', '')).split('#')[0]}"
    item = lambda l: Li(A(l['title'], href=h) if (h := href(l)) else Span(l['title']), ' ', Span(l['src'], cls='mute'))
    return Div(Span(label, cls='lbl'), Ul(*map(item, links), cls='plain cites'), cls='cites')
