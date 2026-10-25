"Grow the graph: paste text, name a vault document, or import vedicreader."
import time
from fasthtml.common import *
from abhyasa.core import Page, RouteOverrides
from abhyasa.sources import extract, from_vault, from_vedicreader
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask')

def connect(app, ctx):
    lr, ask = ctx.learning, ctx.ask

    def page():
        return Page('Add', H1('Add a source'),
            P('Paste text, or name a vault document by id, source or title. The tutor finds its core ideas.', cls='mute'),
            Form(Label('Text', Textarea(name='text', rows=4, autofocus=True, placeholder='Paste a text. ⌘↵ finds its concepts.')),
                 Div(Label('Subject', Input(type='text', name='subject', placeholder='e.g. ml, sanskrit, philosophy')),
                     Label('Or a vault document', Input(type='text', name='ref', placeholder='an id, a source or a title')), cls='pair'),
                 Div(Button('Find concepts ', Kbd('⌥S'), cls='go', data_wait='Reading and finding concepts…', data_skel='#out'), cls='row'),
                 hx_post=Routes.base, hx_target='#out'),
            Div(id='out'),
            H2('vedicreader'), P('Sanskrit lessons and terms, and the jyotiṣa grahas, rāśis and nakṣatras, from the repo files.', cls='mute'),
            Button('Import vedicreader', hx_post=Routes.vedicreader, hx_target='#vr', data_wait='Importing…', data_skel='#vr'), Div(id='vr'), on='Add')

    def add(subject:str='', text:str='', ref:str=''):
        if not (text.strip() or ref.strip()): return P('Paste text or name a document.', cls='mute')
        try: slugs = from_vault(lr, ask, ref, subject) if ref.strip() else extract(lr, ask, text, subject, dict(src='pasted', at=time.time()))
        except ValueError as e: return P(str(e), cls='mute')
        return Ul(*[Li(A(lr.concept(s).name, href=f'/c/{s}')) for s in slugs], cls='plain')

    def vedicreader(): return P(', '.join(f'{v} {k}' for k, v in from_vedicreader(lr).items()) + ' added.')

    RouteOverrides.nav.append(('Add', Routes.base, 3))
    app.get(Routes.base)(page)
    app.post(Routes.base)(add)
    app.post(Routes.vedicreader)(vedicreader)
