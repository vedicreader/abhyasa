"The vault viewer: any document on any shelf, readable, with what you can do with it and the concepts that link to it."
import json, re, time
from fasthtml.common import *
from fastcore.utils import first
from abhyasa.core import Page
from abhyasa.sources import extract
from abhyasa.llm import for_task
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask')
_SHELF = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

def connect(app, ctx):
    lr = ctx.learning
    ask = lambda prompt, sp='': for_task(ctx.ask, 'extract')(prompt, sp)   # looked up on each call, so a settings change works at once

    def _get(shelf, doc_id):
        "The shelf and the docs row, or None when the shelf name is unsafe or the document is not there."
        if not _SHELF.match(shelf): return None, None
        try: sh = lr.vault if shelf == 'store' else lr.vault.shelf(shelf)
        except Exception: return None, None
        return sh, first(sh.t.docs(where='id=?', where_args=[doc_id]))

    def linked(shelf, doc_id):
        return [c for c in lr.concepts() if any(l.get('src') == f'vault:{shelf}' and str(l.get('ref', '')).split('#')[0] == doc_id
                                               for l in c.get('seen_in') or [])]

    def doc(shelf:str, doc_id:str):
        sh, d = _get(shelf, doc_id)
        if d is None: return Page('Not found', H1('No such document'), P(f'The {shelf} shelf has no document {doc_id}.', cls='mute'))
        text = sh.document(doc_id, max_chars=200000).text
        return Page(d['title'] or doc_id, *ui.DocPage(d, json.loads(d['meta'] or '{}'), text, shelf, linked(shelf, doc_id)))

    def learn(shelf:str, doc_id:str):
        sh, d = _get(shelf, doc_id)
        if d is None: return P('No such document.', cls='mute')
        slugs = extract(lr, ask, sh.document(doc_id).text, '', dict(src=f'vault:{shelf}', ref=doc_id, title=d['title'], at=time.time()))
        if not slugs: return P('No concepts found.', cls='mute')
        return Div(Span('Concepts from this document', cls='lbl'), Ul(*[Li(A(lr.concept(s).name, href=f'/c/{s}')) for s in slugs], cls='plain'))

    app.get(Routes.doc)(doc)
    app.post(Routes.learn)(learn)
