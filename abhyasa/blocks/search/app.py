"Search what you learned, and the rest of your vault beside it: one query, every shelf."
from fasthtml.common import *
from abhyasa.core import Page, Md
from abhyasa.settings import val
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning',)

def Hits(hs, text, crumb, href=lambda h: None):
    def item(h):
        u = href(h)
        return Li(Md(text(h)[:val('lists.snippet')]), A(crumb(h), href=u, cls='mute') if u else Span(crumb(h), cls='mute'))
    return Ul(*map(item, hs), cls='plain') if hs else P('nothing', cls='mute')

def connect(app, ctx):
    lr = ctx.learning

    def search(q:str=''):
        if not q.strip(): return Page('Search', H1('Search'), P('Type in the box at the top.', cls='mute'), crumbs=[('Today', '/')])
        mine = lr.search(q, limit=val('lists.search'))
        try: other = lr.v.elsewhere(q, limit=val('lists.elsewhere'), max_read=val('lists.snippet'))
        except Exception: other = []
        return Page('Search', H1(f'“{q}”'),
                    H2('In what you learned'), Hits(mine, lambda h: h['snippet'], lambda h: h['breadcrumb'], lambda h: f"/v/learning/{h['doc_id']}"),
                    H2('In your vault'), Hits(other, lambda h: h.text, lambda h: h.breadcrumb, lambda h: f'/v/{h.store}/{h.doc_id}'), crumbs=[('Today', '/')])

    app.get(Routes.base)(search)
