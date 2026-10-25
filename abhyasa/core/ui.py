"The page frame, shared pieces, and block assets served with a content hash."
import hashlib, time
from pathlib import Path
from fasthtml.common import *
from abhyasa.core.cfg import RouteOverrides
from abhyasa.model import DEPTHS, GOAL

__all__ = ['ASSETS', 'asset_js', 'asset_css', 'serve_assets', 'HDRS', 'Page', 'Md', 'DepthBar', 'Spin', 'when']

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

def HDRS():
    "Headers for every page: the base theme, markdown and KaTeX, and the core script."
    return (asset_css(_here/'base.css'), Script(src='https://cdn.jsdelivr.net/npm/marked@14/marked.min.js'),
            Link(rel='stylesheet', href='https://cdn.jsdelivr.net/npm/katex@0.16/dist/katex.min.css'),
            Script(src='https://cdn.jsdelivr.net/npm/katex@0.16/dist/katex.min.js', defer=True),
            Script(src='https://cdn.jsdelivr.net/npm/katex@0.16/dist/contrib/auto-render.min.js', defer=True),
            asset_js(_here/'core.js'))

def Page(title, *c, on='', wide=False, extra=()):
    "A whole page: the header with the blocks' nav links and a search box, then `c`."
    nav = [A(t, href=h, cls='on' if t == on else '') for t, h, _ in sorted(RouteOverrides.nav, key=lambda x: x[2])]
    return (Title(f'{title} · abhyasa'), *extra, Nav(A('abhyasa', href='/', cls='brand'), *nav,
            Form(Input(type='search', name='q', placeholder='Search what you learned'), action='/search')),
            Main(*c, cls='wide' if wide else ''))

def Md(s, cls='', **kw):
    "Markdown with maths, rendered in the browser by `core.js`."
    return Div(s, cls=f'md {cls}'.strip(), **kw)

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
