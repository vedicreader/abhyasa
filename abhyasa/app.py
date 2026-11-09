"The web app: `fast_app`, the services, and `connect_all` over the blocks in `NAMES` order. Loopback only."
import argparse, atexit, logging, threading, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from starlette.middleware.base import BaseHTTPMiddleware
from fasthtml.common import *
from abhyasa.core import cfg, RouteOverrides, connect_all, serve_assets, serve_feedback, serve_watch, HDRS, look_before, hooks
from abhyasa.core.keys import write_sanketa_pack
from abhyasa.core.leela import write_address, drop_address, LOCAL_HOSTS
from abhyasa.blocks import blocks
from abhyasa.learner import Learning
from abhyasa.tutor import Tutor
from abhyasa.models import route_ask, Router
from abhyasa.sources import VaultSource
from abhyasa.path import Researcher
from abhyasa.learner import close_jobs, CtxPool, use_config

log = logging.getLogger(__name__)

__all__ = ['mk_app', 'stop_app', 'SESSION_COOKIE', 'main']

SESSION_COOKIE = 'abhyasa_session'   # cookies ignore the port: a host app on the same name keeps its own `session_`

FAVICON = (Path(__file__).parent/'core'/'favicon.svg').read_text()   # design/logo/abhyasa-icon.svg

async def _fresh(req, call_next):
    "Pages are never cached, so Back and Forward show the session as it is now; assets keep their long cache."
    r = await call_next(req)
    if r.headers.get('content-type', '').startswith('text/html'): r.headers['Cache-Control'] = 'no-store'
    return r


SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')

class LocalOnly:
    """The app answers only itself. A Host that is not loopback is refused, so a DNS-rebinding page cannot read the vault. A request
    that the browser marks cross-site (`Sec-Fetch-Site`) is refused, so an `<img>` on another page cannot start a session. A POST
    whose `Origin` is not this app is refused, so another page cannot change settings, keys or the vault. Pure ASGI, so streams pass."""
    def __init__(self, app, hosts=LOCAL_HOSTS): self.app, self.hosts = app, tuple(hosts)
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http' and (why := self.refuse(scope)):
            await send(dict(type='http.response.start', status=403, headers=[(b'content-type', b'text/plain; charset=utf-8')]))
            return await send(dict(type='http.response.body', body=why.encode()))
        return await self.app(scope, receive, send)
    def refuse(self, scope) -> str:
        "Why to refuse this request, or ''."
        from urllib.parse import urlsplit
        h = {k.decode('latin-1').lower(): v.decode('latin-1') for k, v in scope.get('headers', [])}
        host = h.get('host', '')
        name = urlsplit(f'//{host}').hostname or ''
        if name not in self.hosts and not any(h.startswith('.') and name.endswith(h) for h in self.hosts): return f'abhyasa answers only on this Mac, not for the host {host!r}.'
        if h.get('sec-fetch-site') == 'cross-site': return 'abhyasa does not answer requests from other web sites.'
        if scope['method'] not in SAFE_METHODS and (o := h.get('origin')) and o != 'null':
            if urlsplit(o).netloc != host: return 'abhyasa does not take changes from other web sites.'
        return ''

class UseConfig:
    "ASGI middleware: each request, and each job it starts, keeps abhyasa's files in the folder `path`."
    def __init__(self, app, path): self.app, self.path = app, path
    async def __call__(self, scope, receive, send):
        with use_config(self.path): return await self.app(scope, receive, send)

def mk_app(learning:Learning, ask=None, transcribe=None, names=None, sources=None, hosts=LOCAL_HOSTS, warm_speech=True, config=None):
    "The app over `learning`; `config` is the folder of a host for the session key and every other file (the settings file and key files of abhyasa are never read); `ask` is the model, `transcribe` the speech to text, `sources` ground the tutor, `names` the blocks to connect, `hosts` the Host names it answers, `warm_speech` loads the speech model at start."
    with use_config(config): return _mk_app(learning, ask, transcribe, names, sources, hosts, warm_speech, config)

def _mk_app(learning, ask, transcribe, names, sources, hosts, warm_speech, config):
    from abhyasa.models import Speech, Speaker
    if transcribe is None: from abhyasa.models import transcribe
    ask = ask if isinstance(ask, Router) else Router(ask or route_ask())   # a model for each task, from the settings
    hooks.clear(); RouteOverrides.nav.clear(); RouteOverrides.subtabs.clear(); RouteOverrides.gear = None
    try: learning.repair_subjects()   # one time on a vault: a concept in General gets the subject of its walk
    except Exception as e: logging.getLogger(__name__).warning('abhyasa could not repair the subjects of the concepts: %r', e)
    from abhyasa.models import cfg_dir
    cfg_dir().mkdir(parents=True, exist_ok=True)
    app, rt = fast_app(hdrs=HDRS(), pico=False, default_hdrs=False, bodykw=dict(hx_boost='true'), before=look_before,
                       key_fname=str(cfg_dir()/'.sesskey'), session_cookie=SESSION_COOKIE)   # not the working folder: an app may start in /, which is read only   # htmx and fasthtml.js come from core/vendor; links load in place
    pool = CtxPool(2)
    if sources is None: sources = [VaultSource(learning)]
    svc = dict(learning=learning, tutor=Tutor(learning, ask, sources=sources, pool=pool), ask=ask, transcribe=transcribe,
               speech=Speech(transcribe), speaker=Speaker(), pool=pool, sessions={}, sources=sources,
               research=Researcher(learning, ask))   # research has its own pool of one worker, so a long search never holds a demo or a note
    app.state.warm_speech, app.state.stop_lock = warm_speech, threading.Lock()
    app.state.pools = [pool, svc['research'].pool, svc['research'].agents, svc['speech'].ex, svc['speaker'].ex]
    app.state.blocks = connect_all(app, blocks(*([names] if names else [])), **svc)
    try: close_jobs(learning)   # no job lives across a restart: a row that says `running` is `closed` now
    except Exception as e: logging.getLogger(__name__).warning('abhyasa could not close the old job rows: %r', e)
    try: hooks.run('app_start')   # after close_jobs, so the row of a job that starts now stays `running`
    except Exception as e: logging.getLogger(__name__).warning('abhyasa could not start the jobs of the start: %r', e)
    try: svc['research'].resume()   # a restart stopped the searches of the steps that are still pending: look again on the research pool
    except Exception as e: logging.getLogger(__name__).warning('abhyasa could not look again for the pending sources: %r', e)
    app.state.svc = svc
    serve_assets(app)
    serve_feedback(app, learning)   # the feedback row under a demo or a lesson, in every block
    serve_watch(app)   # a YouTube video in the side pane
    app.add_middleware(BaseHTTPMiddleware, dispatch=_fresh)
    if config is not None: app.add_middleware(UseConfig, path=config)
    app.add_middleware(LocalOnly, hosts=hosts)   # added last, so it runs first
    app.get('/health')(lambda: JSONResponse(dict(status='ok')))
    app.get('/favicon.ico')(lambda: Response(FAVICON, media_type='image/svg+xml'))
    app.router.routes.insert(0, app.router.routes.pop())   # before fast_app's static route, which answers 404 for it
    return app

def stop_app(app, timeout=5.0):
    "Stop the research of each walk and the worker pools of `app`; wait at most `timeout` seconds in all, and log the pools that still run."
    if (svc := getattr(app.state, 'svc', None)) is None: return
    with app.state.stop_lock:
        if getattr(app.state, 'stopped', False): return
        app.state.stopped = True
    for ev in list(svc['research'].stops.values()): ev.set()
    for p in app.state.pools: p.shutdown(wait=False, cancel_futures=True)
    waits = [threading.Thread(target=p.shutdown, kwargs=dict(wait=True), daemon=True) for p in app.state.pools]
    for w in waits: w.start()
    end = time.monotonic() + timeout
    for w in waits: w.join(max(0, end - time.monotonic()))
    if left := [getattr(p, '_thread_name_prefix', '') for p, w in zip(app.state.pools, waits) if w.is_alive()]:
        log.warning('abhyasa stopped with worker pools still running: %s', left)

def repair_in_background(app, title_of=None):
    "After the start: give the old papers with an arXiv id for a title their real title, then their steps and talks, on the pool of the app. Return the future; nothing waits for it."
    def run():
        lr = app.state.svc['learning']
        try: out = lr.repair_paper_titles(title_of)
        except Exception as e: out = None; log.warning('abhyasa could not repair the titles of the papers: %r', e)
        try: lr.repair_id_titles()   # the steps and the talks of a walk that has its title now
        except Exception as e: log.warning('abhyasa could not give the talks the titles of their papers: %r', e)
        return out
    return app.state.svc['pool'].submit(run)

def warm_catalog(app):
    "After the start: get the model list on the pool of the app, so the Models tab of Settings has it at once. Return the future."
    from abhyasa import models as llm
    return app.state.svc['pool'].submit(llm.catalog)

def main():
    "Serve the app on loopback."
    import uvicorn
    p = argparse.ArgumentParser(description='abhyasa: a tutor that asks you questions. It starts the web app on this Mac.')
    p.add_argument('--port', type=int, default=cfg.port, help='the port of the web app; default $ABHYASA_PORT, then 5077')
    p.add_argument('--vault', default=cfg.vault, help='the vault file; default $ABHYASA_VAULT, then your vault ($VISHALAKSHI_VAULT, then ~/.vishalakshi/vault.db)')
    p.add_argument('--model', default=None, help='the model id; choose it in Settings. Default $ABHYASA_MODEL, then claude/sonnet')
    a = p.parse_args()
    lr = Learning(a.vault)
    print(f'abhyasa on http://{cfg.host}:{a.port}  ({lr})')
    try: write_sanketa_pack()   # Sanketa shows abhyasa's keys when abhyasa is in front
    except OSError: pass
    ask = Router(route_ask(a.model))
    ask.warm()   # makes the ramabana Agent and starts the backends in the background, so the server starts at once
    app = mk_app(lr, ask)
    repair_in_background(app)
    warm_catalog(app)
    try: write_address(f'http://{cfg.host}:{a.port}', Path(lr.vault.path).resolve()); atexit.register(drop_address)   # Leela links back to a walk
    except (OSError, ValueError) as e: log.warning('abhyasa could not write its address file: %r', e)
    try: uvicorn.run(app, host=cfg.host, port=a.port, log_level='warning')
    finally: stop_app(app)
