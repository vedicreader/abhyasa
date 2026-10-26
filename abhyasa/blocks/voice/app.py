"Speech to text on this machine: a mic button for any text box that listens until you stop it, and the routes that transcribe."
import re, json, asyncio
from pathlib import Path
from fasthtml.common import *
from starlette.responses import StreamingResponse
from abhyasa.core import hook, asset_js, asset_css
from abhyasa.voice import settings
from .cfg import Routes

__all__ = ['CAPS', 'connect', 'MicButton', 'hint_for']
CAPS = ('speech', 'learning')
_P = Path(__file__).parent

def MicButton(into:str, concept:str='', id:str='mic', cls:str='mic'):
    "A toggle that listens, sends each spoken segment, and appends the text to the element with id `into`. ⌥D presses it."
    vad = asset_js(_P/'vad.js').attrs['src']   # the AudioWorklet loads it by URL
    return (Button(Span('Speak', cls='say'), I(cls='lvl'), ' ', Kbd('⌥D'), type='button', id=id, cls=cls, onclick='abhyasaMic(this)',
                   title='Speak your thinking. The text goes into the box while you talk. Press again to stop.',
                   data_into=into, data_concept=concept, data_vad=vad, data_start=Routes.start,
                   data_seg=Routes.seg.format(did=''), data_stop=Routes.stop.format(did=''), data_events=Routes.events.format(did='')),
            asset_js(_P/'voice.js'), asset_css(_P/'voice.css'))

def hint_for(learning, slug:str) -> str:
    "Words the speaker can use for concept `slug`: its name, aliases, prerequisites, and the IAST words of its statement."
    c = learning.concept(slug) if slug else None
    if not c: return ''
    ws = [c.name, *(c.get('aliases') or [])]
    ws += [p.name for s in (c.get('prereqs') or []) if (p := learning.concept(s))]
    ws += [w for w in re.findall(r'\w+', c.get('statement') or '') if not w.isascii()]   # Sanskrit terms; the text stays on the server
    return ', '.join(dict.fromkeys(w for w in ws if w))[:500]

def connect(app, ctx):
    sp = ctx.speech

    async def stt(req, hint:str=''):
        audio = await req.body()
        try: return JSONResponse(dict(text=await asyncio.wrap_future(sp.submit(sp.fn, audio, hint=hint))))
        except Exception as e: return JSONResponse(dict(text='', error=str(e)), status_code=500)

    def start(concept:str=''):
        return JSONResponse(dict(id=sp.start(hint_for(ctx.learning, concept)), segment=settings()['stt']['segment'], status=sp.status))

    async def seg(req, did:str, seq:int):
        if not (d := sp.runs.get(did)): return JSONResponse(dict(error='no such dictation'), status_code=404)
        d.add(seq, await req.body())
        return JSONResponse(dict(ok=True, pending=d.pending))

    def stop(did:str, n:int):
        if not (d := sp.runs.get(did)): return JSONResponse(dict(error='no such dictation'), status_code=404)
        d.stop(n)
        return JSONResponse(dict(ok=True))

    def events(did:str):
        if not (d := sp.runs.get(did)): return Response('no such dictation', status_code=404)
        async def gen():
            while True:
                r = await asyncio.to_thread(d.next, 10)
                if r is None: yield ': still listening\n\n'; continue   # keeps the stream open
                yield f'data: {json.dumps(r)}\n\n'
                if r.get('done'): sp.runs.pop(did, None); break
        return StreamingResponse(gen(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    @hook('answer_tools')
    def mic(q, into): return MicButton(into, q.get('concept', ''))

    @hook('page_extra')
    def anywhere():
        "On each page: a mic for each box with `data-mic`, and ⌥D into the box in focus. The floating mic shows while it listens."
        return MicButton('', id='mic-float', cls='mic mic-float')

    sp.warm()   # the first segment should not wait for the model to load
    app.post(Routes.stt)(stt)
    app.post(Routes.start)(start)
    app.post(Routes.seg)(seg)
    app.post(Routes.stop)(stop)
    app.get(Routes.events)(events)
