"""The screen guide: Hyper+E or Explain on any page, and the tutor answers with a board drawn over the page.

A concept can have one explainer video. The concept page shows it with its tools (find, paste, remove); the walk step shows it
through the `step_needs` hook. The ask route adds the cues of the video on the page from the vault."""
import asyncio, json, logging, queue, threading, time
from fasthtml.common import *
from starlette.responses import StreamingResponse
from abhyasa.core import hook
from abhyasa.guide import (FigureCache, Withheld, clean_context, concept_video, explain, figure_labels, file_video, find_explainer, set_video,
                           video_of, vision_ask)
from abhyasa.voice import cfg_dir
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('ask', 'learning', 'sources')
IMAGES = (b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF87a', b'GIF89a')
FIGURE_BYTES = 8_000_000
ASK_BYTES = 200_000
POLL = .25        # the seconds between two looks at whether the page still reads the board
WARM_EVERY = 30.   # the least seconds between two warm calls of the guide backend
WITHHELD = 'The guide did not send this, because your privacy setting withholds it. Change it in Settings.'   # the guard refused: personal data and `cli.pii` refuse
NO_QUERY = 'The tutor did not search, because the name of this idea holds a key or personal data. Paste a link.'   # `safe_query` refused the web query
log = logging.getLogger(__name__)

def why(e) -> str:
    "The words for the learner when a video could not be filed."
    s = str(e)
    return s if s.startswith(('This is not', 'abhyasa')) else 'abhyasa could not read this video. Try another link.'

def is_image(b:bytes) -> bool: return b.startswith(IMAGES) or (b[:4] == b'RIFF' and b[8:12] == b'WEBP')

def connect(app, ctx):
    ask, lr, sources = ctx.ask, ctx.learning, ctx.sources
    figs = FigureCache(cfg_dir()/'guide-figures.json')
    warmed, warm_lock = [-WARM_EVERY], threading.Lock()

    def warm():
        "Start the backend of the guide job in the background, with no model call, at most once in `WARM_EVERY` seconds. The app starts it too."
        with warm_lock:
            if time.monotonic() - warmed[0] < WARM_EVERY or not hasattr(ask, 'warm'): return Response(status_code=204)
            warmed[0] = time.monotonic()
        ask.warm(['guide'])
        return Response(status_code=204)

    async def figure(req, alt:str=''):
        "The label boxes of a figure. The image is in memory for one vision call, and is not kept."
        img = await req.body()
        if not img or len(img) > FIGURE_BYTES or not is_image(img): return JSONResponse(dict(error='Send a PNG, JPEG, GIF or WebP image.'), status_code=415)
        k = figs.key(img)
        if (got := figs.get(k)) is not None: return JSONResponse(dict(key=k, labels=got))
        if (vision := vision_ask(ask)) is None: return JSONResponse(dict(key=k, labels={}, note='The model cannot see pictures.'))
        try: labels = await asyncio.to_thread(figure_labels, vision, img, alt)
        except Withheld: return JSONResponse(dict(error=WITHHELD, labels={}), status_code=403)
        if labels is None: return JSONResponse(dict(key=k, labels={}))   # the call failed: keep nothing, so the next post asks again
        figs.put(k, labels)
        return JSONResponse(dict(key=k, labels=labels))

    async def ask_(req):
        """The board for one question, as server-sent events: `{"step": {…}, "k": n, "tier": "tutor"}` for each step of a sure tutor
        board as soon as it is whole, `{"wait": text}` while the guide looks in the vault or on the web, then `{"board": …}` (the
        whole board, also after its steps), or `{"error": text}`. The model runs on a thread; the page context is never stored."""
        body = await req.body()
        try: d = json.loads(body) if len(body) <= ASK_BYTES else None
        except ValueError: d = None
        said = ' '.join(str((d or {}).get('said') or '').split())
        if not said: return Response('Say or type what you do not understand.', status_code=400, media_type='text/plain')
        ctx_ = clean_context(d.get('ctx'))
        if ctx_.get('video'):   # the cues come from the vault, never from the page
            if (v := await asyncio.to_thread(video_of, lr, ctx_.video['id'])): ctx_.video = v
            else: ctx_.pop('video')
        q, stop = queue.Queue(), threading.Event()   # `stop`: the page stopped reading, so the model stream closes and lets go of its backend
        def run():
            try: q.put(dict(board=explain(ask, ctx_, said, sources=sources, note=lambda t: q.put(dict(wait=t)), lr=lr, stop=stop,
                                          on_step=lambda s, k: q.put(dict(step=s, k=k, tier='tutor')))))
            except Withheld: q.put(dict(error=WITHHELD))
            except Exception as e: log.warning('guide: %r', e); q.put(dict(error='The tutor could not answer. Try again.'))
        threading.Thread(target=run, daemon=True).start()
        async def gen():
            try:
                while True:
                    try: m = await asyncio.to_thread(q.get, True, POLL)
                    except queue.Empty:
                        if await req.is_disconnected(): return   # a newer question, Stop, or a closed tab
                        continue
                    yield f'data: {json.dumps(m)}\n\n'
                    if 'wait' not in m and 'step' not in m: break
            finally: stop.set()
        return StreamingResponse(gen(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    def video_part(c, msg=''):
        e = concept_video(c)
        v = e and video_of(lr, e['vid'])
        return ui.VideoSlot(v, c.slug, msg)

    def concept_of(slug):
        if not (c := lr.concept(slug)): raise HTTPException(404)
        return c

    async def paste(slug:str, url:str=''):
        "File the pasted YouTube link as the explainer of the concept."
        c = concept_of(slug)
        try: await asyncio.to_thread(file_video, lr, url, slug)
        except Withheld: return video_part(c, WITHHELD)
        except Exception as e: log.warning('guide: video %r', e); return video_part(c, why(e))
        return video_part(lr.concept(slug))

    async def find(slug:str):
        "The tutor finds a video for the concept with fossick's `search_yt`, and files it."
        c = concept_of(slug)
        try:
            try: v = await asyncio.to_thread(find_explainer, c.name, c.get('subject') or '')
            except Withheld: return video_part(c, NO_QUERY)
            if not v: return video_part(c, 'The tutor found no short video for this idea. Paste a link.')
            await asyncio.to_thread(file_video, lr, v.url, slug)
        except Withheld: return video_part(c, WITHHELD)
        except Exception as e: log.warning('guide: find video %r', e); return video_part(c, why(e))
        return video_part(lr.concept(slug))

    def drop(slug:str):
        "Take the video away from the concept. Its transcript stays in the vault."
        concept_of(slug); set_video(lr, slug)
        return video_part(lr.concept(slug), 'The video is gone from this idea. Its transcript stays in your vault.')

    @hook('concept_more')
    def video(c): return video_part(c)

    @hook('step_needs')
    def step_video(j, i, c):
        "The explainer video of the idea of the step, when it has one."
        e = concept_video(c)
        return (v := e and video_of(lr, e['vid'])) and ui.Video(v, c.slug) or None

    @hook('nav_extra')
    def go(): return ui.Go()   # in the top bar, so it never covers the page

    @hook('page_extra')
    def parts(): return ui.Parts()

    app.post(Routes.ask)(ask_)
    app.post(Routes.warm)(warm)
    app.post(Routes.figure)(figure)
    app.post(Routes.video)(paste)
    app.post(Routes.find)(find)
    app.post(Routes.drop)(drop)
