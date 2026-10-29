"Search what you learned, and the rest of your vault beside it: one query, every shelf."
import re, time
from fasthtml.common import *
from abhyasa.core import Page, Md, Empty, meta, n_of, ago
from abhyasa.settings import val
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning',)

def short(s, n=None):
    "The first `n` characters of `s`, cut at a word."
    s, n = ' '.join(str(s or '').split()), n or val('lists.snippet')
    return s if len(s) <= n else s[:n].rsplit(' ', 1)[0] + '…'

def Hit(h, by):
    "One hit of what you learned, shown by its kind: a plain title as the link, a short line, and a quiet meta line."
    k, m = h['kind'], h['meta']
    if k == 'concept':
        return Li(A(m.get('name') or h['title'], href=f"/c/{m.get('slug', '')}", cls='hit'), P(short(m.get('statement')), cls='line'),
                  P(meta('An idea', m.get('subject')), cls='mute'))
    if k == 'attempt':
        c = by.get(m.get('concept'))
        return Li(A(short(m.get('question'), 140), href=f"/c/{m.get('concept', '')}", cls='hit'),
                  P(short(m.get('answer'), 200), cls='line mute') if m.get('answer') else '',
                  P(meta('Your answer', c and c.name, ago(m.get('at'))), cls='mute'))
    if k == 'journey':
        walk = m.get('mode') == 'walk'
        return Li(A(m.get('title') or h['title'], href=f"/{'w' if walk else 'j'}/{m.get('id', '')}", cls='hit'),
                  P(short(m.get('goal')), cls='line') if m.get('goal') else '', P('A walk' if walk else 'A journey', cls='mute'))
    if k == 'session':
        log = m.get('log') or []
        n, ok = (len(log), sum(bool(r.get('correct')) for r in log)) if 'log' in m else (m.get('asked', 0), m.get('passed', 0))
        names = sorted({by[r['concept']].name for r in log if r.get('concept') in by})
        day = time.strftime('%d %b', time.localtime(m.get('start') or m.get('updated') or time.time())).lstrip('0')
        return Li(A(f'A session on {day}', href=f"/learning/{m.get('id', '')}", cls='hit'),
                  P(', '.join(names), cls='line') if names else '', P(f'{ok} of {n_of(n, "answer")} passed', cls='mute'))
    if k == 'demo':
        c = by.get(m.get('concept'))
        t = h['title'] if not re.search(r'\{[\w.]+\}', h['title'] or '') else c and c.name   # never a slot that is not filled
        return Li(A(t or 'A demo', href=f"/c/{m.get('concept', '')}", cls='hit'), P(meta('A demo', c and c.name), cls='mute'))
    if k == 'talk':
        return Li(A(m.get('title') or h['title'], href=f"/t/{m.get('id', '')}", cls='hit'),
                  P(meta('A talk', n_of(len(m.get('slides') or ()), 'slide')), cls='mute'))
    return None   # a kind with no plain view does not show

def Elsewhere(hs):
    "Hits in the rest of your vault: a short passage and where it is."
    item = lambda h: Li(Md(short(h.text)), A(h.breadcrumb, href=f'/v/{h.store}/{h.doc_id}', cls='mute'))
    return Ul(*map(item, hs), cls='plain hits') if hs else Empty('Nothing found.')

def connect(app, ctx):
    lr = ctx.learning

    def search(q:str=''):
        if not q.strip(): return Page('Search', H1('Search'), P('Type in the box at the top.', cls='mute'), crumbs=[('Today', '/')])
        by = {c.slug: c for c in lr.concepts()}
        mine = [x for h in lr.search(q, limit=val('lists.search')) if (x := Hit(h, by)) is not None]
        try: other = lr.v.elsewhere(q, limit=val('lists.elsewhere'), max_read=val('lists.snippet'))
        except Exception: other = []
        return Page('Search', H1(f'“{q}”'),
                    H2('In what you learned'), Ul(*mine, cls='plain hits') if mine else Empty('Nothing found.'),
                    H2('In your vault'), Elsewhere(other), crumbs=[('Today', '/')])

    app.get(Routes.base)(search)
