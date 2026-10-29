"The vault viewer: any document on any shelf, readable, with what you can do with it and the concepts that link to it."
import json, re, time
from pathlib import Path
from urllib.parse import quote
from fasthtml.common import *
from fastcore.utils import first
from abhyasa.core import Page, hook
from abhyasa.sources import extract, figure_path
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask')
_SHELF = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_IMG = re.compile(r'!\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)')   # a markdown image: ![alt](link "title")
IMG_MAX = 20 << 20   # the largest image file that the page sends: 20 MB

def connect(app, ctx):
    lr = ctx.learning
    ask = ctx.ask   # the engine picks the model of each task (`for_task`) on each call, so a settings change works at once

    def _get(shelf, doc_id):
        "The shelf and the docs row, or None when the shelf name is unsafe or the document is not there."
        if not _SHELF.match(shelf): return None, None
        try: sh = lr.vault if shelf == 'store' else lr.vault.shelf(shelf)
        except Exception: return None, None
        return sh, first(sh.t.docs(where='id=?', where_args=[doc_id]))

    def linked(shelf, doc_id):
        return [c for c in lr.concepts() if any(l.get('src') == f'vault:{shelf}' and str(l.get('ref', '')).split('#')[0] == doc_id
                                               for l in c.get('seen_in') or [])]

    def image(d, link):
        "The file of the image `link` of the document `d`, from its own assets folder, when it is an image under the size cap; else None."
        f = figure_path(lr, d['source'] or '', link)
        p = f and Path(lr.vault.assets())/f
        return p if p and p.stat().st_size <= IMG_MAX else None

    def images(shelf, d, text):
        "`text` with each image that the document has as a link to the image route, and the other images out; and the set of those links."
        urls = set()
        def one(m):
            if not image(d, m[2]): return ''
            urls.add(u := Routes.img_of(shelf, quote(d['id'], safe=''), m[2]))
            return f'![{m[1]}]({u})'
        return _IMG.sub(one, text), urls

    def doc(shelf:str, doc_id:str):
        sh, d = _get(shelf, doc_id)
        if d is None: return Page('Not found', H1('No such document'), P(f'The {shelf} shelf has no document {doc_id}.', cls='mute'), crumbs=[('Today', '/')])
        text, imgs = images(shelf, d, sh.document(doc_id, max_chars=200000).text)
        return Page(d['title'] or doc_id, *ui.DocPage(d, json.loads(d['meta'] or '{}'), text, shelf, linked(shelf, doc_id), imgs), crumbs=[('Today', '/')])

    def img(shelf:str, doc_id:str, f:str=''):
        "An image of the document, only from its own assets folder, only an image file and only under the size cap."
        sh, d = _get(shelf, doc_id)
        p = d is not None and f and image(d, f)
        return FileResponse(p) if p else Response(status_code=404)

    def learn(shelf:str, doc_id:str):
        sh, d = _get(shelf, doc_id)
        if d is None: return P('No such document.', cls='mute')
        slugs = extract(lr, ask, sh.document(doc_id).text, '', dict(src=f'vault:{shelf}', ref=doc_id, title=d['title'], at=time.time()))
        if not slugs: return P('No concepts found.', cls='mute')
        return Div(Span('Concepts from this document', cls='lbl'), Ul(*[Li(A(lr.concept(s).name, href=f'/c/{s}')) for s in slugs], cls='plain'))

    @hook('pane_title')
    def pane_title(url):
        "The title of the document at `url` (`/v/<shelf>/<id>`) in the side pane; None for another page."
        m = re.match(r'/v/([^/?#]+)/([^/?#]+)(?:[?#]|$)', url or '')
        return m and (d := _get(*m.groups())[1]) is not None and (d['title'] or d['id']) or None

    app.get(Routes.doc)(doc)
    app.post(Routes.learn)(learn)
    app.get(Routes.img)(img)
