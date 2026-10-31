"""The screen guide: Hyper+E or Explain on any page, and the tutor answers with a board drawn over the page.

A concept can have one explainer video. The concept page shows it with its tools (find, paste, remove); the walk step shows it
through the `step_needs` hook. The ask route adds the cues of the video on the page from the vault."""
import asyncio, base64, json, logging, queue, secrets, threading, time
from fasthtml.common import *
from starlette.responses import StreamingResponse
from abhyasa.core import hook, run as run_hook
from abhyasa.demo import show_ask
from abhyasa.guide import (FigureCache, Withheld, clean_context, concept_video, explain, figure_labels, file_video, find_explainer, guide_ask, set_video,
                           unsave, video_of, vision_ask, vision_why, where_of)
from abhyasa.settings import SETTINGS, raw, val, set_val
from abhyasa.voice import cfg_dir
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('ask', 'learning', 'sources', 'speaker')
IMAGES = (b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF87a', b'GIF89a')
FIGURE_BYTES = 8_000_000
ASK_BYTES = 200_000
SAY_CHARS = 600   # the most characters of one spoken line: a step says one short line
POLL = .25        # the seconds between two looks at whether the page still reads the board
INFO_EVERY = 30.  # the seconds that the names of the models on each page stay, while no model setting changes
SAVES = 50        # the most pages that the guide saved and that Undo can take back in this run
WARM_EVERY = 30.   # the least seconds between two warm calls of the guide backend
WITHHELD = 'The guide did not send this. It holds personal data, and your privacy setting blocks it. You can change the setting in Settings.'   # the guard refused: personal data and `cli.pii` refuse
NO_QUERY = 'The tutor did not search. The name of this idea holds a key or personal data. Paste a link.'   # `safe_query` refused the web query
log = logging.getLogger(__name__)

def why(e) -> str:
    "The words for the learner when a video could not be filed."
    s = str(e)
    return s if s.startswith(('This is not', 'abhyasa')) else 'abhyasa could not read this video. Try another link.'

def is_image(b:bytes) -> bool: return b.startswith(IMAGES) or (b[:4] == b'RIFF' and b[8:12] == b'WEBP')

def speech() -> dict:
    "Who writes what you say: the speech engine of the settings, and where it runs. Only the OpenAI engine is hosted."
    from abhyasa.voice import current, KNOWN
    try: e, m = current()
    except Exception: e, m = 'gemma', ''
    if e == 'openai': return dict(model='OpenAI', where='hosted', who='OpenAI')
    lab = next((k['label'] for k in KNOWN if k['model'] == m), '')
    return dict(model='Gemma' if e == 'gemma' else lab.split(' (')[0].split(' ')[0] or 'The speech model', where='on this Mac', who='')

def voice_out() -> dict:
    "Who reads the board aloud: the engine of the setting `voice.out`, its name, and where it runs. Only OpenAI is hosted."
    from abhyasa.voice import out_current, out_where
    e, m, v, _ = out_current()
    name = dict(browser='The browser', kokoro='Kokoro', openai='OpenAI').get(e) or m.split('/')[-1]
    return dict(engine=e, model=name, voice=v, where=out_where(e), who='OpenAI' if e == 'openai' else '')

def connect(app, ctx):
    ask, lr, sources, speaker = ctx.ask, ctx.learning, ctx.sources, ctx.speaker
    saves = {}   # the key of each Undo -> what the guide saved, for this run of the app only
    info_ = [0., None, None]   # the time, the names, and the model settings that they are for

    def info():
        "What the page tells before it sends: the model of the guide, the model that reads a figure, the speech engine, the voice setting and the look of a point mark."
        now = tuple(raw(n) for n in SETTINGS if n.startswith(('models.', 'stt.')))   # a save on the Settings page names the new model at once
        if time.monotonic() - info_[0] > INFO_EVERY or info_[1] is None or info_[2] != now:
            from abhyasa.llm import dflt_model
            g = where_of(getattr(guide_ask(ask), 'model', ''))
            routed = hasattr(getattr(ask, 'dflt', None), 'via')
            info_[:] = time.monotonic(), dict(model=g, vision=where_of(ask.name('guide_vision') or dflt_model()) if routed else g, speech=speech()), now
        return {**info_[1], 'voice': bool(val('guide.voice')), 'point': val('guide.point'), 'out': voice_out(), 'say': Routes.say}
    figs = FigureCache(cfg_dir()/'guide-figures.json')
    warmed, warm_lock = [-WARM_EVERY], threading.Lock()

    def warm():
        "Start the backend of the guide job in the background, with no model call, at most once in `WARM_EVERY` seconds, and load the natural voice. The app starts both too."
        with warm_lock:
            if time.monotonic() - warmed[0] < WARM_EVERY: return Response(status_code=204)
            warmed[0] = time.monotonic()
        if hasattr(ask, 'warm'): ask.warm(['guide'])
        speaker.warm()   # nothing for the browser voice or OpenAI; else the model loads on the voice worker
        return Response(status_code=204)

    async def say(req):
        """One line in the natural voice of the settings. JSON `{text, engine, model, voice, speed}` in (only `text` is needed); JSON
        `{audio: base64 WAV, words: [start of each word in s], engine, model, voice, speed, where, who, cached}` out. 409 when the
        setting is the browser voice: then the page speaks. 403 when the guard withheld a line for OpenAI. The lines of this run are
        kept in memory (`Speaker`), so a line said again comes at once."""
        try: d = json.loads(await req.body() or b'{}')
        except ValueError: d = None
        if not isinstance(d, dict): return JSONResponse(dict(error='Send JSON with the text.'), status_code=400)
        text = ' '.join(str(d.get('text') or '').split())[:SAY_CHARS]
        if not text: return JSONResponse(dict(error='There is no text to say.'), status_code=400)
        kw = {k: d[k] for k in ('engine', 'model', 'voice', 'speed') if d.get(k)}
        try: r = await asyncio.to_thread(speaker.say, text, **kw)
        except Withheld: return JSONResponse(dict(error=WITHHELD), status_code=403)
        except ValueError as e: return JSONResponse(dict(error=str(e)), status_code=409 if 'browser' in str(e) else 400)
        except Exception as e:
            log.warning('guide: voice %r', e)
            return JSONResponse(dict(error='The natural voice could not say this line.'), status_code=502)
        return JSONResponse(dict(audio=base64.b64encode(r.pop('wav')).decode(), **r, who='OpenAI' if r['engine'] == 'openai' else ''))

    async def figure(req, alt:str=''):
        "The label boxes of a figure. The image is in memory for one vision call, and is not kept."
        img = await req.body()
        if not img or len(img) > FIGURE_BYTES or not is_image(img): return JSONResponse(dict(error='Send a PNG, JPEG, GIF or WebP image.'), status_code=415)
        k = figs.key(img)
        if (got := figs.get(k)) is not None: return JSONResponse(dict(key=k, labels=got))
        if (vision := vision_ask(ask)) is None: return JSONResponse(dict(key=k, labels={}, note=vision_why(ask) or 'The model cannot see pictures.'))
        try: labels = await asyncio.to_thread(figure_labels, vision, img, alt)
        except Withheld: return JSONResponse(dict(error=WITHHELD, labels={}), status_code=403)
        if labels is None: return JSONResponse(dict(key=k, labels={}))   # the call failed: keep nothing, so the next post asks again
        figs.put(k, labels)   # an empty result before any figure had labels is not kept: the route can have lost the picture
        return JSONResponse(dict(key=k, labels=labels))

    def show_of(words, c):
        "The demo for \"show me …\" to the guide: the card of the `show_me` hook (the demo block), else a link to the idea. None when the page names no idea."
        if not (c.get('slug') and lr.concept(c.slug)): return None
        card = next((x for x in run_hook('show_me', words, dict(where='guide', concept=c.slug)) if x is not None), None)
        return dict(html=to_xml(card)) if card is not None else dict(href=f'/c/{c.slug}')

    async def ask_(req):
        """The board for one question, as server-sent events. Before each step of its work: a state event
        `{"wait": text, "state": "reading"|"asking"|"searching"|"saving", "model", "where": "on this Mac"|"hosted", "who", "query",
        "sources"}`, with only the fields that apply (`abhyasa.guide`, *Never caught unaware*). The server sends "reading" for a web
        page. The page sets "reading" itself while it reads the page, and "drawing" when the first step or the board comes and the
        board starts: the server never sends "drawing". `{"step": {…}, "k": n,
        "tier": "tutor", "point": look}` for each step of a sure tutor board as soon as it is whole. `{"saved": {"title", "url", "undo"}}` when the
        guide filed a web page in the vault: a POST to `undo` takes it away. Then `{"board": …, "point": look}` (the whole board, also after its
        steps; with `hint` when the board counts as a hint on the open check), or `{"error": text}`. The model runs on a thread; the
        page context is never stored. When the page stops reading, the model stream closes. `point` is the setting `guide.point`, for
        the Mac overlay, which has no page of the app. `thread` (in the body, or in `ctx`) is the last 3 turns of the page,
        `[{said, says, t}]`: `clean_context` keeps a good one, and the server keeps none of it after the question. A question that starts
        with "show me" on a page of an idea gets one event `{"show": {"html": card}}` (the card of the `show_me` hook) or
        `{"show": {"href": link}}`, and no board."""
        body = await req.body()
        try: d = json.loads(body) if len(body) <= ASK_BYTES else None
        except ValueError: d = None
        said = ' '.join(str((d or {}).get('said') or '').split())
        if not said: return Response('Say or type your question.', status_code=400, media_type='text/plain')
        raw_ = d.get('ctx') if isinstance(d.get('ctx'), dict) else {}
        ctx_ = clean_context({**raw_, 'thread': d.get('thread', raw_.get('thread'))})   # the thread of the page: in the body, or in the ctx (the Mac)
        if (words := show_ask(said)) is not None and (s := await asyncio.to_thread(show_of, words, ctx_)):   # "show me …": the demo, not a board
            return StreamingResponse(iter([f'data: {json.dumps(dict(show=s))}\n\n']), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
        if ctx_.get('video'):   # the cues come from the vault, never from the page
            if (v := await asyncio.to_thread(video_of, lr, ctx_.video['id'])): ctx_.video = v
            else: ctx_.pop('video')
        q, stop, look = queue.Queue(), threading.Event(), val('guide.point')   # `stop`: the page stopped reading, so the model stream closes and lets go of its backend
        def tell(e):
            if 'saved' not in e: return q.put(e)
            k = secrets.token_urlsafe(9)
            saves[k] = e['saved']
            while len(saves) > SAVES: saves.pop(next(iter(saves)))
            q.put(dict(saved=dict(title=e['saved']['title'], url=e['saved']['url'], undo=Routes.of(Routes.undo, key=k))))
        def run():
            try:
                b = explain(ask, ctx_, said, sources=sources, lr=lr, stop=stop, on_state=tell, on_step=lambda s, k: q.put(dict(step=s, k=k, tier='tutor', point=look)))
                h = next((x for x in run_hook('guide_board', ctx_.page, b) if x), None) if b.get('hint') and not stop.is_set() else None
                if h: b['hint'] = h   # the board was about the open check (`on_check`): the line that the check shows
                else: b.pop('hint', None)
                q.put(dict(board=b, point=look))
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
                    if 'board' in m or 'error' in m: break
            finally: stop.set()
        return StreamingResponse(gen(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    def undo(key:str):
        "Take away the web page that the guide saved, and its link to the concept."
        if not (s := saves.pop(key, None)): return Response('There is nothing to undo.', media_type='text/plain')
        n = unsave(lr, s)
        return Response(f"Removed {s['title']} from your vault." if n else 'There is nothing to undo.', media_type='text/plain')

    def voice(on:str=''):
        "Voice on or off for the boards of the guide: the setting `guide.voice`."
        set_val('guide.voice', on in ('1', 'true', 'on'))
        return Response(status_code=204)

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
        return video_part(lr.concept(slug), 'This idea has no video now. Its transcript stays in your vault.')

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
    def parts(): return ui.Parts(info())

    app.post(Routes.ask)(ask_)
    app.post(Routes.warm)(warm)
    app.post(Routes.figure)(figure)
    app.post(Routes.undo)(undo)
    app.post(Routes.voice)(voice)
    app.post(Routes.say)(say)
    speaker.warm()   # the first line of the first board should not wait for the model to load
    app.post(Routes.video)(paste)
    app.post(Routes.find)(find)
    app.post(Routes.drop)(drop)
