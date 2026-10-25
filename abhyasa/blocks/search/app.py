"Search what you learned, and the rest of your vault beside it: one query, every shelf."
from fasthtml.common import *
from abhyasa.core import Page, Md
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning',)

def Hits(hs, text, crumb):
    return Ul(*[Li(Md(text(h)[:300]), Span(crumb(h), cls='mute')) for h in hs], cls='plain') if hs else P('nothing', cls='mute')

def connect(app, ctx):
    lr = ctx.learning

    def search(q:str=''):
        if not q.strip(): return Page('Search', H1('Search'), P('Type in the box at the top.', cls='mute'))
        mine = lr.search(q, limit=12)
        try: other = lr.v.elsewhere(q, limit=2, max_read=300)
        except Exception: other = []
        return Page('Search', H1(f'“{q}”'),
                    H2('In what you learned'), Hits(mine, lambda h: h['snippet'], lambda h: h['breadcrumb']),
                    H2('In your vault'), Hits(other, lambda h: h.text, lambda h: h.breadcrumb))

    app.get(Routes.base)(search)
