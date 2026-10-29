import json, unicodedata
from urllib.parse import urlencode
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import Cites, Md, DepthBar, when, run, asset_css, asset_js, meta, n_of, Empty, Said, Primary, Secondary, Quiet, Part
from abhyasa.model import DEPTHS, recall
from abhyasa.store import tree
from .cfg import Routes

_P = Path(__file__).parent
def css(): return asset_css(_P/'concepts.css')

def fold(s) -> str:
    "`s` in lower case with no marks, so `Maghā` finds `magha` (concepts.js folds the same way)."
    return ''.join(ch for ch in unicodedata.normalize('NFKD', str(s or '')) if not unicodedata.combining(ch)).lower()

def finds(c, q) -> bool:
    "Whether the find text `q` is in the name, an alias or the slug of `c`."
    return fold(q).strip() in fold(' '.join((c.name, c.slug, *(c.get('aliases') or ()))))

def label(name) -> str:
    "A subject or a group name as a label: a short name such as `ml` in upper case, a name in lower case with a capital first letter, else as it is."
    if not name: return 'General'
    if len(name) <= 3 and name.isalpha() and name.islower(): return name.upper()
    return name[:1].upper() + name[1:] if name.islower() else name

def Row(c):
    "One concept in the tree: its name, its level, and when it comes back."
    return Li(A(c.name, href=Routes.of(c.slug)), DepthBar(c.floor), Span('  ' + (when(c.due) if c.seen else 'new'), cls='mute'),
              data_find=' '.join(fold(x) for x in (c.name, *(c.get('aliases') or ()))))

def ConceptList(cs): return Ul(*map(Row, cs), cls='plain concepts'), css()

def Head(name, n): return Summary(Span(name, cls='name'), Span(f' · {n}', cls='n'))

def Branch(n, deep=False):
    "A group: its name and count, its groups, then its own concepts. Closed, except when the find box opened it (`deep`)."
    return Details(Head(label(n.name), n.n), *[Branch(k, deep) for k in n.kids], ConceptList(n.cs) if n.cs else '',
                   cls='tree grp', **({'open': True} if deep else {}))

def Subject(n, deep=False):
    "A subject, open: its groups, then the concepts with no group in `Not sorted yet`, open when the subject has no group yet."
    return Details(Head(label(n.name), n.n), *[Branch(k, deep) for k in n.kids],
                   Details(Head('Not sorted yet', len(n.cs)), ConceptList(n.cs), cls='tree loose', **({'open': True} if deep or not n.kids else {})) if n.cs else '',
                   cls='tree subj', open=True)

def Tree(cs, deep=False): return Div(*[Subject(n, deep) for n in tree(cs)], cls='concept-tree')

def Find(q='', subject=''):
    "The find box: it filters the tree as you type (concepts.js). Enter sends it, so it works with no script too."
    return Form(Input(type='search', name='q', value=q, id='find', placeholder='Find a concept', aria_label='Find a concept', autocomplete='off'),
                *([Input(type='hidden', name='subject', value=subject)] if subject else []), action=Routes.base, method='get', cls='find')

def Counts(cs):
    "The meta line over the tree: how many concepts, in how many subjects, and how many are not sorted yet."
    loose = sum(1 for c in cs if not c.get('group'))
    return P(meta(n_of(len(cs), 'concept'), n_of(len({(c.subject or '').lower() for c in cs}), 'subject'), loose and f'{loose} not sorted yet'), cls='mute')

def SortButton(subject=''):
    return Form(Secondary('Sort my concepts'), Span('The tutor puts your concepts in groups. You see the tree before it is saved.', cls='mute'),
                hx_post=Routes.sort, hx_target='#concepts-view', hx_swap='innerHTML', cls='row sort-form',
                **({'hx_vals': json.dumps(dict(subject=subject))} if subject else {}))

def Listing(cs, q='', subject='', said=''):
    "The normal view: the line of a failed sort, the find box and the sort action, then the tree."
    if not cs and not q: return Empty('No concepts yet.', A('Add a source', href='/add'))
    hits = [c for c in cs if finds(c, q)] if q.strip() else cs
    body = Tree(hits, deep=bool(q.strip())) if hits else Empty(f'No concept matches “{q}”.', A('Search everything', href=f"/search?{urlencode(dict(q=q))}"))
    return (P(said, cls='req-err') if said else '', Counts(cs), Div(Find(q, subject), SortButton(subject), cls='tools'), body)

def _sort_id(sid, subject): return Input(type='hidden', name='sort', value=sid), Input(type='hidden', name='subject', value=subject)

def SortPending(sid, cs, subject=''):
    "The sort runs in the background: the card asks the server again in 2 seconds. The tree below stays, so you can read it."
    return (Div(P('The tutor is sorting your concepts…'), P('This can take a minute. You can read your concepts while you wait.', cls='mute'),
                Form(*_sort_id(sid, subject), Quiet('Cancel'), hx_post=Routes.cancel, hx_target='#concepts-view', hx_swap='innerHTML'),
                cls='pending', hx_get=Routes.sort + (f"?{urlencode(dict(subject=subject))}" if subject else ''), hx_trigger='load delay:2s', hx_target='#concepts-view', hx_swap='innerHTML'),
            Tree(cs))

def Proposal(sid, subject, cs, moved, hand, placed=0, left=()):
    "The tree that the tutor proposes, and one choice: accept it (the one main button) or cancel. Nothing is saved before the accept."
    said = f"The tutor moves {n_of(moved, 'concept')}." if moved else 'The tutor has no change to make.'
    if hand: said += f" {n_of(hand, 'concept')} that you moved by hand {'stays where it is' if hand == 1 else 'stay where they are'}."
    tally = f"{placed} placed. {len(left)} left for you" + (f": {', '.join(left)}." if left else '.')
    return Part('The proposed tree', P(said, cls='mute'), P(tally, cls='mute tally'),
                Div(Form(*_sort_id(sid, subject), Primary('Accept this tree'), hx_post=Routes.accept),
                    Form(*_sort_id(sid, subject), Quiet('Cancel'), hx_post=Routes.cancel, hx_target='#concepts-view', hx_swap='innerHTML'),
                    cls='row'),
                Tree(cs), cls='proposal')

def GroupField(c, groups=(), said='', bad=False):
    "A small form on a concept page to move it to a group by hand: one or two names with `/` between them."
    who = ({'hand': 'You set this group.', 'model': 'The tutor set this group.'}.get(c.get('group_by'), '') if c.get('group') else
           'You keep this concept out of the groups.' if c.get('group_by') == 'hand' else '')
    return Form(Label(Span('Group', cls='lbl'),
                      Input(type='text', name='group', value=' / '.join(c.get('group') or []), placeholder='For example: nakshatras / padas',
                            list='group-names', maxlength='90', autocomplete='off', aria_label='Group')),
                Datalist(*[Option(value=' / '.join(g)) for g in groups], id='group-names'),
                Quiet('Move', small=True),
                Span(said, cls='req-err' if bad else 'mute') if said else Span(who, cls='mute') if who else '',
                id='group-field', cls='group-field', hx_post=Routes.group_of(c.slug), hx_swap='outerHTML',
                title=f"{c.subject or 'general'} › {' › '.join(c.get('group') or ['not sorted yet'])}")

def js(): return asset_js(_P/'concepts.js')

def Refs(slugs, by):
    have = [s for s in slugs if s in by]
    return Ul(*[Li(A(by[s].name, href=Routes.of(s)), DepthBar(by[s].floor)) for s in have], cls='plain') if have else Empty('Nothing yet.')

def _src(p):
    t = p.get('title') or p.get('lesson') or p.get('term') or p.get('key') or p.get('src')
    return A(t, href=p['url']) if p.get('url') else t

def ConceptPage(c, by, attempts, groups=()):
    "The concept, its actions, then the reference sections in one quiet group (`.refs`)."
    level = f'level: {DEPTHS[c.floor]}' if c.floor else 'not learned yet'   # the words of the needs line in a walk
    head = P(meta(c.subject, level), DepthBar(c.floor), *((' · ', meta(f"memory {recall(c):.0%}", when(c.due))) if c.seen else ()), cls='mute')
    refs = (*run('concept_more', c),
            *([H2('Misconceptions seen'), Ul(*[Li(Md(m)) for m in c.misconceptions])] if c.misconceptions else []),
            Div(Div(H2('Needs first'), Refs(c.prereqs, by)), Div(H2('Related'), Refs(c.related, by)), cls='pair')
            if any(s in by for s in (*c.prereqs, *c.related)) else Empty('No other idea links to this one yet.'),
            H2('Your attempts'),
            Ul(*[Li(Md(a.question), Div(Span('Right' if a.correct else 'Not right', cls='ok k' if a.correct else 'no k'), Md(a.answer or 'no answer'), cls='mute'), *Said(a))
                 for a in attempts], cls='plain attempts')
            if attempts else Empty('You did not answer a question on this idea yet.'),
            *([H2('Seen in your work'), Cites(c.seen_in, label='')] if c.get('seen_in') else []),
            *([H2('Source'), Ul(*[Li(_src(p)) for p in c.provenance], cls='plain')] if c.provenance else []))
    return (css(), H1(c.name), head, Md(c.statement or '', cls='statement'), Div(*run('concept_actions', c), cls='row'), GroupField(c, groups), Div(*refs, cls='refs'))

def Subjects(subs):
    return (H2('Subjects'), Ul(*[Li(A(r['subject'] or 'general', href=f"{Routes.base}?subject={r['subject'] or ''}"),
                                     Span(f"  {n_of(r['n'], 'concept')}", cls='mute')) for r in subs], cls='plain'))
