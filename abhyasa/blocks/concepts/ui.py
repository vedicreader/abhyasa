from pathlib import Path
from fasthtml.common import *
from abhyasa.core import Cites, Md, DepthBar, when, run, asset_css, meta, n_of, Empty
from abhyasa.model import DEPTHS, recall
from .cfg import Routes

_P = Path(__file__).parent
def css(): return asset_css(_P/'concepts.css')

def ConceptList(cs):
    return Ul(*[Li(A(c.name, href=Routes.of(c.slug)), DepthBar(c.floor), Span('  ' + meta(c.subject, when(c.due) if c.seen else 'new'), cls='mute'))
                for c in cs], cls='plain concepts'), css()

def Refs(slugs, by):
    have = [s for s in slugs if s in by]
    return Ul(*[Li(A(by[s].name, href=Routes.of(s)), DepthBar(by[s].floor)) for s in have], cls='plain') if have else Empty('Nothing yet.')

def _src(p):
    t = p.get('title') or p.get('lesson') or p.get('term') or p.get('key') or p.get('src')
    return A(t, href=p['url']) if p.get('url') else t

def ConceptPage(c, by, attempts):
    "The concept, its actions, then the reference sections in one quiet group (`.refs`)."
    head = P(meta(c.subject, f'floor {DEPTHS[c.floor]}'), DepthBar(c.floor), ' · ', meta(f"recall {recall(c):.0%}", when(c.due)) if c.seen else 'new', cls='mute')
    refs = (*run('concept_more', c),
            *([H2('Misconceptions seen'), Ul(*[Li(Md(m)) for m in c.misconceptions])] if c.misconceptions else []),
            Div(Div(H2('Needs first'), Refs(c.prereqs, by)), Div(H2('Related'), Refs(c.related, by)), cls='pair')
            if any(s in by for s in (*c.prereqs, *c.related)) else Empty('No other idea links to this one yet.'),
            H2('Your attempts'),
            Ul(*[Li(Md(a.question), Div(Span('Right' if a.correct else 'Not right', cls='ok k' if a.correct else 'no k'), Md(a.answer or 'no answer'), cls='mute'))
                 for a in attempts], cls='plain attempts')
            if attempts else Empty('You did not answer a question on this idea yet.'),
            *([H2('Seen in your work'), Cites(c.seen_in, label='')] if c.get('seen_in') else []),
            *([H2('Source'), Ul(*[Li(_src(p)) for p in c.provenance], cls='plain')] if c.provenance else []))
    return (css(), H1(c.name), head, Md(c.statement or '', cls='statement'), Div(*run('concept_actions', c), cls='row'), Div(*refs, cls='refs'))

def Subjects(subs):
    return (H2('Subjects'), Ul(*[Li(A(r['subject'] or 'general', href=f"{Routes.base}?subject={r['subject'] or ''}"),
                                     Span(f"  {n_of(r['n'], 'concept')}", cls='mute')) for r in subs], cls='plain'))
