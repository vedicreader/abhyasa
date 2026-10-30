"""The guided walk: a paper, a text, a topic or a link as one idea at a time, in reading order. The plan, the step page, its check,
Next idea, and the summary at the end of each section. A sitting is a `Session` that the walk feeds itself."""
import hashlib, json, logging, re, tempfile, time
from collections import defaultdict
from threading import Lock
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import n_of, Page, hook, run as run_hook, SourceLine, source_of, Md
from abhyasa.core.leela import leela_line, leela_link
from abhyasa.settings import val, set_val
from abhyasa.detect import detect, vault_title
from abhyasa.store import clean_subject
from abhyasa.profile import profile_text
from abhyasa.method import WALK_WAYS, CHECK_KIND, DEPTH
from abhyasa.tutor import Session, HINTS, public, moved
from abhyasa.sources import file_link, link_kind, LinkError, as_link, is_paper, file_folder, file_repo, folder_why, tree_files, unfile, vault_roots, root_docs
from abhyasa.journey import journey_from_source, journey_from_text, journey_from_sources, walk_from_topic, _topic_walk, TOOL_WAYS, walk_state, short_check, with_step, trail, parent_step, for_talk, _jlock
from abhyasa.walk import tutor_note, open_short, step_meta, code_task, nb_spec, validate_nb_spec, leela_back, leela_found
from abhyasa.contract import path_why
from abhyasa.nb import spec_notebook
from abhyasa.research import to_research, wants_source
from abhyasa.tutor import NoLesson
from abhyasa.demo import queue_demo, job_state, job_age, rung, backed, other_way, demo_lesson, simpler_demo, said
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'tutor', 'ask', 'pool', 'sessions', 'sources', 'research')
FIGURES = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
RUN = dict(read_at=None, done=None, qid=None, note=None)   # the run fields of a step (spec 6.3), empty until the step is used
AIM = dict(demo='', order='order')   # check kind -> the aim of its demo
MAX_STATE = 20_000                   # the most chars of a kept demo state
MAX_SOURCE = 100_000                 # the most chars of code that a run takes
MAX_RESULT = 2 << 20                 # the most bytes of one image of a run from Leela
PNG = b'\x89PNG\r\n\x1a\n'
NO_LINK = 'abhyasa could not make a walk from this link. Try again later, or try another link.'
AS_LINK = 'This is a link, so the tutor reads it from the web.'
NO_DOC = 'No document in your vault has this name. To add a web page or a paper, use A link.'
log = logging.getLogger(__name__)

def connect(app, ctx):
    lr, tutor, sessions = ctx.learning, ctx.tutor, ctx.sessions
    vault = lr.vault.path         # each Leela link names the vault of this app with its key
    ask = ctx.ask   # the engine picks the model of each task (`for_task`) on each call, so a settings change works at once
    up = [('Today', '/'), ('Learn', '/learn')]
    writing = defaultdict(Lock)   # (walk, step) -> a lock, so the note and the check of one step do not write the note twice
    links = {}                    # link -> the pool job that makes its walk, and `said`, the words of its state

    def by(): return {c.slug: c for c in lr.concepts()}
    def go(jid, i): return Redirect(ui.at(Routes.step, jid, i))
    def missing(): return Page('Walk', H1('No such walk'), P(A('Your walks', href='/learn')), on='Learn', crumbs=up)

    def walk_of(jid, i=None):
        "The walk `jid`, and step `i` when it is there; None for an unknown walk or step."
        j = lr.journey(jid)
        if not j or j.get('mode') != 'walk' or (i is not None and not 0 <= i < len(j.steps)): return None
        return j

    def sitting(j):
        "The open sitting of walk `j`: in memory, else from the shelf, else a new one."
        sid = j.get('sitting')
        s = sid and (sessions.get(sid) or Session.load(tutor, sid))
        if not s or s.ended:
            s = Session(tutor, journey=j.id)
            lr.merge_journey(j.id, sitting=s.id)   # only `sitting`, so a step that another request writes stays
        sessions[s.id] = s
        return s

    def question(j, i):
        "The question of the check of step `i`: open, or closed in this run; None when it is gone."
        qid = j.steps[i].get('qid')
        return qid and (tutor.open.get(qid) or tutor.shut.get(qid))

    def demo(s):
        "The demo of step `s` when its check is a demo or an order, else None."
        k = s['check']['kind']
        return lr.demo_for(s['slug'], AIM[k]) if k in AIM else None

    def card(j, i):
        "The check card of step `i`; a short-answer card adds what other blocks put after it (`check_after`)."
        s = j.steps[i]
        k = s['check']['kind']
        if k == 'notebook': return nb_card(j, i)
        if k in AIM: return ui.CHECKS[k](j.id, i, s, demo(s))
        q = question(j, i)
        return ui.CHECKS.get(k, ui.Short)(j.id, i, s, q, after=run_hook('check_after', j, i, q) if q else (), **(dict(vault=vault) if k == 'code' else {}))

    def back_to(j):
        "The way back from side walk `j` to the step that opened it, and the trail for the side pane; None for a walk with no parent."
        pj, i = parent_step(lr, j)
        if not pj: return None
        parts = [[f"Idea {t.step + 1}", ui.at(Routes.step, t.walk, t.step)] for t in trail(lr, j.id)[:-1] if t.step is not None]
        return AttrDict(href=ui.at(Routes.step, pj.id, i), here=f"idea {i + 1} of {len(pj.steps)}", trail=parts)

    def as_short(j, i):
        "Walk `j` with the check of step `i` as a short answer in a text way, when its code task could not be made (spec 6.5)."
        s = j.steps[i]
        if s['check']['kind'] == 'short': return j
        return AttrDict({**j, 'steps': [*j.steps[:i], {**s, 'check': dict(short_check(lr, lr.concept(s['slug'])))}, *j.steps[i + 1:]]})

    def ahead(j, i):
        "Start the demo of step `i` when its check is a demo or an order, it has no outcome, and it has no demo yet (spec 6.5)."
        if not 0 <= i < len(j.steps) or (s := j.steps[i]).get('done') or s['check']['kind'] not in AIM or demo(s): return
        queue_demo(tutor, s['slug'], aim=AIM[s['check']['kind']])

    def no_demo(j, i):
        "The pending card while the demo of step `i` is made; None when the wait is over, so the step uses a short answer."
        s = j.steps[i]
        slug, aim = s['slug'], AIM[s['check']['kind']]
        if job_state(tutor, slug, aim) == 'none': ahead(j, i)
        if job_state(tutor, slug, aim) == 'running' and job_age(tutor, slug, aim) < val('walks.demo_wait'): return ui.Pending(j.id, i, s)
        lr.walk_step(j.id, i, check=dict(short_check(lr, lr.concept(slug))))

    def open_code(j, i, sid):
        "Open the code task of step `i` and keep its stub and visible tests on the step, so a reload shows the same task; None when it fails."
        try: t = code_task(tutor, lr.concept(j.steps[i]['slug']), session=sid, meta=step_meta(j, i))
        except Exception: return None
        lr.walk_step(j.id, i, qid=t.q.id, code=dict(fname=t.fname, stub=t.stub, tests=t.tests))
        return t.q

    def reply(j, i, r=None):
        "The reply to a move on a check: the results part for a code check, else the whole card."
        q = question(j, i)
        return ui.CodeOut(j.id, i, q, r) if q and j.steps[i].get('code') else card(j, i)

    def no_check(j, i):
        "The reply to a move on a check that is not open: the closed card, or 409 when the check was never loaded."
        if not j: return Response(status_code=404)
        if j.steps[i].get('done'): return reply(j, i)
        return Response('No check is open on this idea. Load the page again.', status_code=409)

    def live(jid, i):
        "The sitting with the open question of step `i` as its question, or None when the check is not open."
        if not (j := walk_of(jid, i)) or (qid := j.steps[i].get('qid')) not in tutor.open: return j, None
        s = sitting(j)
        if not s.q or s.q.id != qid: s.q = public(tutor.open[qid])
        return j, s

    def closed(j, i, r):
        "Mark step `i` done with the outcome of its check."
        j = lr.walk_step(j.id, i, done=dict(outcome=r.outcome, aid=tutor.shut[j.steps[i]['qid']].get('aid'), at=time.time()))
        return reply(j, i, r), *ui.Filled(j, walk_state(j), by(), i)   # the dot of the idea fills in the outline

    looking, look_for = ctx.research.looking, ctx.research.look_for   # research runs on its own pool; the request does not wait
    nb_jobs, nb_lock = {}, Lock()   # (walk, step) -> the research pool job that writes the notebook spec of the step

    def nb_writing(jid, i):
        "Whether a job writes the notebook spec of step `i` of walk `jid` now."
        return (f := nb_jobs.get((jid, i))) is not None and not f.done()

    def write_notebook(jid, i):
        "Start the job that writes the notebook spec of step `i` on the research pool, unless it runs or the step has a spec."
        with nb_lock:
            j = walk_of(jid, i)
            if not j or nb_writing(jid, i) or j.steps[i].get('nb') or j.steps[i]['check']['kind'] != 'notebook': return
            nb_jobs[jid, i] = ctx.research.pool.submit(nb_spec, lr, ask, j, i)

    def nb_card(j, i):
        "The card of a notebook step: the notebook, the line while the tutor writes it, or the reason when it could not."
        s, link = j.steps[i], leela_link(j, i, vault=vault)
        if s.get('nb'): return ui.NotebookCard(j.id, i, s, link)
        if not s.get('nb_why'): write_notebook(j.id, i)
        if nb_writing(j.id, i) or not s.get('nb_why'): return ui.NbPending(j.id, i, link, s.get('leela_at'))
        return ui.NbFailed(j.id, i, s['nb_why'], link, s.get('leela_at'))

    def from_leela(j, i, back=None):
        """The card "From Leela" of step `i`, or None. A done step gets Next idea. A notebook step that is not done keeps Open in Leela.
        Another step that is not done keeps its own check, so it gets no card."""
        if not (b := (leela_back(lr, j) if back is None else back).get(i)): return None
        j = lr.journey(j.id)
        s = j.steps[i]
        if s.get('done'): return ui.FromLeela(j, i, b, (ui.GoOn(j.id, i), leela_line(j, i, say='Open the lesson in Leela', vault=vault)))
        if s['check']['kind'] != 'notebook': return None
        return ui.FromLeela(j, i, b, ui.NbGo(j.id, i, leela_link(j, i, vault=vault), spec=bool(s.get('nb')), opened=s.get('leela_at')))

    def write_notebooks(j):
        "Start the job that writes the notebook spec of each notebook step of walk `j`, on the research pool."
        for i, s in enumerate(j.steps):
            if s['check']['kind'] == 'notebook': write_notebook(j.id, i)

    @hook('walk_made')
    def research_new(j):
        "After a topic walk is made: look for a web source for each step with no passage, up to `research.per_walk` steps, and write the notebook of each notebook step."
        if (j := lr.journey(j['id'])) and j.get('mode') == 'walk':
            look_for(j.id, to_research(j))
            write_notebooks(j)

    def paper_said(docs):
        "The wait line of a paper: its page count when the vault knows it."
        try: n = (lr.vault if docs[0].shelf == 'store' else lr.vault.shelf(docs[0].shelf)).doc(docs[0].doc_id)['pages']
        except Exception: n = None
        return f"Reading the paper: {n_of(n, 'page')}…" if n else 'Reading the paper…'

    def from_link(url, pages, st, tool=False, subject=''):
        "On the pool: file the pages of `url`, then read each page and make one walk. Return the walk id. A paper is one document, read in full."
        docs = file_link(lr, url, pages)
        said = (lambda k, n: paper_said(docs)) if is_paper(url) else (lambda k, n: f"Reading {k + 1} of {n_of(n, 'page')}…")
        j = journey_from_sources(lr, ask, docs, progress=lambda k, n: st.update(said=said(k, n)), tool=tool, subject=subject)
        run_hook('concepts_added')   # the concepts block places the new concepts on the pool
        if not j.steps:
            lr.drop_journey(j.id)
            raise LinkError('The tutor found no ideas on these pages.')
        write_notebooks(j)
        return j.id

    def retitle(jid):
        "On the pool: give a walk named by an arXiv id the title of its paper. A failure of the network keeps the id."
        try: lr.retitle_paper(jid)
        except Exception as e: log.warning('abhyasa could not get the title of the paper: %r', e)

    def link_walk(url, pages, tool=False, subject=''):
        "Start the pool job that makes a walk from `url`, unless one is running. The request does not wait for the network or the model."
        try: link_kind(url)
        except ValueError as e: return P(str(e) if isinstance(e, LinkError) else NO_LINK, cls='req-err')
        st = links.get(url)
        if not st or st.job.done():
            paper = is_paper(url)   # one paper: the count of pages to read does not apply
            st = links[url] = AttrDict(said='Reading the paper…' if paper else 'Getting the pages from the link…')
            st.job = ctx.pool.submit(from_link, url, int(pages) if str(pages).strip().isdigit() and not paper else None, st, tool, subject)
        return ui.LinkPending(url, st.said)

    def file_chip(i, st):
        "On the pool: file the source of the chip id `i` (`gh:`, `folder:`, `repo:`, `link:`), or get its docs (`vault:`, `doc:`). Returns (name, docs)."
        kind, _, v = i.partition(':')
        if kind == 'gh':
            st.update(said=f'Cloning {v}')
            return v, file_repo(lr, v)
        if kind in ('folder', 'repo'):
            name, fs = Path(v).name, ([] if folder_why(v) else tree_files(v))
            nb = sum(p.suffix == '.ipynb' for p in fs)
            st.update(said=f"Filing {name}: {n_of(nb, 'notebook') if nb else n_of(len(fs), 'file')}")
            return name, file_folder(lr, v)
        if kind == 'link':
            st.update(said='Getting the pages from the link')
            return v, file_link(lr, v)
        if kind == 'vault': return v, root_docs(lr, v)
        if kind == 'doc' and (d := lr.vault.doc(v)): return d['title'], L([AttrDict(shelf='store', doc_id=d['id'], title=d['title'], url=d['source'])])
        return v, L()   # vedicreader: the walk reads it as a source, it is not filed

    def from_goal(goal, ids, st, subject=''):
        "On the pool: file each chip that is not in the vault, then plan the walk to `goal` (or, with no goal, walk through the docs). Return the walk id."
        filed, notes, docs, names = st.setdefault('filed', []), [], L(), []   # `st.filed`: the Undo still works when the walk fails
        for i in ids:
            kind, _, v = i.partition(':')
            try: name, ds = file_chip(i, st)
            except Exception as e:   # one source that fails never stops the walk
                log.warning('abhyasa could not file the source %r: %r', i, e)
                why = f' {e}' if isinstance(e, LinkError) and not str(e).startswith('abhyasa could not') else ''
                notes.append((f'abhyasa could not clone {v}.' if kind == 'gh' else f'abhyasa could not file {Path(v).name or v}.') + why)
                continue
            docs += ds; names.append(name)
            if cut := getattr(ds, 'cut', ''): notes.append(f'{name}: {cut}')
            if added := getattr(ds, 'added', None):
                filed.append(dict(root=name, docs=[dict(x) for x in added], at=time.time(), notebooks=sum(str(x.url).endswith('.ipynb') for x in added)))
        st.update(said='Planning the walk')
        if goal: j = walk_from_topic(lr, ask, goal, profile_text(lr.profile()), ctx.sources, False, chips=ids)   # the plan sees the documents of the chips
        elif docs:
            n = val('links.pages')
            j = journey_from_sources(lr, ask, docs[:n], title=' and '.join(names), subject=subject,
                                     progress=lambda k, m: st.update(said=f"Reading {k + 1} of {n_of(m, 'document')}"))
        else: raise LinkError(' '.join(notes) or 'abhyasa found no text to read in these sources.')
        run_hook('concepts_added')
        if not j.steps:
            lr.drop_journey(j.id)
            raise LinkError('The tutor found no steps for this goal.' if goal else 'The tutor found no ideas in these sources.')
        lr.merge_journey(j.id, filed=filed, notes=notes, chips=list(ids))
        if goal:
            research_new(j)
            if val('research.on') and not val('research.told'): set_val('research.told', True)
        return j.id

    def goal_walk(goal, ids, subject=''):
        "Start the pool job that files the chips `ids` and makes the walk, unless one is running. The request does not wait."
        key = 'goal:' + hashlib.sha1(json.dumps([goal, ids]).encode()).hexdigest()[:12]
        st = links.get(key)
        if not st or st.job.done():
            st = links[key] = AttrDict(said='Planning the walk')
            st.job = ctx.pool.submit(from_goal, goal, ids, st, subject)
        return ui.LinkPending(key, st.said)

    def path_walk(jid):
        "On the pool: make the path `jid` a walk, with a passage from your sources and a check on each step, then look for web sources. Return the walk id."
        with _jlock(jid):
            if not (j := lr.journey(jid)): raise LinkError('This walk is not there now.')
            if j.get('mode') != 'walk': j = _topic_walk(lr, j, ctx.sources)
        research_new(j)
        return j.id

    @hook('walk_from_path')
    def from_path(j):
        "Start the pool job that makes path `j` a walk, unless one is running. The pending card is the same as for a walk from a goal."
        key = f"path:{j['id']}"
        st = links.get(key)
        if not st or st.job.done():
            st = links[key] = AttrDict(said='Reading your sources for each step')
            st.job = ctx.pool.submit(path_walk, j['id'])
        return ui.LinkPending(key, st.said)

    def unfile_(jid:str='', root:str='', job:str='', row:str=''):
        """Undo, for one hour after Start: forget the docs that Start added for `root` (for walk `jid`, or for the pool job `job` when its walk failed), when each is still the same file.
        With `row`, the answer is a list item, for a row of a list such as Sources."""
        said = undo(jid, root, job)
        return Li(said, cls='lrow') if row else said

    def undo(jid, root, job):
        st = links.get(job) if job else None
        if not (j := walk_of(jid) if jid else st): return Response(status_code=404)
        f = first(x for x in j.get('filed') or () if x['root'] == root and not x.get('undone'))
        if not f: return P('There is nothing to undo.', cls='mute')
        if not ui.can_undo(f): return P('The time for Undo is over. abhyasa keeps these documents.', cls='mute')
        n = unfile(lr, f['docs'])
        if st: f['undone'] = True
        else: lr.merge_journey(jid, filed=[{**x, 'undone': True} if x['root'] == root else x for x in j['filed']])
        return P(f"Removed {root} from your vault: {n_of(n, 'document')}.", cls='mute filed')

    def job(url:str=''):
        "The state of the walk from `url`: the pending card, a redirect to the walk when it is ready, or a message."
        if not (st := links.get(url.strip())): return P('No walk is being made from this link. Send the form again.', cls='req-err')
        if not st.job.done(): return ui.LinkPending(url.strip(), st.said)
        if (e := st.job.exception()):   # never the words of a library; what Start filed keeps its Undo
            return Div(P(str(e) if isinstance(e, LinkError) else NO_LINK, cls='req-err'), ui.Filed(dict(id='', filed=st.get('filed')), job=url.strip()))
        return Response(headers={'HX-Redirect': ui.at(Routes.one, st.job.result())})

    def new(ref:str='', shelf:str='store', text:str='', title:str='', topic:str='', url:str='', pages:str='', tool:str='', subject:str='',
            q:str='', pick:str='', file:str='', opts:str='', doc:str='', sources:list[str]=None, chips:str=''):
        if (q.strip() or chips) and not any(x.strip() for x in (ref, text, topic, url)):   # the Start box: its reading says which field it is
            t = vault_title(lr.vault, q) if not file else None
            r = detect(q, dict([t]) if t else {}, research=val('research.on'), file=file, pick=pick, doc=doc, roots_in_vault=vault_roots(lr))   # `ref` is a document id
            ids = [x for x in (sources or []) if x] if chips else r.send.get('sources', [])   # the chips that the box showed, less the ones that you removed
            goal = r.kind == 'goal' or (chips and r.kind == 'topic')   # a topic with sources that you added is a goal
            if (goal or r.kind in ('sources', 'folder')) and (r.send or chips):
                if not goal and not ids: return P('Add a source first.', cls='req-err')
                return goal_walk(q.strip() if goal else '', ids, clean_subject(subject))
            if chips and not q.strip(): return P('Write your goal first.', cls='req-err')
            if not r.send: return P(r.line if r.kind != 'ask' else 'Pick one answer first.', cls='req-err')
            ref, text, topic, url = (r.send.get(k, '') for k in ('ref', 'text', 'topic', 'url'))
            title = title or r.send.get('title', '')
            if not opts: tool = tool or r.send.get('tool', '')   # the options of the box were not shown: the reading picks
        tool, ref, shelf, subject = tool == 'on', ref.strip(), shelf.strip() or 'store', clean_subject(subject)
        if url.strip(): return link_walk(url.strip(), pages, tool, subject)
        if (u := as_link(ref)): return Div(P(AS_LINK, cls='mute'), link_walk(u, '', tool, subject))   # a link in the vault document field
        try:
            if ref and (lr.vault if shelf == 'store' else lr.vault.shelf(shelf)).doc(ref) is None:
                log.warning('the tutor could not make a walk: no vault document matches %r', ref)
                return P(NO_DOC, cls='req-err')
            if ref: j = journey_from_source(lr, ask, ref, shelf, subject, tool)
            elif text.strip(): j = journey_from_text(lr, ask, text.strip(), title.strip() or text.strip().splitlines()[0][:60], subject, tool)
            elif topic.strip(): j = walk_from_topic(lr, ask, topic.strip(), profile_text(lr.profile()), ctx.sources, tool)
            else: return P('Name a vault document, paste a text, or write a topic.', cls='req-err')
        except Exception as e:   # the log keeps the words of the library; the page shows a plain line
            log.warning('the tutor could not make a walk: %r', e)
            return P(str(e) if isinstance(e, LinkError) else 'The tutor could not make a walk. Try again.', cls='req-err')
        run_hook('concepts_added')   # a topic walk too: its concepts have a subject when the learner gave one
        if not j.steps:
            lr.drop_journey(j.id)
            return P('The tutor found no ideas in this document.' if ref or text.strip() else 'The tutor found no steps for this topic.', cls='req-err')
        if topic.strip() and not ref and not text.strip():
            research_new(j)
            if val('research.on') and not val('research.told'): set_val('research.told', True)   # the box said one time that a topic goes to the search
        else: write_notebooks(j)   # a walk from a document or a text: no web search, but its notebook steps get their spec
        if ref: ctx.pool.submit(retitle, j.id)   # a vault PDF with an arXiv id for a name: the title of the paper comes after the page
        return Response(headers={'HX-Redirect': ui.at(Routes.one, j.id)})

    def one(jid:str):
        if not (j := walk_of(jid)): return missing()
        leela_back(lr, j)   # a step that Leela checked is done, so the walk goes on from the next one
        st = walk_state(j := lr.journey(jid))
        if j.get('started') and st.current is not None: return go(jid, st.current)
        h1, *rest = ui.PlanPage(j, st, by(), run_hook('walk_actions', j), vault=vault)
        return Page(j.title, h1, ui.Filed(j), *rest, on='Learn', crumbs=up, extra=ui.assets())   # Undo for what Start filed, under the title

    def plan(jid:str, i:int, act:str, way:str=''):
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        if act == 'drop':
            with _jlock(jid):   # under the lock of the walk, so a source that research writes now stays
                j = lr.journey(jid); j.steps.pop(i)
                j = lr.put_journey(j)
        elif act == 'check' and way in (TOOL_WAYS if j.get('tool') else WALK_WAYS):
            kind = CHECK_KIND.get(way, 'short')
            floor = (lr.concept(j.steps[i]['slug']) or {}).get('floor') or 0
            j = lr.walk_step(jid, i, check=dict(way=way, kind=kind, depth=(2 if floor < 2 else 3) if kind == 'short' else DEPTH[kind], why='you chose it'))
        else: return Response(status_code=400)
        return ui.Plan(j, walk_state(j), by())

    def start(jid:str):
        if not (j := walk_of(jid)): return missing()
        with _jlock(jid):   # read and write under the lock of the walk, so a source that research writes now stays
            if not (j := lr.journey(jid)).get('started'): j = lr.put_journey({**j, 'started': time.time(), 'steps': [{**RUN, **s} for s in j.steps]})
        sitting(j)
        return go(jid, walk_state(lr.journey(jid)).current or 0)

    def step(jid:str, i:int):
        if not (j := walk_of(jid, i)): return missing()
        if not for_talk(j):   # a side walk of a talk is for the room: it keeps no read time and starts no demo
            if not j.steps[i].get('read_at'): j = lr.walk_step(jid, i, read_at=time.time())
            ahead(j, i + 1)
        back = leela_back(lr, j)
        j, b = lr.journey(jid), by()
        page = ui.StepPage(j, walk_state(j), b, i, needs=run_hook('step_needs', j, i, b.get(j.steps[i]['slug'])), back=back_to(j), vault=vault,
                       present=run_hook('walk_actions', j, quiet=True), looking=looking(jid, i), result=None if for_talk(j) else from_leela(j, i, back))
        return Page(ui.name(b, j.steps[i]), page, wide=True, extra=ui.assets(),
                    on='Learn', crumbs=[*up, (j.title, ui.at(Routes.one, jid))])

    def note(jid:str, i:int):
        "The tutor note of step `i`, loaded after the page; a failed note shows nothing."
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        try:
            with writing[jid, i]: return ui.Note(tutor_note(lr, ctx.ask, j, i, ctx.sources))
        except Exception: return ''

    def source(jid:str, i:int):
        "The passage of step `i` as it is now. When a web source came, the note loads again, so it explains the passage. A GET only reads."
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        s = j.steps[i]
        out = ui.Passage(j, s, by().get(s['slug']), i, looking(jid, i))
        return (out, ui.NoteSlot(jid, i, oob=True)) if (s.get('read') or {}).get('src') == 'web' else out

    def find_source(jid:str, i:int):
        "Find a source: look for a web source for step `i` on the pool, also after a search that found nothing. Off in Settings, it does nothing."
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        if val('research.on') and wants_source(j.steps[i]): look_for(jid, [i])
        return source(jid, i)

    def check(jid:str, i:int):
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        if (got := from_leela(j, i)) is not None: return got   # what came back from Leela takes the place of the check
        with writing[jid, i]:
            j = lr.journey(jid)
            if j.steps[i]['check']['kind'] == 'notebook': return card(j, i)   # it runs in Leela: abhyasa opens no question on it
            if not j.steps[i].get('done') and j.steps[i]['check']['kind'] in AIM and not demo(j.steps[i]):
                if (wait := no_demo(j, i)): return wait
                j = lr.journey(jid)
            if not j.steps[i].get('done') and j.steps[i]['check']['kind'] not in AIM and j.steps[i].get('qid') not in tutor.open:
                s = sitting(j)
                s.q = (open_code(j, i, s.id) if j.steps[i]['check']['kind'] == 'code' else None) or open_short(tutor, as_short(j, i), i, s.id)
                s.save()
        return card(lr.journey(jid), i)

    def nb_again(jid:str, i:int):
        "Try again to write the notebook spec of step `i`, after the tutor could not."
        if not (j := walk_of(jid, i)) or j.steps[i]['check']['kind'] != 'notebook': return Response(status_code=404)
        if j.steps[i].get('nb_why'): j = lr.walk_step(jid, i, nb_why='')
        return card(j, i)

    def notebook(jid:str, i:int):
        "The notebook of step `i` as a Jupyter file to download: the task, the setup, the stub, the tests and the run."
        if not (j := walk_of(jid, i)) or not (spec := j.steps[i].get('nb')): return Response(status_code=404)
        name = f'{jid}-{i}.ipynb'
        try: p = spec_notebook(spec, Path(tempfile.mkdtemp(prefix='abhyasa-nb-'))/name)
        except ValueError: return Response('The notebook of this step is not valid. Write it again.', status_code=409)
        return FileResponse(p, media_type='application/x-ipynb+json', headers={'Content-Disposition': f'attachment; filename="{name}"'})

    def open_leela(jid:str, i:int):
        "Open in Leela: note the time on step `i` (`leela_at`), then go to the Leela link. When Leela does not run, go back to the step."
        if not walk_of(jid, i): return Response(status_code=404)
        if not (link := leela_link(lr.journey(jid), i, vault=vault)): return RedirectResponse(ui.at(Routes.step, jid, i), status_code=303)
        lr.walk_step(jid, i, leela_at=time.time())
        return RedirectResponse(link, status_code=303)

    def data(jid:str, i:int, name:str='', path:str=''):
        "Set the path of the data entry `name` of the notebook of step `i`, as the folder of your images. A path outside your home folder is refused."
        with _jlock(jid):   # read and write under the lock of the walk
            if not (j := walk_of(jid, i)) or not (spec := j.steps[i].get('nb')): return Response(status_code=404)
            if not any(d['name'] == name for d in spec['data']): return Response('The notebook has no data with this name.', status_code=400)
            if why := path_why(path.strip()): return Response(f'abhyasa did not keep this path: {why}. Use a folder in your home folder, as ~/Pictures/comic.', status_code=400)
            try: new = validate_nb_spec({**spec, 'data': [{**d, 'path': path.strip()} if d['name'] == name else d for d in spec['data']]})
            except ValueError as e: return Response(f'abhyasa did not keep this path: {e}.', status_code=400)
            j = lr.walk_step(jid, i, nb=new)
        return card(j, i)

    def answer(jid:str, i:int, answer:str='', thinking:str='', confidence:int=None):
        j, s = live(jid, i)
        if not s: return no_check(j, i)
        try: r = s.answer(answer, thinking, confidence)
        except KeyError: return no_check(lr.journey(jid), i)   # another request closed it while this one waited
        return closed(j, i, r) if r.done else reply(j, i)

    def run(jid:str, i:int, source:str=''):
        "Run the code of step `i` on its tests; the reply is the results part only."
        if len(source) > MAX_SOURCE: return Response(f'The code is too long. Send at most {MAX_SOURCE:,} characters.', status_code=413)
        with writing[jid, i]:   # one run at a time, so a double click does not use two tries
            j, s = live(jid, i)
            if not s or not j.steps[i].get('code'): return no_check(j, i) if s is None else Response('This check is not a code check.', status_code=409)
            r = s.code(source)
            return closed(j, i, r) if r.done else reply(j, i, r)

    def hint(jid:str, i:int):
        j, s = live(jid, i)
        if not s: return no_check(j, i)
        try:
            if len(tutor.open[s.q.id].hints) < len(HINTS): s.hint()
        except KeyError: return no_check(lr.journey(jid), i)
        return reply(j, i)

    def giveup(jid:str, i:int, confidence:int=None):
        j, s = live(jid, i)
        if not s: return no_check(j, i)
        try: r = s.give_up(confidence=confidence or 0) if tutor.open[s.q.id].tries else s.answer(dont_know=True, confidence=confidence)
        except KeyError: return no_check(lr.journey(jid), i)
        return closed(j, i, r)

    def lesson_job(jid, i, slug):
        "Start the pool job that writes the lesson in another way of step `i`, unless it runs. The job keeps the lesson on the step."
        k = f'{slug}:lesson'
        if (jb := tutor.jobs.get(k)) is not None and not jb.done(): return
        ld = lr.journey(jid).steps[i]['ladder']
        a = first(x for x in lr.attempts(slug) if x.id == ld.get('aid'))
        def job():
            if not (text := demo_lesson(tutor, a, ld['way'])) or isinstance(text, NoLesson): return   # an empty lesson or the fallback note is a failure
            with writing[jid, i]: lr.walk_step(jid, i, ladder={**(lr.journey(jid).steps[i].get('ladder') or {}), 'lesson': text})
        if a is not None: tutor.jobs[k] = ctx.pool.submit(job)

    def climb(jid, i, a):
        "After the wrong prediction `a` in the demo check of step `i`, keep the next rung of the demo ladder on the step. The URL of its help, or ''."
        s = lr.journey(jid).steps[i]
        if a.correct or s['check']['kind'] != 'demo' or not val('checks.demo_ladder') or (k := rung(lr, s['slug'])) not in (1, 2): return ''
        old, slug, simple = s.get('ladder') or {}, s['slug'], said(lr, s['slug'], 'simple')
        if k == 1 and said(lr, slug, 'unclear'): ld = dict(rung=2, aid=a.id)   # "Not clear" on the demo: the simpler demo comes now
        elif k == 1: ld = dict(rung=1, aid=a.id, way=other_way(lr, slug, s['check']['way']), **({'simple': True} if simple else {}))
        elif simple: ld = dict(rung=1, aid=a.id, way=other_way(lr, slug, (s['check']['way'], old.get('way', ''))), simple=True)   # "Too simple": one more lesson, no simpler demo
        else: ld = {**old, 'rung': 2}
        with writing[jid, i]: lr.walk_step(jid, i, ladder=ld)
        if not backed(lr, slug, tutor.goal):   # the job starts now, so the help is often ready when the page asks
            if ld['rung'] == 1: lesson_job(jid, i, slug)
            else: simpler_demo(tutor, slug)
        return ui.at(Routes.ladder, jid, i)

    def ladder_view(jid, i, s, show=''):
        "The help under the demo check of step `i` as it is now. It only reads: it starts no job and writes nothing."
        ld, slug = s['ladder'], s['slug']
        stop = backed(lr, slug, tutor.goal)   # once `_back` steps back to a prereq, the ladder makes nothing
        if ld['rung'] == 1 and not ld.get('asked'):
            if ld.get('lesson') or stop: return ui.Ladder(jid, i, ld, more=not ld.get('simple'))   # after "Too simple", no link to a simpler demo
            jb = tutor.jobs.get(f'{slug}:lesson')
            if jb is not None and not jb.done(): return ui.Ladder(jid, i, ld, pending='The tutor is writing a lesson in another way. You can read the passage while you wait.')
            lost = first(x for x in lr.attempts(slug) if x.id == ld.get('aid')) is None   # no attempt: a new job cannot help
            return ui.Ladder(jid, i, ld, failed='The tutor could not write a lesson this time.', retry=not lost)
        # the simpler demo: after the second wrong prediction, or when you asked for it
        if (d := lr.demo_for(slug, aim='simpler')) and not said(lr, slug, 'unclear'): return ui.Ladder(jid, i, ld, demo=d, show=bool(show) or bool(ld.get('asked')))   # after "Not clear", a new one
        st = job_state(tutor, slug, 'simpler')
        if stop and st != 'failed': return ui.Ladder(jid, i, ld)
        if st == 'running': return ui.Ladder(jid, i, ld, pending='The tutor is making a simpler demo of this idea. You can read the passage while you wait.')
        return ui.Ladder(jid, i, ld, failed='The tutor could not make a simpler demo this time.', retry=True)

    def ladder(jid:str, i:int, show:str=''):
        "The help under the demo check of step `i`: the lesson in another way, then the simpler demo. A GET only reads."
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        return ladder_view(jid, i, j.steps[i], show) if j.steps[i].get('ladder') else ui.Slot(jid, i, j.steps[i])

    def ask_ladder(jid:str, i:int, simpler:str=''):
        """Ask for help under the demo check of step `i`: the simpler demo (`simpler`, so a demo with one gate can reach it, and the feedback row
        after "Not clear" before a prediction), or the job again after a failure. This is the only route that starts a help job."""
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        if not (ld := j.steps[i].get('ladder')):
            if not simpler or j.steps[i]['check']['kind'] != 'demo': return ui.Slot(jid, i, j.steps[i])
            with writing[jid, i]: lr.walk_step(jid, i, ladder=(ld := dict(rung=2, asked=True)))
        if simpler and not ld.get('asked'):
            with writing[jid, i]: lr.walk_step(jid, i, ladder={**lr.journey(jid).steps[i]['ladder'], 'asked': True})
        s = walk_of(jid, i).steps[i]; ld, slug = s['ladder'], s['slug']
        if not backed(lr, slug, tutor.goal):
            if ld['rung'] == 1 and not ld.get('asked'):
                if not ld.get('lesson'): lesson_job(jid, i, slug)
            else: simpler_demo(tutor, slug)   # the demo there, or a job for a new one
        return ladder_view(jid, i, s)

    def predict(jid:str, i:int, slug:str, gate:str, picked:str, ans:str='', ok:str='', why:str='', context:str='', confidence:int=None):
        "Log the first prediction on each gate in the demo of step `i` with the walk; the first one closes the step (spec 6.5)."
        j = walk_of(jid, i)
        if not j or (s := j.steps[i])['check']['kind'] not in AIM or not (d := lr.demo(slug)) or d.concept != s['slug']:
            return JSONResponse(dict(ok=False), status_code=404)
        if (s.get('done') or {}).get('outcome') == 'skipped': return JSONResponse(dict(ok=False), status_code=409)
        if first(a for a in lr.attempts(s['slug']) if (a.get('walk'), a.get('step'), a.get('demo'), a.get('gate')) == (jid, i, slug, gate)):
            return JSONResponse(dict(ok=True, again=True))   # one record for each gate of each demo: a second try comes after the answer showed
        st, floor0 = sitting(j), lr.concept(s['slug']).get('floor') or 0
        a = lr.record_prediction(slug, gate, picked, ans, ok == 'true', why, context, st.id, confidence,
                                 kind=s['check']['kind'], method=s['check']['way'], **step_meta(j, i))
        st.noted(a, floor0)
        with writing[jid, i]:
            if not lr.journey(jid).steps[i].get('done'): lr.walk_step(jid, i, done=dict(outcome=a.outcome, aid=a.id, at=time.time()))
        ws, help_ = walk_state(lr.journey(jid)), climb(jid, i, a)
        # walk.js fills the dot, moves the progress line, and loads the help under the card when there is a `ladder`
        return JSONResponse(dict(ok=True, dot=ws.steps[i].dot, done=ws.done, total=ws.total, **({'ladder': help_} if help_ else {})))

    def keep(jid:str, i:int, state:str=''):
        "Keep the state of the demo on the newest prediction of step `i`."
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        try: kept = json.loads(state) if len(state) <= MAX_STATE else None
        except ValueError: kept = None
        if kept is None: return Response('The state is not valid.', status_code=400)
        a = first(a for a in lr.attempts(j.steps[i]['slug']) if a.get('walk') == jid and a.get('step') == i and a.get('demo'))
        if not a: return Response('Make a prediction first.', status_code=409)
        lr.mark_attempt(a.id, keep=kept)
        return JSONResponse(dict(ok=True))

    def next_(jid:str, i:int):
        "Skip step `i` when it has no outcome yet, then go to the next step, or to the summary at the end of a section."
        if not (j := walk_of(jid, i)): return missing()
        st = walk_state(j)
        if not j.steps[i].get('done'):
            if (qid := j.steps[i].get('qid')) in tutor.open:
                tutor.open.pop(qid)
                if (s := sessions.get(j.get('sitting') or '')) and s.q and s.q.id == qid: s.q = None; s.save()
            lr.walk_step(jid, i, done=dict(outcome='skipped', at=time.time()))
        ends = any(ix[-1] == i for _, ix in st.sections)
        if ends and (sid := j.get('sitting')) and (s := sessions.pop(sid, None) or Session.load(tutor, sid)) and not s.ended:
            s.end()   # the section ends here, on the POST, not on the GET of its summary
        # a plain 303, not HX-Redirect: htmx follows it and swaps the page in place, so the next idea comes in with a view transition
        return RedirectResponse(ui.at(Routes.done, jid, i) if ends else ui.at(Routes.step, jid, i + 1), status_code=303)

    def done(jid:str, i:int):
        "The summary of the section of step `i`. It changes nothing: Next idea ended the sitting, and the next step opens a new one."
        if not (j := walk_of(jid, i)): return missing()
        back = leela_back(lr, j)
        j = lr.journey(jid)
        sec, ix = next((sec, ix) for sec, ix in walk_state(j).sections if i in ix)
        slugs = {j.steps[k]['slug'] for k in ix}
        s = (sessions.get(sid) or Session.load(tutor, sid)) if (sid := j.get('sitting')) else None
        rows = [r for r in (s.log if s else ()) if r['concept'] in slugs]
        nxt = ix[-1] + 1 if ix[-1] + 1 < len(j.steps) else None
        crumbs = [*up, (j.title, ui.at(Routes.one, jid))]
        if nxt is not None: return Page('Section done', *ui.SectionDone(j, sec, ix, moved(rows), nxt, by()), on='Learn', crumbs=crumbs, extra=ui.assets())
        b = by()
        logs = [x.get('log') or [] for x in sorted(lr.sessions(limit=None, journey=jid), key=lambda x: x.get('start') or 0) if x.get('id') != sid]
        rows = [r for log in logs for r in log] + (s.log if s else [])   # the whole walk: every sitting, in order
        sides = [((b.get(d['slug']) or {}).get('name', d['slug']), d.get('outcome') in ('solid', 'fragile')) for st in j.steps for d in st.get('detours') or ()]
        now, slugs = time.time(), {st['slug'] for st in j.steps if (st.get('done') or {}).get('outcome') not in (None, 'skipped')}
        due = min((c.due for k in slugs if (c := b.get(k)) and c.get('due') and c.due > now), default=None)
        k = max((k for k, x in back.items() if x.run and x.run.get('images')), default=None)   # the last step with images: what you made
        made = ui.WhatYouMade(j, k, back[k]) if k is not None else ''
        return Page('You finished the walk', *ui.WalkDone(j, walk_state(j), moved(rows), b, sides, due, run_hook('walk_end', j), run_hook('walk_actions', j, quiet=True), made=made),
                    on='Learn', crumbs=crumbs, extra=ui.assets())

    def img(jid:str, i:int):
        "The figure of step `i`, only from inside the vault assets and only as an image file."
        if not (j := walk_of(jid, i)) or not (f := (j.steps[i].get('read') or {}).get('figure')): return Response(status_code=404)
        root = Path(lr.vault.assets()).resolve()
        p = (root/f).resolve()
        if not p.is_relative_to(root) or p.suffix.lower() not in FIGURES or not p.is_file(): return Response(status_code=404)
        return FileResponse(p)

    def result(jid:str, i:int, n:str):
        """One image of a run that Leela filed for step `i`: only `<assets>/leela/<jid>/<i>/<n>.png`, `n` one digit, listed by the run of
        the step that `run_ok` accepts, and a PNG file of at most `MAX_RESULT` bytes."""
        if not re.fullmatch(r'[0-9]', n) or not (j := walk_of(jid, i)): return Response(status_code=404)
        run = (leela_found(lr, j).get(i) or AttrDict(run=None)).run
        if not run or f'leela/{jid}/{i}/{n}.png' not in run.get('images', []): return Response(status_code=404)
        root = (Path(lr.vault.assets())/'leela').resolve()
        p = (root/jid/str(i)/f'{n}.png').resolve()
        try:
            ok = p.is_relative_to(root) and p.is_file() and p.stat().st_size <= MAX_RESULT
            if ok:
                with p.open('rb') as f: ok = f.read(8) == PNG
        except OSError: ok = False
        if not ok: return Response(status_code=404)
        return FileResponse(p, media_type='image/png', headers={'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': "default-src 'none'"})

    def walks_of(slug):
        "`(walk, index)` for each walk that has a step on concept `slug`."
        return [(j, i) for j, i in with_step(lr, slug) if j.get('mode') == 'walk' and not for_talk(j)]

    @hook('pane_title')
    def pane_title(url):
        "The title of the walk at `url` (`/w/<id>/<step>`) in the side pane; None for another page."
        m = re.match(r'/w/([^/?#]+)/\d+(?:[?#]|$)', url or '')
        return (j := m and walk_of(m.group(1))) and j.title or None

    @hook('concept_more')
    def passages(c):
        "The passage of concept `c` in each walk, with its source line and a link to its step."
        rows = [(j, i, j.steps[i].get('read') or {}) for j, i in walks_of(c.slug)]
        rows = [x for x in rows if x[2].get('text')]
        return Div(H2('In a walk'), *[Div(Blockquote(Md(r['text']), SourceLine(source_of(r, j)), cls='quote'), P(A(f'{j.title}: read it in the walk', href=ui.at(Routes.step, j.id, i)), cls='mute'))
                                      for j, i, r in rows], cls='walk-passages') if rows else None

    @hook('concept_more')
    def leela(c):
        "A link to Leela for a concept with a code way, when Leela runs."
        line = leela_line(None, topic=c.name, say=f'Learn {c.name} with code in Leela', quiet=True, vault=vault) if 'code' in (c.get('ways') or ()) else ''
        return line or None

    @hook('lesson_extra')
    def reread(r):
        "A link back to the passage when the concept of the lesson is a step of a walk."
        s = lr.session(r.get('session') or '') if r.get('session') else None
        rows = [(j, i) for j, i in walks_of(r.concept) if (j.steps[i].get('read') or {}).get('text')]
        j, i = next(((j, i) for j, i in rows if s and j.id == s.get('journey')), rows[0] if rows else (None, None))
        if j is None: return None
        pg = j.steps[i]['read'].get('page')
        return P(A('Read the passage again' + (f': p. {pg}' if pg else ''), href=ui.at(Routes.step, j.id, i)), cls='walk-again')

    app.post(Routes.new)(new)
    app.get(Routes.job)(job)
    app.post(Routes.unfile)(unfile_)
    app.get(Routes.one)(one)
    app.post(Routes.plan)(plan)
    app.post(Routes.start)(start)
    app.get(Routes.step)(step)
    app.get(Routes.note)(note)
    app.get(Routes.check)(check)
    app.post(Routes.check)(nb_again)
    app.post(Routes.answer)(answer)
    app.post(Routes.hint)(hint)
    app.post(Routes.giveup)(giveup)
    app.post(Routes.run)(run)
    app.post(Routes.predict)(predict)
    app.post(Routes.keep)(keep)
    app.get(Routes.ladder)(ladder)
    app.post(Routes.ladder)(ask_ladder)
    app.post(Routes.next)(next_)
    app.get(Routes.done)(done)
    app.get(Routes.img)(img)
    app.get(Routes.result)(result); app.router.routes.insert(0, app.router.routes.pop())   # before fast_app's static route for `.png`
    app.get(Routes.notebook)(notebook)
    app.post(Routes.data)(data)
    app.post(Routes.leela)(open_leela)
    app.get(Routes.source)(source)
    app.post(Routes.source)(find_source)
