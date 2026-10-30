import json
from urllib.parse import urlencode
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import Cites, Md, DepthBar, when, run, asset_css, asset_js, meta, n_of, Empty, Said, Primary, Secondary, Quiet, Part
from abhyasa.model import DEPTHS, recall
from abhyasa.store import tree, fold
from .cfg import Routes

_P = Path(__file__).parent
def css(): return asset_css(_P/'concepts.css')

def finds(c, q) -> bool:
    "Whether the find text `q` is in the name, an alias or the slug of `c`."
    return fold(q).strip() in fold(' '.join((c.name, c.slug, *(c.get('aliases') or ()))))

def label(name) -> str:
    "A subject or a group name as a label: a short name such as `ml` in upper case, a name in lower case with a capital first letter, else as it is."
    if not name: return 'General'
    if len(name) <= 3 and name.isalpha() and name.islower(): return name.upper()
    return name[:1].upper() + name[1:] if name.islower() else name

def path_text(path) -> str: return ' / '.join(path)

def _in(subject, path=(), at=''):
    "The hidden fields of a form in the tree: the subject and the path it acts on, and the page (`at`) to show after it."
    return (Input(type='hidden', name='subject', value=subject or ''), *([Input(type='hidden', name='path', value=path_text(path))] if path else ()),
            Input(type='hidden', name='at', value=at or ''), Input(type='hidden', name='back', value='tree'))

def _opens(url, at, **q):
    "A quiet button that gets a small form from `url` into the `.slot` after it."
    return dict(hx_get=f"{url}?{urlencode({**q, 'at': at or ''})}", hx_target='next .slot', hx_swap='innerHTML', type='button')

def Slot(): return Div(cls='slot')

def _act(label, cls, **kw):
    "A small quiet button with the class `cls` too."
    b = Quiet(label, small=True, **kw); b.attrs['class'] += f' {cls}'
    return b

def Row(c, at=None):
    "One concept in the tree: its name, its level, and when it comes back. On the page you can change (`at`), a handle to drag it and \"Move to…\"."
    edit = at is not None
    return Li(*((Span('⠿', cls='handle', aria_hidden='true', title='Drag to a group'),) if edit else ()),
              A(c.name, href=Routes.of(c.slug)), DepthBar(c.floor), Span('  ' + (when(c.due) if c.seen else 'new'), cls='mute'),
              *((Span('Placed by the tutor', cls='mute placed'), Form(Quiet('Undo', small=True), hx_post=Routes.undo_of(c.slug), hx_swap='none', cls='undo'))
                if c.get('group_by') == 'placed' and c.get('group') else ()),
              *((Span(f"from {c.was} → {' › '.join(c.get('group') or []) or 'Not sorted yet'}", cls='mute moved'),) if c.get('was') else ()),
              *((_act('Move to…', 'move-to', aria_label=f'Move “{c.name}” to a group', **_opens(Routes.move_of(c.slug), at)), Slot()) if edit else ()),
              data_find=' '.join(fold(x) for x in (c.name, *(c.get('aliases') or ()))),
              **({'data_slug': c.slug, 'data_subject': c.subject or '', 'data_post': Routes.group_of(c.slug)} if edit else {}))

def ConceptList(cs, at=None): return Ul(*[Row(c, at) for c in cs], cls='plain concepts'), css()

def Head(name, n, *acts, **kw): return Summary(Span(name, cls='name'), Span(f' · {n}', cls='n'), *acts, **kw)

def branch_key(subject, path=()): return (fold(subject), *map(fold, path))

LOOSE = '\0'   # the key of `Not sorted yet` in `opened`: `branch_key(subject, [LOOSE])`

def Branch(n, deep=False, subject='', at=None, opened=()):
    "A group: its name and count, its groups, then its own concepts. Closed, except when the find box opened it (`deep`) or a change by hand went in it (`opened`)."
    edit = at is not None
    acts = (_act('Rename', 'act', aria_label=f'Rename the group “{label(n.name)}”', **_opens(Routes.rename_group, at, subject=subject or '', path=path_text(n.path))),) if edit else ()
    return Details(Head(label(n.name), n.n, *acts, **({'data_drop': path_text(n.path), 'data_subject': subject or ''} if edit else {})),
                   *((Slot(),) if edit else ()), *[Branch(k, deep, subject, at, opened) for k in n.kids], ConceptList(n.cs, at) if n.cs else '',
                   cls='tree grp', **({'open': True} if deep or branch_key(subject, n.path) in opened else {}))

def Subject(n, deep=False, at=None, opened=()):
    "A subject, open: its groups, then the concepts with no group in `Not sorted yet`, open when the subject has no group yet."
    edit = at is not None
    acts = (_act('New group', 'act', aria_label=f'Make a new group in {label(n.name)}', **_opens(Routes.new_group, at, subject=n.name or '')),) if edit else ()
    return Details(Head(label(n.name), n.n, *acts), *((Slot(),) if edit else ()), *[Branch(k, deep, n.name, at, opened) for k in n.kids],
                   Details(Head('Not sorted yet', len(n.cs), **({'data_drop': '', 'data_subject': n.name or ''} if edit else {})), ConceptList(n.cs, at),
                           cls='tree loose', **({'open': True} if deep or not n.kids or branch_key(n.name, [LOOSE]) in opened else {})) if n.cs else '',
                   cls='tree subj', open=True)

def Tree(cs, deep=False, groups=None, at=None, opened=()):
    "The tree of `cs`. `groups` (`{subject: paths}`) adds the groups with no concept. On the page you can change (`at`), each part has its actions."
    return Div(*[Subject(n, deep, at, opened) for n in tree(cs, groups)], cls='concept-tree')

def Find(q='', subject=''):
    "The find box: it filters the tree as you type (concepts.js). Enter sends it, so it works with no script too."
    return Form(Input(type='search', name='q', value=q, id='find', placeholder='Find a concept', aria_label='Find a concept', autocomplete='off'),
                *([Input(type='hidden', name='subject', value=subject)] if subject else []), action=Routes.base, method='get', cls='find')

def Counts(cs):
    "The meta line over the tree: how many concepts, in how many subjects, and how many are not sorted yet."
    loose = sum(1 for c in cs if not c.get('group'))
    return P(meta(n_of(len(cs), 'concept'), n_of(len({(c.subject or '').lower() for c in cs}), 'subject'), loose and f'{loose} not sorted yet'), cls='mute')

def SortButton(subject='', n=0):
    "The sort action, with the count of concepts that have no group. With none, it does not show."
    if not n: return ''
    return Form(Secondary(f"Sort {n_of(n, 'new concept')}"), Span('The tutor puts them in the groups that you have. You see the result before it is saved. Concepts that are sorted do not move.', cls='mute'),
                hx_post=Routes.sort, hx_target='#concepts-view', hx_swap='innerHTML', cls='row sort-form',
                **({'hx_vals': json.dumps(dict(subject=subject))} if subject else {}))

def Listing(cs, q='', subject='', said='', new=0, groups=None, hand=(), opened=(), bar=''):
    "The normal view: the Undo bar or the line of a failed sort, the find box and the sort action, the tree, then `More` with \"Sort everything again\"."
    if not cs and not q: return Empty('Concepts appear here when you start a walk.', A('Start a walk', href='/learn'))
    hits = [c for c in cs if finds(c, q)] if q.strip() else cs
    body = (Tree(hits, deep=bool(q.strip()), groups=None if q.strip() else groups, at=subject, opened=opened) if hits else
            Empty(f'No concept matches “{q}”.', A('Search everything', href=f"/search?{urlencode(dict(q=q))}")))
    return (bar, P(said, cls='req-err') if said else '', Counts(cs), Div(Find(q, subject), SortButton(subject, new), cls='tools'), body, SortAgain(subject, hand))

def SortAgain(subject='', hand=()):
    "The quiet `More` part at the foot: sort every concept again, with one ticked box for each group that you made (`hand`: `(subject, path)`)."
    def name(s, g): return ' › '.join([label(s)] * (not subject) + list(g))
    return Details(Summary('More'),
                   Form(P('The tutor sorts all your concepts again. You see the new tree before it is saved. Your own groups stay. Untick a group to let the tutor sort it too.', cls='mute'),
                        *[Label(Input(type='checkbox', name='keep', value=json.dumps([s or '', path_text(g)]), checked=True), ' ', name(s, g), cls='keep') for s, g in hand],
                        Input(type='hidden', name='every', value='1'), *([Input(type='hidden', name='subject', value=subject)] if subject else []),
                        Secondary('Sort everything again'),
                        hx_post=Routes.sort, hx_target='#concepts-view', hx_swap='innerHTML', cls='sort-again'),
                   cls='more sort-more')

def UndoBar(step, said, at=None, oob=False):
    "The Undo bar after a change by hand: what changed, in one sentence, and Undo (⌘Z). On the tree it shows the tree again; on a concept page (`oob`: it goes in `#undo-bar`) it loads the page again."
    tgt = dict(hx_target='#concepts-view', hx_swap='innerHTML') if at is not None else dict(hx_swap='none')
    return Div(Span(said), Form(Input(type='hidden', name='step', value=step), *([Input(type='hidden', name='at', value=at)] if at is not None else []),
                                Quiet('Undo', Kbd('⌘Z'), small=True), hx_post=Routes.back, **tgt),
               id='undo-bar', cls='undo-bar', role='status', aria_live='polite', **({'hx_swap_oob': 'true'} if oob else {}))

def _close(): return _act('Cancel', 'slot-close', type='button')

def MoveForm(c, groups, at=''):
    "\"Move to…\" for one row: a list of the groups of its subject, and \"Not in a group\". The keyboard way to drag."
    now = path_text(c.get('group') or [])
    return Form(Label(Span(f'Move “{c.name}” to', cls='lbl'),
                      Select(Option('Not in a group', value='', selected=not now), *[Option(' › '.join(g), value=path_text(g), selected=path_text(g) == now) for g in groups],
                             name='group', autofocus=True)),
                *_in(c.subject, (), at), Quiet('Move', small=True), _close(),
                hx_post=Routes.group_of(c.slug), hx_target='#concepts-view', hx_swap='innerHTML', cls='slot-form')

def RenameGroupForm(subject, path, at='', said=''):
    "A one-line form to give a group a new name."
    return Form(Label(Span('New name', cls='lbl'), Input(type='text', name='name', value=path[-1] if path else '', maxlength='40', autocomplete='off', autofocus=True, aria_label='New name of the group')),
                *_in(subject, path, at), Quiet('Rename', small=True), _close(), Span(said, cls='req-err') if said else '',
                hx_post=Routes.rename_group, hx_target='#concepts-view', hx_swap='innerHTML', cls='slot-form')

def NewGroupForm(subject, at='', said=''):
    "A one-line form to make an empty group under a subject. A second name after `/` makes a group in a group."
    return Form(Label(Span('New group', cls='lbl'), Input(type='text', name='path', placeholder='For example: nakshatras / padas', maxlength='90', autocomplete='off', autofocus=True, aria_label='Name of the new group')),
                Input(type='hidden', name='subject', value=subject or ''), Input(type='hidden', name='at', value=at or ''),
                Quiet('Make', small=True), _close(), Span(said, cls='req-err') if said else '',
                hx_post=Routes.new_group, hx_target='#concepts-view', hx_swap='innerHTML', cls='slot-form')

def NameField(c, said='', bad=False):
    "A small form on a concept page to give the concept a new name. A name that you set stays when a source adds the concept again."
    return Form(Label(Span('Name', cls='lbl'), Input(type='text', name='name', value=c.name, maxlength='120', autocomplete='off', aria_label='Name')),
                Quiet('Rename', small=True), Span(said, cls='req-err' if bad else 'mute') if said else '',
                id='name-field', cls='group-field', hx_post=Routes.rename_of(c.slug), hx_swap='outerHTML')

def _sort_id(sid, subject): return Input(type='hidden', name='sort', value=sid), Input(type='hidden', name='subject', value=subject)

def SortPending(sid, cs, subject=''):
    "The sort runs in the background: the card asks the server again in 2 seconds. The tree below stays, so you can read it."
    return (Div(P('The tutor is sorting your concepts…'), P('This can take a minute. You can read your concepts while you wait.', cls='mute'),
                Form(*_sort_id(sid, subject), Quiet('Cancel'), hx_post=Routes.cancel, hx_target='#concepts-view', hx_swap='innerHTML'),
                cls='pending', hx_get=Routes.sort + (f"?{urlencode(dict(subject=subject))}" if subject else ''), hx_trigger='load delay:2s', hx_target='#concepts-view', hx_swap='innerHTML'),
            Tree(cs))

def Proposal(sid, subject, cs, moved, hand, placed=0, left=(), kept=None):   # `cs`: the new concepts, or every concept for "Sort everything again"
    "The tree that the tutor proposes, and one choice: accept it (the one main button) or cancel. Nothing is saved before the accept. `kept`: the count of hand groups that stay, for \"Sort everything again\"."
    said = f"The tutor moves {n_of(moved, 'concept')}." if moved else 'The tutor has no change to make.'
    if kept: said += f" {n_of(kept, 'group')} that you made {'stays' if kept == 1 else 'stay'}."
    elif hand: said += f" {n_of(hand, 'concept')} that you moved by hand {'stays where it is' if hand == 1 else 'stay where they are'}."
    tally = f"{placed} placed. {len(left)} left for you" + (f": {', '.join(left)}. They stay in Not sorted yet." if left else '.')
    opened = {branch_key(c.subject, c.group[:i]) for c in cs if c.get('was') for i in range(1, len(c.group) + 1)} | \
             {branch_key(c.subject, [LOOSE]) for c in cs if not c.get('group')}   # each group that changes opens, and so does Not sorted yet
    return Part('The proposed tree', P(said, cls='mute'), P(tally, cls='mute tally'),
                Div(Form(*_sort_id(sid, subject), Primary('Accept this tree'), hx_post=Routes.accept),
                    Form(*_sort_id(sid, subject), Quiet('Cancel'), hx_post=Routes.cancel, hx_target='#concepts-view', hx_swap='innerHTML'),
                    cls='row'),
                Tree(cs, opened=opened), cls='proposal')

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
    t = p.get('title') or p.get('lesson') or p.get('term') or p.get('key') or ('A walk' if p.get('src') == 'journey' else p.get('src'))   # the stored name stays
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
    return (css(), H1(c.name, id='concept-name'), head, Md(c.statement or '', cls='statement'), Div(*run('concept_actions', c), cls='row'), GroupField(c, groups), NameField(c), Div(id='undo-bar'), Div(*refs, cls='refs'))

def Subjects(subs):
    return (H2('Subjects'), Ul(*[Li(A(label(r['subject']), href=f"{Routes.base}?subject={r['subject'] or ''}"),
                                     Span(f"  {n_of(r['n'], 'concept')}", cls='mute')) for r in subs], cls='plain'))
