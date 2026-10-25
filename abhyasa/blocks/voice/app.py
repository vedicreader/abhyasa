"Speech to text on this machine: a mic button for any text box, and the route that transcribes."
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import hook, asset_js
from .cfg import Routes

__all__ = ['CAPS', 'connect', 'MicButton']
CAPS = ('transcribe',)
_P = Path(__file__).parent

def MicButton(into:str, hint:str=''):
    "A toggle that records, sends WAV to `Routes.stt`, and appends the text to the element with id `into`. ⌥D presses it."
    return (Button('Speak ', Kbd('⌥D'), type='button', id='mic', cls='mic', onclick='abhyasaMic(this)',
                   data_into=into, data_hint=hint, data_url=Routes.stt), asset_js(_P/'voice.js'))

def connect(app, ctx):
    async def stt(req, hint:str=''):
        audio = await req.body()
        try: return JSONResponse(dict(text=ctx.transcribe(audio, hint=hint)))
        except Exception as e: return JSONResponse(dict(text='', error=str(e)), status_code=500)

    @hook('answer_tools')
    def mic(q, into): return MicButton(into, q.name)

    app.post(Routes.stt)(stt)
