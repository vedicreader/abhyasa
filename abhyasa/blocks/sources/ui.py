"Your documents: one row for each source, with its kind, the walks and talks that use it, and the date that you added it."
import time
from fasthtml.common import *
from abhyasa.core import Empty, Pill, Quiet, meta, n_of
from .cfg import Routes

EMPTY = 'Sources appear here when you start a walk from a paper, a link or a text.'

def day(t) -> str:
    "The date `t` as `30 Oct 2026`; '' with no time."
    return time.strftime('%d %b %Y', time.localtime(t)).lstrip('0') if t else ''

def Used(used):
    "The walks and talks that quote a source, as links."
    if not used: return ''
    return Span('Used in ', *[x for k, (t, h) in enumerate(used) for x in ((', ',) if k else ()) + (A(t, href=h),)], cls='mute used')

def Act(r):
    "Undo for one hour after Start filed a folder or a repo, then Remove."
    if not r.get('root'): return ''
    if r.get('undo'):
        return Quiet('Undo', small=True, type='button', hx_post=Routes.unfile, hx_vals=dict(jid=r.undo, root=r.root), hx_target='closest li', hx_swap='outerHTML')
    return Quiet('Remove', small=True, type='button', hx_post=Routes.remove, hx_vals=dict(shelf=r.shelf, root=r.root), hx_target='closest li', hx_swap='outerHTML',
                 hx_confirm=f'Remove {r.root} from your vault? Your walks keep their steps.')

def Inside(r):
    "The documents of a folder or a repo, or the copies of a paper, in a closed part."
    if len(r.docs) < 2 and not r.get('root'): return ''
    word = 'copy' if r.get('copies') else 'document'
    return Details(Summary(n_of(len(r.docs), word, 'copies' if word == 'copy' else None)),
                   Ul(*[Li(A(t, href=h) if h else t) for t, h in r.docs], cls='plain'), cls='more docs')

def Row(r):
    "One source: its title (a link to the vault viewer), its kind, the walks and talks that use it, the date, and Undo or Remove for a folder or a repo."
    name = A(r.title, href=r.href, cls='jt') if r.href else Span(r.title, cls='jt')
    return Li(Div(name, Pill(r.kind), Span(meta(('filed ' if r.get('root') else 'added ') + day(r.at) if r.at else ''), cls='mute'), Used(r.used), cls='lrow-head'),
              Div(Act(r), cls='lrow-acts'), Inside(r), cls='srow lrow')

def Rows(rs):
    "Each source, the newest first; with none, one line."
    return Ul(*map(Row, rs), cls='plain sources') if rs else Empty(EMPTY)
