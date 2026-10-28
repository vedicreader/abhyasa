"Grow the graph: paste text, name a vault document, give a link for a walk, or import vedicreader."
import time
from fasthtml.common import *
from pathlib import Path
from abhyasa.core import Page, RouteOverrides, Primary, Secondary, Quiet, Choice, asset_css, asset_js
from abhyasa.sources import extract, from_vault, from_vedicreader
from abhyasa.settings import val
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask')
_P = Path(__file__).parent

def connect(app, ctx):
    lr = ctx.learning
    ask = ctx.ask   # the engine picks the model of each task (`for_task`) on each call, so a settings change works at once

    KINDS = (('doc', 'A paper or document'), ('topic', 'A topic'), ('link', 'A link'), ('text', 'A text'))

    def Kind(k, *c):
        "The fields of one choice. Only the chosen one shows and sends (add.js)."
        return Fieldset(*c, cls=f'add-{k}', **({} if k == 'doc' else dict(disabled=True, hidden=True)))

    def Find():
        "Find the core ideas only, with no walk: a Subject for them and the quiet button. A paper and a text use it."
        return (Label('Subject', Input(type='text', name='subject', placeholder='optional, for example: ml, sanskrit')),
                Div(Quiet('Find concepts only', hx_post=Routes.base, hx_target='#walk-out', data_wait='Reading and finding concepts…', data_skel='#walk-out'),
                    Span('The tutor adds the core ideas to your graph and makes no walk.', cls='mute'), cls='row find'))

    def page():
        return Page('Add', H1('Add a source'),
            P('Pick what you have. The tutor makes a walk from it: one idea at a time, in reading order, with a check after each passage.', cls='mute'),
            Form(Choice('kind', KINDS, 'doc', aria_label='What you have'),
                 Kind('doc', Label('A document in your vault', Input(type='text', name='ref', placeholder='an id, a source or a title')), *Find()),
                 Kind('topic', Label('A topic', Input(type='text', name='topic', placeholder='for example: how attention works'))),
                 Kind('link', Div(Label('A link', Input(type='text', name='url', placeholder='an arXiv id, a PDF, a docs page or a GitHub repo')),
                                  Label('Pages to read', Input(type='number', name='pages', min=1, max=val('links.cap'), value=val('links.pages'))), cls='pair'),
                      Label(Input(type='checkbox', name='tool'), ' It is a library or a command-line tool. Code opens in Leela.', cls='tick'),
                      P('abhyasa gets the pages of a link only when you send this form. It reads only the pages in the folder of the link.', cls='mute')),
                 Kind('text', Label('A text', Textarea(name='text', rows=4, placeholder='Paste a text.')),
                      Label('Its title', Input(type='text', name='title', placeholder='for a pasted text')), *Find()),
                 Div(Primary('Make a walk', data_wait='Making the walk…', data_skel='#walk-out'), cls='row'),
                 hx_post='/walk/new', hx_target='#walk-out', cls='add-form'),
            Div(id='walk-out'),
            Details(Summary('More sources'),
                    P('vedicreader: Sanskrit lessons and terms, and the jyotiṣa grahas, rāśis and nakṣatras, from the repo files.', cls='mute'),
                    Secondary('Import vedicreader', hx_post=Routes.vedicreader, hx_target='#vr', data_wait='Importing…', data_skel='#vr'), Div(id='vr'), cls='more'),
            on='Add', crumbs=[('Today', '/')], extra=(asset_css(_P/'add.css'), asset_js(_P/'add.js', defer=True)))

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
