"Every concept in a tree of groups, one concept's page, the sort of the concepts into groups, and the subjects on Your learning."
import logging, re, uuid
from fasthtml.common import *
from fastcore.basics import AttrDict
from abhyasa.core import Page, RouteOverrides, hook
from abhyasa.settings import val
from abhyasa.store import clean_group, GROUP_DEPTH, GROUP_LEN
from abhyasa.sources import propose_groups, apply_groups
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
    st = AttrDict(id='', job=None, subject='')   # the one sort: its id, the pool job, and the subject it sorts ('' for all)

    def cs_of(subject=''): return lr.concepts(subject or None)

    def proposed(places, subject):
        "The concepts of the sort with their proposed groups, and the counts of the moves and of the concepts moved by hand."
        cs = cs_of(subject)
        moved = sum(1 for c in cs if c.slug in places and clean_group(c.get('group'), c.subject) != places[c.slug])
        return [AttrDict({**c, 'group': places.get(c.slug, c.get('group'))}) for c in cs], moved, sum(c.get('group_by') == 'hand' for c in cs)

    def view(subject='', q=''):
        "The content of `#concepts-view` for the state of the sort. It only reads."
        if st.job is not None and not st.job.done(): return ui.SortPending(st.id, cs_of(subject))
        said = ''
        if st.job is not None:
            if st.job.exception() is None: return ui.Proposal(st.id, *proposed(st.job.result(), st.subject))
            said = 'The tutor could not sort your concepts. Try again.'   # the log has the words of the library (`run_sort`)
        return ui.Listing(cs_of(subject), q, subject, said)

    def index(subject:str='', q:str=''):
        return Page('Concepts', ui.css(), ui.js(), ui.H1(subject or 'Concepts'), Div(view(subject, q), id='concepts-view'), on='Concepts',
                    crumbs=[('Today', '/'), *([('Concepts', Routes.base)] if subject else [])])

    def run_sort(subject):
        "On the pool: the proposed group of each concept. Nothing is saved."
        try: return propose_groups(lr, ctx.ask, subject or None)
        except Exception as e: log.warning('the tutor could not sort the concepts: %r', e); raise

    def sort_start(subject:str=''):
        "Start the sort on the pool, unless one runs. The request does not wait for the model."
        if st.job is None or st.job.done():
            st.update(id=uuid.uuid4().hex[:8], subject=subject, job=ctx.pool.submit(run_sort, subject))
        return view(subject)

    def sort_state():
        "The state of the sort, for the pending card that asks again. It only reads."
        return (ui.Empty('No sort is running.'), *view()) if st.job is None else view(st.subject)

    def accept(sort:str=''):
        "Save the proposed tree in one step. A sort that is old or still running saves nothing."
        if st.job is None: return P('No sort is running. Sort again.', cls='req-err')
        if sort != st.id or not st.job.done() or st.job.exception(): return P('This sort is old. Sort again.', cls='req-err')
        apply_groups(lr, st.job.result())
        st.update(id='', job=None)
        return Response(headers={'HX-Redirect': Routes.base})

    def cancel(sort:str=''):
        "Drop the sort. Nothing is saved. A job that still runs ends on the pool, and its result is not used."
        if sort == st.id: st.update(id='', job=None)
        return view()

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

    RouteOverrides.nav.append(('Concepts', Routes.base, 2))
    app.get(Routes.base)(index)
    app.get(Routes.sort)(sort_state)
    app.post(Routes.sort)(sort_start)
    app.post(Routes.accept)(accept)
    app.post(Routes.cancel)(cancel)
    app.get(Routes.one)(one)
    app.post(Routes.group)(group)
