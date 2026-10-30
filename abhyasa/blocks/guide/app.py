"The screen guide: Hyper+E or Explain on any page, and the tutor answers with a board drawn over the page."
import asyncio, json, logging, queue, threading
from fasthtml.common import *
from starlette.responses import StreamingResponse
from abhyasa.core import hook
from abhyasa.guide import FigureCache, Withheld, clean_context, explain, figure_labels, vision_ask
from abhyasa.voice import cfg_dir
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('ask', 'learning', 'sources')
IMAGES = (b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF87a', b'GIF89a')
FIGURE_BYTES = 8_000_000
ASK_BYTES = 200_000
log = logging.getLogger(__name__)

def is_image(b:bytes) -> bool: return b.startswith(IMAGES) or (b[:4] == b'RIFF' and b[8:12] == b'WEBP')

def connect(app, ctx):
    ask, lr, sources = ctx.ask, ctx.learning, ctx.sources
    figs = FigureCache(cfg_dir()/'guide-figures.json')

    async def figure(req, alt:str=''):
        "The label boxes of a figure. The image is in memory for one vision call, and is not kept."
        img = await req.body()
        if not img or len(img) > FIGURE_BYTES or not is_image(img): return JSONResponse(dict(error='Send a PNG, JPEG, GIF or WebP image.'), status_code=415)
        k = figs.key(img)
        if (got := figs.get(k)) is not None: return JSONResponse(dict(key=k, labels=got))
        if (vision := vision_ask(ask)) is None: return JSONResponse(dict(key=k, labels={}, note='The model cannot see pictures.'))
        labels = await asyncio.to_thread(figure_labels, vision, img, alt)
        figs.put(k, labels)
        return JSONResponse(dict(key=k, labels=labels))

    async def ask_(req):
        """The board for one question, as server-sent events: `{"wait": text}` while the guide looks in the vault or on the web, then
        `{"board": …}`, or `{"error": text}`. The model runs on a thread; the page context is never stored."""
        body = await req.body()
        try: d = json.loads(body) if len(body) <= ASK_BYTES else None
        except ValueError: d = None
        said = ' '.join(str((d or {}).get('said') or '').split())
        if not said: return Response('Say or type what you do not understand.', status_code=400, media_type='text/plain')
        ctx_ = clean_context(d.get('ctx'))
        q = queue.Queue()
        def run():
            try: q.put(dict(board=explain(ask, ctx_, said, sources=sources, note=lambda t: q.put(dict(wait=t)), lr=lr)))
            except Withheld: q.put(dict(error='The page holds personal data, and your settings say to keep it on this Mac. The guide did not ask the model.'))
            except Exception as e: log.warning('guide: %r', e); q.put(dict(error='The tutor could not answer. Try again.'))
        threading.Thread(target=run, daemon=True).start()
        async def gen():
            while True:
                m = await asyncio.to_thread(q.get)
                yield f'data: {json.dumps(m)}\n\n'
                if 'wait' not in m: break
        return StreamingResponse(gen(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    @hook('nav_extra')
    def go(): return ui.Go()   # in the top bar, so it never covers the page

    @hook('page_extra')
    def parts(): return ui.Parts()

    app.post(Routes.ask)(ask_)
    app.post(Routes.figure)(figure)
