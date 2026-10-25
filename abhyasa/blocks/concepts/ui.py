from pathlib import Path
from fasthtml.common import *
from abhyasa.core import Md, DepthBar, when, run, asset_css
from abhyasa.model import DEPTHS, recall
from .cfg import Routes

_P = Path(__file__).parent
def css(): return asset_css(_P/'concepts.css')

def ConceptList(cs):
    return Ul(*[Li(A(c.name, href=Routes.of(c.slug)), DepthBar(c.floor), Span(f"  {c.subject} · {when(c.due) if c.seen else 'new'}", cls='mute'))
                for c in cs], cls='plain concepts'), css()

def Refs(slugs, by):
    have = [s for s in slugs if s in by]
    return Ul(*[Li(A(by[s].name, href=Routes.of(s)), DepthBar(by[s].floor)) for s in have], cls='plain') if have else P('none', cls='mute')

def _src(p):
    t = p.get('title') or p.get('lesson') or p.get('term') or p.get('key') or p.get('src')
    return A(t, href=p['url']) if p.get('url') else t

def ConceptPage(c, by, attempts):
    head = P(c.subject, ' · floor ', DEPTHS[c.floor], DepthBar(c.floor), ' · ',
             f"recall {recall(c):.0%} · {when(c.due)}" if c.seen else 'new', cls='mute')
    return (css(), H1(c.name), head, Md(c.statement or '', cls='statement'), Div(*run('concept_actions', c), cls='row'),
            *([H2('Misconceptions seen'), Ul(*map(Li, c.misconceptions))] if c.misconceptions else []),
            H2('Needs first'), Refs(c.prereqs, by), H2('Related'), Refs(c.related, by),
            H2('Your attempts'),
            Ul(*[Li(Md(a.question), P(Span('Right' if a.correct else 'Not right', cls='ok' if a.correct else 'no'), a.answer or 'no answer', cls='mute'))
                 for a in attempts], cls='plain attempts')
            if attempts else P('none yet', cls='mute'),
            *([H2('Source'), Ul(*[Li(_src(p)) for p in c.provenance], cls='plain')] if c.provenance else []))

def Subjects(subs):
    return (H2('Subjects'), Ul(*[Li(A(r['subject'] or 'general', href=f"{Routes.base}?subject={r['subject'] or ''}"),
                                     Span(f"  {r['n']} concepts", cls='mute')) for r in subs], cls='plain'))
