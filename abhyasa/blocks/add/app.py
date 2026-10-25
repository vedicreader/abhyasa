"Grow the graph: paste text, name a vault document, or import vedicreader."
import time
from fasthtml.common import *
from abhyasa.core import Page, RouteOverrides, Spin
from abhyasa.sources import extract, from_vault, from_vedicreader
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask')

def connect(app, ctx):
    lr, ask = ctx.learning, ctx.ask

    def page():
        return Page('Add', H1('Add a source'),
            P('Paste text, or name a vault document by id, source or title. The tutor finds its core ideas.', cls='mute'),
            Form(Label('Subject', Input(type='text', name='subject', placeholder='e.g. ml, sanskrit, philosophy')),
                 Label('Text', Textarea(name='text', rows=8)), Label('Or a vault document', Input(type='text', name='ref')),
                 Div(Button('Find concepts', cls='go'), Spin('reading…'), cls='row'),
                 hx_post=Routes.base, hx_target='#out', hx_indicator='.spin'),
            Div(id='out'),
            H2('vedicreader'), P('Sanskrit lessons and terms, and the jyotiṣa grahas, rāśis and nakṣatras, from the repo files.', cls='mute'),
            Button('Import vedicreader', hx_post=Routes.vedicreader, hx_target='#vr'), Div(id='vr'), on='Add')

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
