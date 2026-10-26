"The web app: `fast_app`, the services, and `connect_all` over the blocks in `NAMES` order. Loopback only."
import argparse
from concurrent.futures import ThreadPoolExecutor
from starlette.middleware.base import BaseHTTPMiddleware
from fasthtml.common import *
from abhyasa.core import cfg, RouteOverrides, connect_all, serve_assets, HDRS
from abhyasa.core import hooks
from abhyasa.blocks import blocks
from abhyasa.store import Learning
from abhyasa.tutor import Tutor
from abhyasa.llm import rishi_ask, Router
from abhyasa.ground import VaultSource, VedicSource

__all__ = ['mk_app', 'main']

FAVICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="#7a4a2e"/></svg>'

async def _fresh(req, call_next):
    "Pages are never cached, so Back and Forward show the session as it is now; assets keep their long cache."
    r = await call_next(req)
    if r.headers.get('content-type', '').startswith('text/html'): r.headers['Cache-Control'] = 'no-store'
    return r

def mk_app(learning:Learning, ask=None, transcribe=None, names=None, sources=None):
    "The app over `learning`; `ask` is the model, `transcribe` the speech to text, `sources` ground the tutor, `names` the blocks to connect."
    from abhyasa.voice import Speech
    if transcribe is None: from abhyasa.voice import transcribe
    ask = ask if isinstance(ask, Router) else Router(ask or rishi_ask())   # a model for each task, from the settings
    hooks.clear(); RouteOverrides.nav.clear()
    from abhyasa.voice import cfg_dir
    cfg_dir().mkdir(parents=True, exist_ok=True)
    app, rt = fast_app(hdrs=HDRS(), pico=False, default_hdrs=False, bodykw=dict(hx_boost='true'),
                       key_fname=str(cfg_dir()/'.sesskey'))   # not the working folder: an app may start in /, which is read only   # htmx and fasthtml.js come from core/vendor; links load in place
    if sources is None: sources = [VaultSource(learning), *([vs] if (vs := VedicSource()).dbs() else [])]
    pool = ThreadPoolExecutor(2)
    svc = dict(learning=learning, tutor=Tutor(learning, ask, sources=sources, pool=pool), ask=ask, transcribe=transcribe,
               speech=Speech(transcribe), pool=pool, sessions={}, sources=sources)
    app.state.blocks = connect_all(app, blocks(*([names] if names else [])), **svc)
    app.state.svc = svc
    serve_assets(app)
    app.add_middleware(BaseHTTPMiddleware, dispatch=_fresh)
    app.get('/health')(lambda: JSONResponse(dict(status='ok')))
    app.get('/favicon.ico')(lambda: Response(FAVICON, media_type='image/svg+xml'))
    app.router.routes.insert(0, app.router.routes.pop())   # before fast_app's static route, which answers 404 for it
    return app

def main():
    "Serve the app on loopback."
    import uvicorn
    p = argparse.ArgumentParser(description='abhyasa: a learning harness that makes you think')
    p.add_argument('--port', type=int, default=cfg.port)
    p.add_argument('--vault', default=cfg.vault, help='the vault file; default $ABHYASA_VAULT, then vishalakshi\'s')
    p.add_argument('--model', default=None, help='a rishi model name; default $ABHYASA_MODEL or claude/sonnet')
    a = p.parse_args()
    lr = Learning(a.vault)
    print(f'abhyasa on http://{cfg.host}:{a.port}  ({lr})')
    uvicorn.run(mk_app(lr, rishi_ask(a.model)), host=cfg.host, port=a.port, log_level='warning')
