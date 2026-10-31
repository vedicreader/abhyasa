"Every concept in a tree of groups, one concept's page, the sort of the concepts into groups."
import json, logging, re, threading, uuid
from urllib.parse import urlencode
from fasthtml.common import *
from fastcore.basics import AttrDict
from abhyasa.core import Page, RouteOverrides, hook, moved_to
from abhyasa.settings import val
from abhyasa.store import clean_group, clean_name, under, GROUP_DEPTH, GROUP_LEN
from abhyasa.sources import propose_groups, apply_groups, place_new
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'sources', 'ask', 'pool')
log = logging.getLogger(__name__)

def check_group(text:str):
    "`(path, '')` for the text of the Group field, or `(None, why)` when it is refused: more than two levels, a long name, or no letter."
    parts = [p.strip() for p in re.split(r'[/>›]', text or '') if p.strip()]
    if len(parts) > GROUP_DEPTH: return None, 'A group has two levels at most. For example: nakshatras / padas.'
    if any(len(p) > GROUP_LEN for p in parts): return None, f'Each name has {GROUP_LEN} characters at most.'
    g = clean_group(parts)
    if parts and not g: return None, 'Use letters or digits in a group name.'
    return g, ''

def connect(app, ctx):
    lr = ctx.learning
    placing = threading.Lock()   # one placement of new concepts at a time
    st = AttrDict(id='', job=None, subject='', every=False, free=(), drop=(), kept=0)   # the one sort: its id, the pool job, the subject it sorts ('' for all); for "Sort everything again" also the hand concepts it may move, the hand groups that you unticked, and the count kept

    def cs_of(subject=''): return lr.concepts(subject or None)

    def subjects_of(subject=''): return [subject] if subject else sorted({c.subject or '' for c in cs_of()})

    def proposed(places, subject):
        "The concepts of the sort with their proposed subjects and groups, the count of the moves, the count of the concepts moved by hand, the count placed, and the names left. \"Sort everything again\" shows every concept."
        cs, sj = cs_of(subject), getattr(places, 'subjects', {})
        if st.every: free = [c for c in cs if c.get('group_by') != 'hand' or c.slug in st.free]
        else: free = [c for c in cs if not c.get('group') and c.get('group_by') != 'hand']   # the new concepts: the only ones that a sort of new concepts looks at
        ok = {c.slug for c in free}
        def new(c): return clean_group(places[c.slug], sj.get(c.slug, c.subject)) if c.slug in ok and c.slug in places else (c.get('group') or [])
        def was(c): return {'was': ' › '.join(c.get('group') or []) or 'Not sorted yet'} if new(c) != (c.get('group') or []) else {}   # the mark of a moved concept
        rows = [AttrDict({**c, 'group': new(c), 'subject': sj.get(c.slug, c.subject), **was(c)}) for c in (cs if st.every else free)]
        moved = sum(new(c) != (c.get('group') or []) for c in free)
        return rows, moved, 0 if st.every else sum(c.get('group_by') == 'hand' for c in cs), sum(c.slug in places for c in free), [c.name for c in free if c.slug not in places]

    def mine(subject): return st.job is not None and st.subject == subject   # a sort shows only on the page of its own subject

    def busy(): return st.job is not None and not st.job.done()

    def hand(subject=''):
        "The groups that you made, as `(subject, path)`, for the subjects of the page."
        return [(s, g) for s in subjects_of(subject) for g in lr.hand_groups(s)]

    def view(subject='', q='', said='', opened=(), bar=''):
        "The content of `#concepts-view` for the state of the sort of `subject`. It only reads."
        if mine(subject) and busy(): return P(said, cls='req-err') if said else '', *ui.SortPending(st.id, cs_of(subject), subject)
        if mine(subject):
            if st.job.exception() is None: return ui.Proposal(st.id, subject, *proposed(st.job.result(), subject), kept=st.kept if st.every else None)
            said = 'The tutor could not sort your concepts. Try again.'   # the log has the words of the library (`run_sort`)
        return ui.Listing(cs_of(subject), q, subject, said, len(lr.unsorted(subject or None)), {s: lr.saved_groups(s) or [] for s in subjects_of(subject)},
                          hand(subject), opened, bar)

    def index(subject:str='', q:str=''):
        name = ui.label(subject) if subject else 'Concepts'   # the display name, not the slug
        return Page(name, ui.css(), ui.js(), ui.H1(name), Div(view(subject, q), id='concepts-view', data_at=subject), on='Library', sub='Concepts',
                    crumbs=[('Library', Routes.base)] if subject else [])   # a tab root has no crumb

    def run_sort(subject, every=False, free=()):
        "On the pool: the proposed group of each concept. Nothing is saved."
        try: return propose_groups(lr, ctx.ask, subject or None, every=every, free=free)
        except Exception as e: log.warning('the tutor could not sort the concepts: %r', e); raise

    def sort_start(subject:str='', every:int=0, keep:list[str]=None):
        "Start the sort of `subject` on the pool, unless one runs. The request does not wait for the model. A sort of another subject, or of another kind, must end first. With `every`, the tutor sorts every concept again; `keep` is the hand groups that stay ticked."
        if busy() and (not mine(subject) or st.every != bool(every)):
            return view(subject, said=f"The tutor is sorting the concepts of {st.subject} now. Try again when it is done." if st.subject else
                        'The tutor is sorting all your concepts now. Try again when it is done.')
        if not busy():
            mark, keep = hand(subject), set(keep or [])
            drop = [(s, g) for s, g in mark if json.dumps([s, ui.path_text(g)]) not in keep] if every else []
            free = [c.slug for c in cs_of(subject) if c.get('group_by') == 'hand' and any(s == (c.subject or '') and under(c.get('group') or [], g) for s, g in drop)]
            st.update(id=uuid.uuid4().hex[:8], subject=subject, every=bool(every), free=free, drop=drop, kept=len(mark) - len(drop),
                      job=ctx.pool.submit(run_sort, subject, bool(every), free))
        return view(subject)

    def sort_state(subject:str=''):
        "The state of the sort of `subject`, for the pending card that asks again. It only reads."
        return view(subject) if mine(subject) else (ui.Empty('No sort is running.'), *view(subject))

    def accept(sort:str='', subject:str=''):
        "Save the proposed tree in one step. A sort that is old, of another subject, or still running saves nothing."
        if st.job is None: return P('No sort is running. Sort again.', cls='req-err')
        if sort != st.id or not mine(subject) or busy() or st.job.exception(): return P('This sort is old. Sort again.', cls='req-err')
        try: apply_groups(lr, st.job.result(), every=st.every, free=st.free, unmark=st.drop)   # one step, with the hand marks of the groups that you unticked
        except Exception as e:
            log.warning('abhyasa could not save the sorted tree: %r', e)
            return P('abhyasa could not save the tree. Nothing changed. Try again.', cls='req-err')
        st.update(id='', job=None, subject='', every=False, free=(), drop=(), kept=0); undos.clear()   # an old Undo would undo part of the sort
        return Response(headers={'HX-Redirect': Routes.base + (f"?{urlencode(dict(subject=subject))}" if subject else '')})

    def cancel(sort:str='', subject:str=''):
        "Drop the sort. Nothing is saved. A job that still runs ends on the pool, and its result is not used."
        if sort == st.id and mine(subject): st.update(id='', job=None, subject='')
        return view(subject)

    def undo(slug:str):
        "Undo a placement by the tutor: the concept goes back to `Not sorted yet`, and the tutor leaves it there. A group that you set stays."
        if lr.concept(slug) is None: return Response('No such concept.', status_code=404)
        lr.unplace(slug)
        return Response(headers={'HX-Refresh': 'true'})

    def place_job():
        "On the pool: place the new concepts in the groups of their subjects. A failure only goes in the log."
        with placing:
            try: place_new(lr, ctx.ask)
            except Exception as e: log.warning('the tutor could not place the new concepts: %r', e)

    @hook('concepts_added')
    def concepts_added():
        "New concepts came in (a walk, an add or an import): place them on the pool. The request does not wait."
        try: ctx.pool.submit(place_job)
        except Exception as e: log.warning('the tutor could not start to place the new concepts: %r', e)

    def one(slug:str):
        c = lr.concept(slug)
        if not c: return Page('Concept', ui.P('No such concept.'), on='Library')
        if lr.stale_links(c):
            try: lr.connect(slug, ctx.sources); c = lr.concept(slug)
            except Exception: pass
        return Page(c.name, *ui.ConceptPage(c, {x.slug: x for x in lr.concepts()}, lr.attempts(slug, limit=val('lists.attempts')), lr.groups(c.subject)),
                    on='Library', crumbs=[('Home', '/'), ('Library', Routes.base)])

    # Undo: the smallest Undo for the changes by hand, in one place, until the shared editor core (Task 7) takes it over.
    # Each change keeps a snapshot of what it can touch; Undo (or ⌘Z) writes back the last one. It is in memory only.
    undos = []

    def by_hand(said, slugs=(), subjects=(), f=None):
        "Do the change `f` by hand and keep its Undo. Return the id of the Undo step and the result of `f`."
        snap = lr.snapshot(slugs, subjects)
        out = f()
        undos.append(AttrDict(id=uuid.uuid4().hex[:8], said=said, snap=snap)); del undos[:-20]
        return undos[-1].id, out

    def undo_hand(step:str='', at:str=None):
        "Undo the last change by hand, when `step` is that change. On the tree, show the tree again; on a concept page, load it again."
        if not undos or undos[-1].id != step: said = 'Nothing to undo. The last change was undone or is old.'
        else: u = undos.pop(); lr.restore(u.snap); said = ''
        if at is None: return Response(headers={'HX-Refresh': 'true'})
        return view(at, said=said, bar=ui.UndoBar(undos[-1].id, undos[-1].said, at) if undos else '')

    def opened(subject, path=()): return {ui.branch_key(subject, path[:i]) for i in range(1, len(path) + 1)}

    def tree_after(at, subject, path, step, said):
        "The tree after a change by hand: the group that changed is open, and the Undo bar says what changed."
        return view(at, opened=opened(subject, path), bar=ui.UndoBar(step, said, at))

    def group(slug:str, group:str='', back:str='', at:str=''):
        "Move one concept by hand. The text is checked and cleaned first. From the tree (`back`), show the tree again."
        c = lr.concept(slug)
        if not c: return Response('No such concept.', status_code=404)
        g, why = check_group(group[:400])
        if why: return view(at, said=why) if back else ui.GroupField(c, lr.groups(c.subject), why, bad=True)
        said = f"Moved “{c.name}” to {' › '.join(g)}." if g else f"“{c.name}” is not in a group now."
        step, c = by_hand(said, [slug], [], lambda: lr.set_group(slug, g, by='hand'))
        if back: return tree_after(at, c.subject, c.group, step, said)
        return ui.GroupField(c, lr.groups(c.subject), 'Moved.' if g else 'Not in a group now.'), ui.UndoBar(step, said, oob=True)

    def move_form(slug:str, at:str=''):
        c = lr.concept(slug)
        if not c: return Response('No such concept.', status_code=404)
        return ui.MoveForm(c, lr.groups(c.subject), at)

    def rename(slug:str, name:str=''):
        "Give one concept a new name by hand. A source that adds it again keeps your name."
        c = lr.concept(slug)
        if not c: return Response('No such concept.', status_code=404)
        try: step, n = by_hand(f"Renamed “{c.name}” to “{clean_name(name[:400], 120)}”.", [slug], [], lambda: lr.rename(slug, name[:400]))
        except ValueError as e: return ui.NameField(c, str(e), bad=True)
        return ui.NameField(n, 'Renamed.'), ui.H1(n.name, id='concept-name', hx_swap_oob='true'), ui.UndoBar(step, undos[-1].said, oob=True)

    def subject_slugs(subject): return [c.slug for c in cs_of(subject) if (c.subject or '') == (subject or '')]

    def bad_subject(subject):
        "Why a subject from a form is refused: too long, with control characters, or not a subject that you have. '' when it is good."
        if len(subject) > GROUP_LEN or clean_name(subject, GROUP_LEN) != subject or subject not in subjects_of(): return 'No such subject.'
        return ''

    def rename_group_form(subject:str='', path:str='', at:str=''):
        if why := bad_subject(subject): return P(why, cls='req-err')
        return ui.RenameGroupForm(subject, check_group(path)[0] or [], at)

    def rename_group(subject:str='', path:str='', name:str='', at:str=''):
        "Give a group a new name by hand. Its concepts go with it, and the tutor never moves them."
        if why := bad_subject(subject): return view(at, said=why)
        p, why = check_group(path[:400])
        if why or not p: return view(at, said=why or 'Pick a group to rename.')
        new = clean_group([*p[:-1], name[:400]], subject)
        if len(new) != len(p): return view(at, said='Use letters or digits in a group name.')
        try: step, _ = by_hand(f"Renamed the group “{p[-1]}” to “{new[-1]}”.", subject_slugs(subject), [subject], lambda: lr.rename_group(subject, p, name[:400]))
        except ValueError as e: return view(at, said=str(e))
        return tree_after(at, subject, new, step, undos[-1].said)   # the keys fold, so a group that it joined opens too

    def new_group_form(subject:str='', at:str=''):
        if why := bad_subject(subject): return P(why, cls='req-err')
        return ui.NewGroupForm(subject, at)

    def new_group(subject:str='', path:str='', at:str=''):
        "Make an empty group by hand. You can then move concepts into it."
        if why := bad_subject(subject): return view(at, said=why)
        g, why = check_group(path[:400])
        if why or not g: return view(at, said=why or 'Give the group a name.')
        step, _ = by_hand(f"Made the group “{' › '.join(g)}”.", [], [subject], lambda: lr.new_group(subject, g))
        return tree_after(at, subject, g, step, undos[-1].said)

    RouteOverrides.nav.append(('Library', Routes.base, 2))
    RouteOverrides.subtabs.setdefault('Library', []).append(('Concepts', Routes.base, 0))
    app.get(Routes.base)(index)
    app.get(Routes.old)(moved_to(Routes.base))   # an old link, and the fallback of "show me" in the guide: `/concepts?q=…` finds in the Library
    app.get(Routes.sort)(sort_state)
    app.post(Routes.sort)(sort_start)
    app.post(Routes.accept)(accept)
    app.post(Routes.cancel)(cancel)
    app.get(Routes.one)(one)
    app.post(Routes.group)(group)
    app.get(Routes.move)(move_form)
    app.post(Routes.rename)(rename)
    app.get(Routes.rename_group)(rename_group_form)
    app.post(Routes.rename_group)(rename_group)
    app.get(Routes.new_group)(new_group_form)
    app.post(Routes.new_group)(new_group)
    app.post(Routes.back)(undo_hand)
    app.post(Routes.undo)(undo)
