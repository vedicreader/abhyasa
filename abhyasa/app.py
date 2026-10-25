"The web app: `fast_app`, the services, and `connect_all` over the blocks in `NAMES` order. Loopback only."
import argparse
from concurrent.futures import ThreadPoolExecutor
from fasthtml.common import *
from abhyasa.core import cfg, RouteOverrides, connect_all, serve_assets, HDRS
from abhyasa.core import hooks
from abhyasa.blocks import blocks
from abhyasa.store import Learning
from abhyasa.tutor import Tutor
from abhyasa.llm import rishi_ask

__all__ = ['mk_app', 'main']

def mk_app(learning:Learning, ask=None, transcribe=None, names=None):
    "The app over `learning`; `ask` is the model, `transcribe` the speech to text, `names` the blocks to connect."
    if transcribe is None: from abhyasa.voice import transcribe
    ask = ask or rishi_ask()
    hooks.clear(); RouteOverrides.nav.clear()
    app, rt = fast_app(hdrs=HDRS(), pico=False)
    svc = dict(learning=learning, tutor=Tutor(learning, ask), ask=ask, transcribe=transcribe,
               pool=ThreadPoolExecutor(2), sessions={})
    app.state.blocks = connect_all(app, blocks(*([names] if names else [])), **svc)
    app.state.svc = svc
    serve_assets(app)
    app.get('/health')(lambda: JSONResponse(dict(status='ok')))
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
