"Every concept in a tree of groups, one concept's page, the sort of the concepts into groups, and the subjects on Your learning."
import logging, re, threading, uuid
from urllib.parse import urlencode
from fasthtml.common import *
from fastcore.basics import AttrDict
from abhyasa.core import Page, RouteOverrides, hook
from abhyasa.settings import val
from abhyasa.store import clean_group, GROUP_DEPTH, GROUP_LEN
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
    st = AttrDict(id='', job=None, subject='')   # the one sort: its id, the pool job, and the subject it sorts ('' for all)

    def cs_of(subject=''): return lr.concepts(subject or None)

    def proposed(places, subject):
        "The concepts of the sort with their proposed subjects and groups, the count of the moves, the count of the concepts moved by hand, the count placed, and the names left."
        cs, sj = cs_of(subject), getattr(places, 'subjects', {})
        free = [c for c in cs if not c.get('group') and c.get('group_by') != 'hand']   # the new concepts: the only ones that the sort looks at
        rows = [AttrDict({**c, 'group': places.get(c.slug, c.get('group')), 'subject': sj.get(c.slug, c.subject)}) for c in free]
        return rows, sum(c.slug in places for c in free), sum(c.get('group_by') == 'hand' for c in cs), sum(c.slug in places for c in free), [c.name for c in free if c.slug not in places]

    def mine(subject): return st.job is not None and st.subject == subject   # a sort shows only on the page of its own subject

    def busy(): return st.job is not None and not st.job.done()

    def view(subject='', q='', said=''):
        "The content of `#concepts-view` for the state of the sort of `subject`. It only reads."
        if mine(subject) and busy(): return ui.SortPending(st.id, cs_of(subject), subject)
        if mine(subject):
            if st.job.exception() is None: return ui.Proposal(st.id, subject, *proposed(st.job.result(), subject))
            said = 'The tutor could not sort your concepts. Try again.'   # the log has the words of the library (`run_sort`)
        return ui.Listing(cs_of(subject), q, subject, said, len(lr.unsorted(subject or None)))

    def index(subject:str='', q:str=''):
        return Page('Concepts', ui.css(), ui.js(), ui.H1(subject or 'Concepts'), Div(view(subject, q), id='concepts-view'), on='Library', sub='Concepts',
                    crumbs=[('Today', '/'), *([('Concepts', Routes.base)] if subject else [])])

    def run_sort(subject):
        "On the pool: the proposed group of each concept. Nothing is saved."
        try: return propose_groups(lr, ctx.ask, subject or None)
        except Exception as e: log.warning('the tutor could not sort the concepts: %r', e); raise

    def sort_start(subject:str=''):
        "Start the sort of `subject` on the pool, unless one runs. The request does not wait for the model. A sort of another subject must end first."
        if busy() and not mine(subject):
            return view(subject, said=f"The tutor is sorting the concepts of {st.subject} now. Try again when it is done." if st.subject else
                        'The tutor is sorting all your concepts now. Try again when it is done.')
        if not busy(): st.update(id=uuid.uuid4().hex[:8], subject=subject, job=ctx.pool.submit(run_sort, subject))
        return view(subject)

    def sort_state(subject:str=''):
        "The state of the sort of `subject`, for the pending card that asks again. It only reads."
        return view(subject) if mine(subject) else (ui.Empty('No sort is running.'), *view(subject))

    def accept(sort:str='', subject:str=''):
        "Save the proposed tree in one step. A sort that is old, of another subject, or still running saves nothing."
        if st.job is None: return P('No sort is running. Sort again.', cls='req-err')
        if sort != st.id or not mine(subject) or busy() or st.job.exception(): return P('This sort is old. Sort again.', cls='req-err')
        apply_groups(lr, st.job.result())
        st.update(id='', job=None, subject='')
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
        if not c: return Page('Concept', ui.P('No such concept.'))
        if lr.stale_links(c):
            try: lr.connect(slug, ctx.sources); c = lr.concept(slug)
            except Exception: pass
        return Page(c.name, *ui.ConceptPage(c, {x.slug: x for x in lr.concepts()}, lr.attempts(slug, limit=val('lists.attempts')), lr.groups(c.subject)),
                    crumbs=[('Today', '/'), ('Concepts', Routes.base)])

    def group(slug:str, group:str=''):
        "Move one concept by hand. The text is checked and cleaned first."
        c = lr.concept(slug)
        if not c: return Response('No such concept.', status_code=404)
        g, why = check_group(group[:400])
        if why: return ui.GroupField(c, lr.groups(c.subject), why, bad=True)
        c = lr.set_group(slug, g, by='hand')
        return ui.GroupField(c, lr.groups(c.subject), 'Moved.' if g else 'Not in a group now.')

    @hook('learning_end')
    def subjects(): return ui.Subjects(lr.subjects())

    def library(): return Redirect(Routes.base)

    RouteOverrides.nav.append(('Library', Routes.base, 2))
    RouteOverrides.subtabs.setdefault('Library', []).append(('Concepts', Routes.base, 0))
    app.get(Routes.base)(index)
    app.get(Routes.library)(library)
    app.get(Routes.sort)(sort_state)
    app.post(Routes.sort)(sort_start)
    app.post(Routes.accept)(accept)
    app.post(Routes.cancel)(cancel)
    app.get(Routes.one)(one)
    app.post(Routes.group)(group)
    app.post(Routes.undo)(undo)
