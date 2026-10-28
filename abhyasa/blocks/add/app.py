"Grow the graph: paste text, name a vault document, give a link for a walk, or import vedicreader."
import time
from fasthtml.common import *
from abhyasa.core import Page, RouteOverrides
from abhyasa.sources import extract, from_vault, from_vedicreader
from abhyasa.settings import val
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask')

def connect(app, ctx):
    lr = ctx.learning
    ask = ctx.ask   # the engine picks the model of each task (`for_task`) on each call, so a settings change works at once

    def page():
        return Page('Add', H1('Add a source'),
            P('Paste text, or name a vault document by id, source or title. The tutor finds its core ideas.', cls='mute'),
            Form(Label('Text', Textarea(name='text', rows=4, autofocus=True, placeholder='Paste a text. ⌘↵ finds its concepts.')),
                 Div(Label('Subject', Input(type='text', name='subject', placeholder='e.g. ml, sanskrit, philosophy')),
                     Label('Or a vault document', Input(type='text', name='ref', placeholder='an id, a source or a title')), cls='pair'),
                 Div(Button('Find concepts ', Kbd('⌥S'), cls='go', data_wait='Reading and finding concepts…', data_skel='#out'), cls='row'),
                 hx_post=Routes.base, hx_target='#out'),
            Div(id='out'),
            H2('As a walk, in reading order'),
            P('The tutor takes one idea at a time, in the order of a document, a text, a topic or a link. You read the passage and answer a check.', cls='mute'),
            Form(Div(Label('A vault document', Input(type='text', name='ref', placeholder='an id, a source or a title')),
                     Label('Or a topic', Input(type='text', name='topic', placeholder='for example: how attention works')), cls='pair'),
                 Label('Or a text', Textarea(name='text', rows=3, placeholder='Paste a text.')),
                 Label('Its title', Input(type='text', name='title', placeholder='for a pasted text')),
                 Div(Label('From a link', Input(type='text', name='url', placeholder='an arXiv id, a PDF, a docs page or a GitHub repo')),
                     Label('Pages to read', Input(type='number', name='pages', min=1, max=val('links.cap'), value=val('links.pages'))), cls='pair'),
                 Label(Input(type='checkbox', name='tool'), ' It is a library or a command-line tool. Code and tools open in Leela.', cls='tick'),
                 P('abhyasa gets the pages of a link only when you send this form. It reads only the pages in the folder of the link.', cls='mute'),
                 Div(Button('Make a walk', cls='go', data_wait='Making the walk…', data_skel='#walk-out'), cls='row'),
                 hx_post='/walk/new', hx_target='#walk-out'),
            Div(id='walk-out'),
            H2('vedicreader'), P('Sanskrit lessons and terms, and the jyotiṣa grahas, rāśis and nakṣatras, from the repo files.', cls='mute'),
            Button('Import vedicreader', hx_post=Routes.vedicreader, hx_target='#vr', data_wait='Importing…', data_skel='#vr'), Div(id='vr'), on='Add', crumbs=[('Today', '/')])

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
