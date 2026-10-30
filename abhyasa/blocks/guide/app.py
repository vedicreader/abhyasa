"The screen guide: Hyper+E or Explain on any page, and the tutor answers with a board drawn over the page."
import asyncio, json
from fasthtml.common import *
from starlette.responses import StreamingResponse
from abhyasa.core import hook
from abhyasa.guide import FigureCache, figure_labels, vision_ask
from abhyasa.voice import cfg_dir
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('ask', 'learning', 'sources')
IMAGES = (b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF87a', b'GIF89a')
FIGURE_BYTES = 8_000_000

def is_image(b:bytes) -> bool: return b.startswith(IMAGES) or (b[:4] == b'RIFF' and b[8:12] == b'WEBP')

def connect(app, ctx):
    ask, lr = ctx.ask, ctx.learning
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

    @hook('page_extra')
    def parts(): return ui.Parts()

    app.post(Routes.figure)(figure)
