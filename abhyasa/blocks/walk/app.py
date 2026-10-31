"""The guided walk: a paper, a text, a topic or a link as one idea at a time, in reading order. The plan, the step page, its check,
Next idea, and the summary at the end of each section. A sitting is a `Session` that the walk feeds itself."""
import hashlib, json, logging, re, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, wait as wait_all
from threading import Lock
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import n_of, Page, hook, run as run_hook, SourceLine, source_of, Md, edit_assets, UndoBar
from abhyasa.core.leela import leela_line, leela_link
from abhyasa.settings import val, set_val
from abhyasa.detect import detect, vault_title
from abhyasa.store import clean_subject
from abhyasa.profile import profile_text
from abhyasa.method import WALK_WAYS, CHECK_KIND, DEPTH, TEXT_WAYS
from abhyasa.tutor import Session, HINTS, public, moved
from abhyasa.sources import file_link, link_kind, LinkError, as_link, is_paper, file_folder, file_repo, folder_why, tree_files, unfile, vault_roots, root_docs
from abhyasa.journey import with_data, keep_data, NAME_MOST, journey_from_source, journey_from_text, journey_from_sources, walk_from_topic, walk_path, walk_paths, TOOL_WAYS, walk_state, short_check, with_step, trail, parent_step, for_talk, _jlock
from abhyasa.walk import tutor_note, open_short, step_meta, leela_back, leela_found
from abhyasa.course import course_of, drop_data
import abhyasa.walk as walk_engine   # `walk_engine.nb_spec` is read on each call, so a test can put a fake in its place
import abhyasa.talk   # adds Learning.talks: the editor links the talks made from a walk
from abhyasa.talk import walk_changes
from abhyasa.edit import (edit_walk, undo_walk, restore_walk, move_step, skip_step, remove_step, merge_steps, add_step, split_step,
                          passages as real_passages, pick_read, CTRL, rewrite as tutor_rewrite, links_in, propose, improve_walk)
from abhyasa.research import to_research, wants_source, want_agent, research_state
from abhyasa.tutor import NoLesson
from abhyasa.demo import queue_demo, job_state, job_age, rung, backed, other_way, demo_lesson, simpler_demo, said, show_ask
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'tutor', 'ask', 'pool', 'sessions', 'sources', 'research')
FIGURES = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
RUN = dict(read_at=None, done=None, qid=None, note=None)   # the run fields of a step (spec 6.3), empty until the step is used
AIM = dict(demo='', order='order')   # check kind -> the aim of its demo
MAX_STATE = 20_000                   # the most chars of a kept demo state
MAX_RESULT = 2 << 20                 # the most bytes of one image of a run from Leela
PNG = b'\x89PNG\r\n\x1a\n'
NO_LINK = 'abhyasa could not make a walk from this link. Try again later, or try another link.'
AS_LINK = 'This is a link, so the tutor reads it from the web.'
NO_DOC = 'No document in your vault has this name. To add a web page or a paper, paste its link.'
NO_REWRITE = 'The tutor could not rewrite this. Nothing changed.'
KEPT = 'Your edit was kept. The rewrite was not used.'
FILE_WAIT = 20   # seconds that the plan of a goal waits for its sources; a slower one, such as a big clone, joins the walk when it is filed
FILERS = 3       # the sources that file at the same time, each on its own job, off the pool of the app
NO_ADD, NO_SPLIT = 'The tutor could not add this idea. Nothing changed.', 'The tutor could not split this idea. Nothing changed.'
NOTE_MOST, Q_MOST, WORDS_MOST = 2000, 500, 1000   # the most characters of a tutor note, of a check question that you write, and of what you ask Improve the walk to change
EDIT_ACTS = ('move', 'skip', 'back', 'remove', 'split', 'merge', 'add', 'pick', 'note', 'check', 'q', 'rewrite')

class Kept(Exception):
    "A rewrite that came after you changed each of its fields: your edits stay, and the rewrite is not used."

def bad(s): return Response(s, status_code=400, media_type='text/plain')

def place(s, n):
    "The index in `s` (digits only, as `isdecimal` reads them) in a list of `n`; else `ValueError`."
    s = str(s).strip()
    try: k = int(s) if s.isdecimal() else -1
    except ValueError: k = -1
    if not 0 <= k < n: raise ValueError('Give a place in the list.')
    return k

def on_step(slug, fn):
    "An editor change that runs `fn` on the step on `slug` in the steps that it gets."
    def op(ss):
        s = next((s for s in ss if s.get('slug') == slug), None)
        if s is None: raise KeyError('This idea is not in the walk now.')
        fn(s)
        return ss
    return op
log = logging.getLogger(__name__)

def connect(app, ctx):
    lr, tutor, sessions = ctx.learning, ctx.tutor, ctx.sessions
    vault = lr.vault.path         # each Leela link names the vault of this app with its key
    ask = ctx.ask   # the engine picks the model of each task (`for_task`) on each call, so a settings change works at once
    up = [('Home', '/')]
    writing = defaultdict(Lock)   # (walk, concept of the step) -> a lock, so the note and the check of one step do not write the note twice; a move keeps it
    links = {}                    # link -> the pool job that makes its walk, and `said`, the words of its state

    def by(): return {c.slug: c for c in lr.concepts()}

    def slug_at(jid, i):
        "The concept of step `i` of walk `jid` now, or ''."
        j = lr.journey(jid)
        return j.steps[i]['slug'] if j and 0 <= i < len(j.steps) else ''

    def of_step(a, jid, i, slug):
        "Whether attempt `a` is on the step of walk `jid` on concept `slug` (now at place `i`): by `idea`, or by the place for an old attempt with no `idea`."
        return a.get('walk') == jid and (a['idea'] == slug if a.get('idea') else a.get('step') == i)

    def held(jid, i): return writing[jid, slug_at(jid, i)]   # the lock of step `i`, by its concept

    def put(j, i, **kv):
        "Merge `kv` into step `i` of walk `j` as `j` has it, found again by its concept, so a move in the editor at the same time keeps it on the same idea. The walk now."
        return lr.walk_slug(j['id'], j['steps'][i]['slug'], **kv) or lr.journey(j['id'])
    def go(jid, i): return Redirect(ui.at(Routes.step, jid, i))
    def missing(): return Page('Walk', H1('No such walk'), P(A('Your walks', href='/')), on='Home', crumbs=up)

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
        return ui.CHECKS.get(k, ui.Short)(j.id, i, s, q, after=run_hook('check_after', j, i, q) if q else ())

    def back_to(j):
        "The way back from side walk `j` to the step that opened it, and the trail for the side pane; None for a walk with no parent."
        pj, i = parent_step(lr, j)
        if not pj: return None
        parts = [[f"Idea {t.step + 1}", ui.at(Routes.step, t.walk, t.step)] for t in trail(lr, j.id)[:-1] if t.step is not None]
        return AttrDict(href=ui.at(Routes.step, pj.id, i), here=f"idea {i + 1} of {len(pj.steps)}", trail=parts)

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
        put(j, i, check=dict(short_check(lr, lr.concept(slug))))

    def no_check(j, i):
        "The reply to a move on a check that is not open: the closed card, or 409 when the check was never loaded."
        if not j: return Response(status_code=404)
        if j.steps[i].get('done'): return card(j, i)
        return Response('No check is open on this idea. Load the page again.', status_code=409)

    def live(jid, i):
        "The sitting with the open question of step `i` as its question, or None when the check is not open."
        if not (j := walk_of(jid, i)) or (qid := j.steps[i].get('qid')) not in tutor.open: return j, None
        s = sitting(j)
        if not s.q or s.q.id != qid: s.q = public(tutor.open[qid])
        return j, s

    def closed(j, i, r):
        "Mark step `i` done with the outcome of its check."
        j = put(j, i, done=dict(outcome=r.outcome, aid=tutor.shut[j.steps[i]['qid']].get('aid'), at=time.time()))
        return card(j, i), *ui.Filled(j, walk_state(j, b := by()), b, i)   # the dot of the idea fills in the outline

    looking, look_for = ctx.research.looking, ctx.research.look_for   # research runs on its own pool; the request does not wait
    gathering = ctx.research.gathering   # the gather agent runs on its own pool, too

    def halted(jid):
        "Whether Stop was asked for the research of walk `jid`, which may still end its last call."
        return (ev := ctx.research.stops.get(jid)) is not None and ev.is_set()

    def band(j, plan=False):
        "The line of research of walk `j`, as it is now."
        running = ctx.research.running(j['id'])
        return ui.GatherBand(j, research_state(j, running), running and halted(j['id']), plan)

    def seen(j):
        "The learner opened walk `j` after its research ended: the notice on each page goes."
        if j.get('research_end') and not j.get('research_seen') and not ctx.research.running(j['id']):
            with _jlock(j['id']): lr.merge_journey(j['id'], research_seen=True)

    @hook('page_extra')
    def research_notice():
        "On any page: a notice for each walk whose research ended in this run of abhyasa, until the learner opens the walk."
        out = []
        for jid in list(ctx.research.jobs):
            if ctx.research.running(jid) or not (j := lr.journey(jid)) or for_talk(j): continue   # a side walk of a talk is for the room
            if j.get('research_end') and not j.get('research_seen') and time.time() - j['research_end'] < 6 * 3600: out.append(ui.ResearchNotice(j))
        return Div(*out, cls='research-notices') if out else ''

    def status():
        "For the Mac app: the walks whose research runs now, and the walks whose research ended in the last 6 hours, each with its title, its link and the time of its end."
        def row(j): return dict(id=j['id'], title=j.get('title') or 'Walk', url=ui.walk_url(j['id'], 'sources'), end=j.get('research_end'), have=(s := research_state(j)).have, total=s.total)
        js = [j for jid in list(ctx.research.jobs) if (j := lr.journey(jid)) and not for_talk(j)]
        return JSONResponse(dict(running=[row(j) for j in js if ctx.research.running(j['id'])],
                                 ended=[row(j) for j in js if not ctx.research.running(j['id']) and (j.get('research_end') or 0) > time.time() - 6 * 3600]))
    nb_jobs, nb_lock = {}, Lock()   # (walk, concept of the step) -> the research pool job that writes the notebook spec of the step

    def nb_writing(jid, i):
        "Whether a job writes the notebook spec of step `i` of walk `jid` now."
        return (f := nb_jobs.get((jid, slug_at(jid, i)))) is not None and not f.done()

    def write_notebook(jid, i):
        "Start the job that writes the notebook spec of step `i` on the research pool, unless it runs or the step has a spec."
        with nb_lock:
            j = walk_of(jid, i)
            if not j or nb_writing(jid, i) or j.steps[i].get('nb') or j.steps[i]['check']['kind'] != 'notebook': return
            nb_jobs[jid, j.steps[i]['slug']] = ctx.research.pool.submit(walk_engine.nb_spec, lr, ask, j, i)   # nb_spec writes to the step by its concept

    def with_folders(j, i):
        "Walk `j` with each of its data folders in the notebook spec of step `i`: a folder that you added after the tutor wrote the spec joins it, so Leela gets it."
        spec = j.steps[i].get('nb')
        if spec and (d := with_data(spec.get('data'), j.get('data'))) != list(spec.get('data') or ()): return put(j, i, nb={**spec, 'data': d})
        return j

    def nb_card(j, i):
        "The card of a notebook step: the notebook, the line while the tutor writes it, or the reason when it could not."
        j = with_folders(j, i)
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
        try: n = lr.doc_shelf(docs[0].shelf).doc(docs[0].doc_id)['pages']
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
        return v, L()   # a kind that abhyasa does not know: nothing to file

    filer = ThreadPoolExecutor(FILERS, thread_name_prefix='abhyasa-file')

    def file_one(i, st):
        "On the filer: file the chip `i`. What it gave: `name`, `docs`, `notes`, `filed` (the Undo row, or None), and `bad` for a folder that is refused."
        kind, _, v = i.partition(':')
        try: name, ds = file_chip(i, st)
        except Exception as e:   # one source that fails never stops the walk
            log.warning('abhyasa could not file the source %r: %r', i, e)
            why = f' {e}' if isinstance(e, LinkError) and not str(e).startswith('abhyasa could not') else ''
            return AttrDict(notes=[(f'abhyasa could not clone {v}.' if kind == 'gh' else f'abhyasa could not file {Path(v).name or v}.') + why],
                            bad=kind in ('folder', 'repo'))   # a refused folder never reaches the plan or the agent
        added = getattr(ds, 'added', None)
        return AttrDict(name=name, docs=ds, notes=[f'{name}: {cut}'] if (cut := getattr(ds, 'cut', '')) else [],
                        filed=dict(root=name, docs=[dict(x) for x in added], at=time.time(), notebooks=sum(str(x.url).endswith('.ipynb') for x in added)) if added else None)

    def still(i): return f"abhyasa is still filing {i.partition(':')[2].rstrip('/').split('/')[-1]}. The walk uses it when it is filed."

    def joined(jid, i, fut):
        "On the filer, when the chip `i` is filed after its walk `jid` was made: it joins the chips of the walk, with its count, its Undo and its notes."
        try: o = fut.result()
        except Exception as e: o = AttrDict(notes=[f'abhyasa could not file {i}.'], bad=True); log.warning('abhyasa could not file %r: %r', i, e)
        join(jid, i, o)

    def join(jid, i, o):
        "The chip `i` that `file_one` filed as `o` joins walk `jid`."
        with _jlock(jid):
            if not (j := lr.journey(jid)): return
            chips = [x for x in j.get('chips') or () if not (o.get('bad') and x == i)]
            if not o.get('bad') and i not in chips: chips.append(i)
            lr.put_journey({**j, 'chips': chips, 'filing': [x for x in j.get('filing') or () if x != i],
                            'chip_counts': {**(j.get('chip_counts') or {}), **({i: len(o.docs)} if 'docs' in o else {})},
                            'filed': [*(j.get('filed') or ()), *([o.filed] if o.get('filed') else [])],
                            'notes': [n for n in j.get('notes') or () if n != still(i)] + o.notes})

    @hook('walk_add_sources')
    def add_sources(jid, ids):
        "File the chips `ids` for the walk `jid` that it does not have, each on its own job. Each one joins the walk when it is filed. Gives the ids that it started."
        with _jlock(jid):
            if not (j := lr.journey(jid)): return []
            new = [i for i in dict.fromkeys(ids) if i and i not in (j.get('chips') or ()) and i not in (j.get('filing') or ())]
            if new: lr.put_journey({**j, 'filing': [*(j.get('filing') or ()), *new]})
        for i in new: filer.submit(file_one, i, AttrDict(said='')).add_done_callback(lambda f, i=i: joined(jid, i, f))
        return new

    def mine(paths, notes):
        "Your data folders `paths` as rows; a folder that abhyasa cannot use adds its line to `notes`."
        rows = []
        for p in paths:
            try: rows = keep_data(rows, p)
            except ValueError as e: notes.append(f'{Path(p).name}: {e}')
        return rows

    def from_goal(goal, ids, st, subject='', data=()):
        """On the pool: file each chip that is not in the vault, each on its own job, then plan the walk to `goal` (or, with no goal, walk
        through the docs). A goal waits at most `FILE_WAIT` seconds: a source that is still filing joins the walk when it is filed. Return the walk id."""
        filed, notes, docs, names, counts = st.setdefault('filed', []), [], L(), [], {}   # `st.filed`: the Undo still works when the walk fails
        jobs = {i: filer.submit(file_one, i, st) for i in dict.fromkeys(ids)}
        wait_all(jobs.values(), timeout=FILE_WAIT if goal else None)
        late = [i for i, f in jobs.items() if not f.done()]
        for i in late: jobs[i].add_done_callback(lambda f: (o := f.result()).get('filed') and filed.append(o.filed))   # its Undo, also when the walk fails
        for i, f in jobs.items():
            if i in late: notes.append(still(i)); continue
            o = f.result(); notes += o.notes
            if o.get('bad'): ids = [x for x in ids if x != i]
            if 'docs' not in o: continue
            docs += o.docs; names.append(o.name); counts[i] = len(o.docs)
            if o.filed: filed.append(o.filed)
        st.update(said='Planning the walk')
        rows = mine(data, notes)
        if goal: j = walk_from_topic(lr, ask, goal, profile_text(lr.profile()), ctx.sources, False, chips=ids, data=rows)   # the plan sees the documents of the chips and your data
        elif docs:
            n = val('links.pages')
            j = journey_from_sources(lr, ask, docs[:n], title=' and '.join(names), subject=subject,
                                     progress=lambda k, m: st.update(said=f"Reading {k + 1} of {n_of(m, 'document')}"))
        else: raise LinkError(' '.join(notes) or 'abhyasa found no text to read in these sources.')
        run_hook('concepts_added')
        if not j.steps:
            lr.drop_journey(j.id)
            raise LinkError('The tutor found no steps for this goal.' if goal else 'The tutor found no ideas in these sources.')
        j = lr.merge_journey(j.id, filed=filed, notes=notes, chips=list(ids), chip_counts=counts, filing=late, **({'data': rows} if rows else {}))
        for i in late: jobs[i].add_done_callback(lambda f, i=i: joined(j.id, i, f))   # it can be done now: then it joins at once
        if goal:
            run_hook('goal_walk', j)   # the course block joins the walk to the course of its goal
            if want_agent(j): ctx.research.gather(j.id); write_notebooks(j)   # a big goal: the agent gathers the sources (D6)
            else: research_new(j)
            if val('research.on') and not val('research.told'): set_val('research.told', True)
        return j.id

    def goal_walk(goal, ids, subject='', data=()):
        "Start the pool job that files the chips `ids` and makes the walk with your `data` folders, unless one is running. The request does not wait."
        key = 'goal:' + hashlib.sha1(json.dumps([goal, ids, list(data)]).encode()).hexdigest()[:12]
        st = links.get(key)
        if not st or st.job.done():
            st = links[key] = AttrDict(said='Planning the walk')
            st.job = ctx.pool.submit(from_goal, goal, ids, st, subject, data)
        return ui.LinkPending(key, st.said)

    def data_drop(jid:str, path:str=''):
        "Remove one data folder: from the course of the walk and each of its walks, else from the walk. The folder stays on the disk."
        if not (j := walk_of(jid)): return Response(status_code=404)
        if (c := course_of(lr, jid)): drop_data(lr, c.id, path)
        else: lr.merge_journey(jid, data=[d for d in j.get('data') or () if d['path'] != path])
        return ui.YourData(lr.journey(jid))

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
            q:str='', pick:str='', file:str='', opts:str='', doc:str='', sources:list[str]=None, chips:str='', mine:list[str]=None):
        if (q.strip() or chips) and not any(x.strip() for x in (ref, text, topic, url)):   # the Start box: its reading says which field it is
            t = vault_title(lr.vault, q) if not file else None
            r = detect(q, dict([t]) if t else {}, research=val('research.on'), file=file, pick=pick, doc=doc, roots_in_vault=vault_roots(lr))   # `ref` is a document id
            ids = [x for x in (sources or []) if x] if chips else r.send.get('sources', [])   # the chips that the box showed, less the ones that you removed
            goal = r.kind == 'goal' or (chips and r.kind == 'topic')   # a topic with sources that you added is a goal
            if (goal or r.kind in ('sources', 'folder')) and (r.send or chips):
                ours = [x for x in ids if x in (mine or ()) and x.startswith('folder:')]   # the folders that you ticked as your data: not filed
                ids = [x for x in ids if x not in ours]
                if not goal and not ids: return P('Add a source first.', cls='req-err')
                return goal_walk(q.strip() if goal else '', ids, clean_subject(subject), [x.partition(':')[2] for x in ours])
            if chips and not q.strip(): return P('Write your goal first.', cls='req-err')
            if not r.send: return P(r.line if r.kind != 'ask' else 'Pick one answer first.', cls='req-err')
            ref, text, topic, url = (r.send.get(k, '') for k in ('ref', 'text', 'topic', 'url'))
            title = title or r.send.get('title', '')
            if not opts: tool = tool or r.send.get('tool', '')   # the options of the box were not shown: the reading picks
        tool, ref, shelf, subject = tool == 'on', ref.strip(), shelf.strip() or 'store', clean_subject(subject)
        if url.strip(): return link_walk(url.strip(), pages, tool, subject)
        if (u := as_link(ref)): return Div(P(AS_LINK, cls='mute'), link_walk(u, '', tool, subject))   # a link in the vault document field
        try:
            if ref and ((sh := lr.doc_shelf(shelf)) is None or sh.doc(ref) is None):
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

    def ended(j, b):
        "The end of walk `j`, for its page: what moved in each sitting, the side walks, the first review, what other blocks add, and what you made in Leela."
        back = leela_back(lr, j)
        sid = j.get('sitting')
        live_ = sessions.get(sid) if sid else None
        logs = [x.get('log') or [] for x in sorted(lr.sessions(limit=None, journey=j.id), key=lambda x: x.get('start') or 0) if not (live_ and x.get('id') == sid)]
        rows = [r for log in logs for r in log] + (live_.log if live_ else [])   # the whole walk: every sitting, in order
        sides = [((b.get(d['slug']) or {}).get('name', d['slug']), d.get('outcome') in ('solid', 'fragile')) for st in j.steps for d in st.get('detours') or ()]
        now, slugs = time.time(), {st['slug'] for st in j.steps if (st.get('done') or {}).get('outcome') not in (None, 'skipped')}
        due = min((c.due for k in slugs if (c := b.get(k)) and c.get('due') and c.due > now), default=None)
        k = max((k for k, x in back.items() if x.run and x.run.get('images')), default=None)   # the last step with images: what you made
        return ui.WalkEnd(j, walk_state(j, b), moved(rows), b, sides, due, run_hook('walk_end', j), made=ui.WhatYouMade(j, k, back[k]) if k is not None else '')

    def one(jid:str, plan:str='', open:str='', pick:str=''):
        """The walk page, in the state of the walk: new, going, finished, a side walk, or empty. The plan changes in place (`open` opens the row of one idea,
        and `pick` its passage picker). `?plan=1` was the build view: it goes to the sources."""
        if plan: return RedirectResponse(ui.walk_url(jid, 'sources'), status_code=301)
        if not (j := walk_of(jid)): return missing()
        leela_back(lr, j)   # a step that Leela checked is done, so the walk goes on from the next one
        j, b = lr.journey(jid), by()
        st = walk_state(j, b)   # an idea learned elsewhere is known
        seen(j)
        ph = ui.phase(j, st)
        top = ended(j, b) if ph == 'finished' else Div(ui.SideTop(j, st, back_to(j)), *(run_hook('walk_end', j) if st.current is None else ())) if ph == 'side' else None   # a side walk that ends says what you learned on the way
        ts = talks_of(jid)
        plan_ = ui.PlanPart(j, b, open, bool(pick)) if j.steps and not for_talk(j) else ''
        page = ui.WalkPage(j, st, b, plan_, band(j, plan=True), top=top, more=run_hook('walk_plan_more', j), talks=ts,
                           changed={t['id'] for t in ts if any(walk_changes(lr, t).values())}, actions=run_hook('walk_actions', j, quiet=True), vault=vault)
        return Page(j.title, *page, on='Home', crumbs=up, extra=(*edit_assets(), *ui.assets()), wide=True)

    def start(jid:str):
        if not (j := walk_of(jid)): return missing()
        with _jlock(jid):   # read and write under the lock of the walk, so a source that research writes now stays
            if not (j := lr.journey(jid)).get('started'): j = lr.put_journey({**j, 'started': time.time(), 'steps': [{**RUN, **s} for s in j.steps]})
        sitting(j)
        return go(jid, walk_state(lr.journey(jid), by()).current or 0)

    def step(jid:str, i:int):
        if not (j := walk_of(jid, i)): return missing()
        if not for_talk(j):   # a side walk of a talk is for the room: it keeps no read time and starts no demo
            if not j.steps[i].get('read_at'): j = put(j, i, read_at=time.time())
            if (h := j.get('here') or {}).get('step') != i or time.time() - (h.get('at') or 0) > 60: j = lr.merge_journey(jid, here=dict(step=i, at=time.time()))   # the idea that you are on, for Continue
            ahead(j, i + 1)
        back = leela_back(lr, j)
        j, b = lr.journey(jid), by()
        seen(j)
        line = [band(j)] if ctx.research.running(jid) or j.get('research_start') or j.get('gather_at') else []   # the line of research is on each step
        page = ui.StepPage(j, walk_state(j, b), b, i, needs=[*line, *run_hook('step_needs', j, i, b.get(j.steps[i]['slug']))], back=back_to(j), vault=vault,
                       present=run_hook('walk_actions', j, quiet=True), looking=looking(jid, i), result=None if for_talk(j) else from_leela(j, i, back))
        return Page(ui.name(b, j.steps[i]), page, wide=True, extra=ui.assets(),
                    on='Home', crumbs=[*up, (j.title, ui.at(Routes.one, jid))])

    def note(jid:str, i:int):
        "The tutor note of step `i`, loaded after the page; a failed note shows nothing."
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        try:
            with held(jid, i): return ui.Note(tutor_note(lr, ctx.ask, j, i, ctx.sources))
        except Exception as e: log.warning('the tutor could not write the note of %s step %s: %r', jid, i, e); return ''

    def source(jid:str, i:int, quiet:str=''):
        """The passage of step `i` as it is now. When a web source came, the note loads again, so it explains the passage. A GET only reads.
        `quiet`: the page asks while the learner reads, so a source that came shows only `A source is ready — show it`."""
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        s = j.steps[i]
        out = ui.Passage(j, s, by().get(s['slug']), i, looking(jid, i), quiet=bool(quiet))
        return (out, ui.NoteSlot(jid, i, oob=True)) if (s.get('read') or {}).get('src') == 'web' and not quiet else out

    def find_source(jid:str, i:int):
        "Find a source: look for a web source for step `i` on the pool, also after a search that found nothing. Off in Settings, it does nothing."
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        if val('research.on') and wants_source(j.steps[i]): look_for(jid, [i])
        return source(jid, i)

    def gather_band(jid:str, plan:str=''):
        "The line of research, as it is now. It asks again every 3 s while research runs."
        if not (j := walk_of(jid)): return Response(status_code=404)
        return band(j, bool(plan))

    def gather_log(jid:str):
        "What the gather agent read and filed, newest first, each row with its link. It opens in the side pane."
        if not (j := walk_of(jid)): return missing()
        return Page('What the agent did', *ui.GatherLog(j), on='Home', crumbs=[*up, (j.title, ui.at(Routes.one, jid))], extra=ui.assets())

    def stop_gather(jid:str):
        "Stop the research of the walk: each tool of the agent refuses, its turn and its sub-agents are cancelled, or the search of each idea ends after the one that runs. What it filed stays."
        if not walk_of(jid): return Response(status_code=404)
        ctx.research.stop(jid)
        return band(lr.journey(jid))

    def again(jid:str):
        "Find sources again: look again for each idea with no source, with the agent when the walk wants it, else with the search of each idea."
        if not (j := walk_of(jid)): return Response(status_code=404)
        if val('research.on') and not ctx.research.running(jid):
            ix = [i for i, s in enumerate(j.steps) if wants_source(s)]
            if ix and want_agent(j): ctx.research.gather(jid)
            elif ix: ctx.research.look_for(jid, ix)
        return band(lr.journey(jid))

    def check(jid:str, i:int):
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        if (got := from_leela(j, i)) is not None: return got   # what came back from Leela takes the place of the check
        with held(jid, i):
            j = lr.journey(jid)
            if j.steps[i]['check']['kind'] == 'notebook': return card(j, i)   # it runs in Leela: abhyasa opens no question on it
            if not j.steps[i].get('done') and j.steps[i]['check']['kind'] in AIM and not demo(j.steps[i]):
                if (wait := no_demo(j, i)): return wait
                j = lr.journey(jid)
            if not j.steps[i].get('done') and j.steps[i]['check']['kind'] not in AIM and j.steps[i].get('qid') not in tutor.open:
                s = sitting(j)
                try: s.q = open_short(tutor, j, i, s.id)
                except Exception as e:
                    log.warning('the tutor could not write the check of %s step %s: %r', jid, i, e)
                    return Div(P('The tutor could not write the check.', cls='req-err'),
                               Button('Try again', hx_get=ui.at(Routes.check, jid, i), hx_target='closest div', hx_swap='outerHTML'))
                s.save()
        return card(lr.journey(jid), i)

    def nb_again(jid:str, i:int):
        "Try again to write the notebook spec of step `i`, after the tutor could not."
        if not (j := walk_of(jid, i)) or j.steps[i]['check']['kind'] != 'notebook': return Response(status_code=404)
        if j.steps[i].get('nb_why'): j = put(j, i, nb_why='')
        return card(j, i)

    def open_leela(jid:str, i:int):
        "Open in Leela: note the time on step `i` (`leela_at`), then go to the Leela link. When Leela does not run, go back to the step."
        with _jlock(jid):   # one read of the walk: the link, the concept opened at this place and the stamp all name the same idea
            if not (j := walk_of(jid, i)): return Response(status_code=404)
            if not (link := leela_link(j, i, vault=vault)): return RedirectResponse(ui.at(Routes.step, jid, i), status_code=303)
            j = with_folders(j, i)
            slug = j.steps[i]['slug']   # an older Leela lesson files no concept, so its results match only while the step at this place has it
            lr.put_journey({**j, 'leela_opened': {**(j.get('leela_opened') or {}), str(i): slug}})
            lr.walk_slug(jid, slug, leela_at=time.time())
        return RedirectResponse(link, status_code=303)

    def failed(what, jid, i, e):
        "A call to the model that failed: the log gets the error, and the page a plain line. A 503 keeps the answer in its box."
        log.warning('the tutor could not %s on %s step %s: %r', what, jid, i, e)
        return Response(f'The tutor could not {what}. Try again.', status_code=503, media_type='text/plain')

    def answer(jid:str, i:int, answer:str='', thinking:str='', confidence:int=None):
        j, s = live(jid, i)
        if not s: return no_check(j, i)
        if (words := show_ask(answer)) is not None:   # "show me …" opens a demo under the title (the demo block); it uses no try
            return card(j, i), *run_hook('show_me', words, dict(where='walk', concept=j.steps[i]['slug'], walk=jid, step=i))
        try: r = s.answer(answer, thinking, confidence)
        except KeyError as e:
            if s.q.id in tutor.open: return failed('grade your answer', jid, i, e)
            return no_check(lr.journey(jid), i)   # another request closed it while this one waited
        except Exception as e: return failed('grade your answer', jid, i, e)
        return closed(j, i, r) if r.done else card(j, i)

    def hint(jid:str, i:int):
        j, s = live(jid, i)
        if not s: return no_check(j, i)
        try:
            if len(tutor.open[s.q.id].hints) < len(HINTS): s.hint()
        except KeyError as e:
            if s.q.id in tutor.open: return failed('give a hint', jid, i, e)
            return no_check(lr.journey(jid), i)
        except Exception as e: return failed('give a hint', jid, i, e)
        return card(j, i)

    @hook('guide_board')
    def board_hint(page, board):
        "A board of the screen guide about the open check of a walk step (`board.hint`, from `guide.on_check`) counts as one hint on that check. The line that the check shows, or None."
        m = re.fullmatch(r'/w/([^/]+)/(\d+)', str(page or ''))
        if not m or not board.get('steps') or not board.get('hint'): return None
        j, s = live(m[1], int(m[2]))
        if not s: return None
        try: n = tutor.board_hint(s.q.id, ' '.join(x['say'] for x in board['steps']))
        except KeyError: return None   # another request closed the check
        if n is None: return None
        s.save()
        return f'Hint {n} of {len(HINTS)} used (from the board).'

    def giveup(jid:str, i:int, confidence:int=None):
        j, s = live(jid, i)
        if not s: return no_check(j, i)
        try: r = s.give_up(confidence=confidence or 0) if tutor.open[s.q.id].tries else s.answer(dont_know=True, confidence=confidence)
        except KeyError as e:
            if s.q.id in tutor.open: return failed('close the check', jid, i, e)
            return no_check(lr.journey(jid), i)
        except Exception as e: return failed('close the check', jid, i, e)
        return closed(j, i, r)

    def lesson_job(jid, i, slug):
        "Start the pool job that writes the lesson in another way of step `i`, unless it runs. The job keeps the lesson on the step."
        k = f'{slug}:lesson'
        if (jb := tutor.jobs.get(k)) is not None and not jb.done(): return
        ld = lr.journey(jid).steps[i]['ladder']
        a = first(x for x in lr.attempts(slug) if x.id == ld.get('aid'))
        def job():
            if not (text := demo_lesson(tutor, a, ld['way'])) or isinstance(text, NoLesson): return   # an empty lesson or the fallback note is a failure
            with writing[jid, slug]:   # by its concept: the step can move while the lesson is written
                st = first(x for x in (lr.journey(jid) or {}).get('steps') or () if x['slug'] == slug)
                if st is not None: lr.walk_slug(jid, slug, ladder={**(st.get('ladder') or {}), 'lesson': text})
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
        with held(jid, i): put(lr.journey(jid), i, ladder=ld)
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
            with held(jid, i): put(j, i, ladder=(ld := dict(rung=2, asked=True)))
        if simpler and not ld.get('asked'):
            with held(jid, i): put(j, i, ladder={**lr.journey(jid).steps[i]['ladder'], 'asked': True})
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
        if first(a for a in lr.attempts(s['slug']) if of_step(a, jid, i, s['slug']) and (a.get('demo'), a.get('gate')) == (slug, gate)):
            return JSONResponse(dict(ok=True, again=True))   # one record for each gate of each demo: a second try comes after the answer showed
        st, floor0 = sitting(j), lr.concept(s['slug']).get('floor') or 0
        a = lr.record_prediction(slug, gate, picked, ans, ok == 'true', why, context, st.id, confidence,
                                 kind=s['check']['kind'], method=s['check']['way'], **step_meta(j, i))
        st.noted(a, floor0)
        with held(jid, i):
            if not lr.journey(jid).steps[i].get('done'): put(j, i, done=dict(outcome=a.outcome, aid=a.id, at=time.time()))
        ws, help_ = walk_state(lr.journey(jid), by()), climb(jid, i, a)
        # walk.js fills the dot, moves the progress line, and loads the help under the card when there is a `ladder`
        return JSONResponse(dict(ok=True, dot=ws.steps[i].dot, done=ws.done, total=ws.total, **({'ladder': help_} if help_ else {})))

    def keep(jid:str, i:int, state:str=''):
        "Keep the state of the demo on the newest prediction of step `i`."
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        try: kept = json.loads(state) if len(state) <= MAX_STATE else None
        except ValueError: kept = None
        if kept is None: return Response('The state is not valid.', status_code=400)
        a = first(a for a in lr.attempts(j.steps[i]['slug']) if of_step(a, jid, i, j.steps[i]['slug']) and a.get('demo'))
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
            put(j, i, done=dict(outcome='skipped', at=time.time()))
        ends = any(ix[-1] == i for _, ix in st.sections)
        if ends and (sid := j.get('sitting')) and (s := sessions.pop(sid, None) or Session.load(tutor, sid)) and not s.ended:
            s.end()   # the section ends here, on the POST, not on the GET of its summary
        last = i + 1 >= len(j.steps)
        # a plain 303, not HX-Redirect: htmx follows it and swaps the page in place, so the next idea comes in with a view transition
        return RedirectResponse(ui.at(Routes.one, jid) if last else ui.at(Routes.done, jid, i) if ends else ui.at(Routes.step, jid, i + 1), status_code=303)

    def done(jid:str, i:int):
        "The summary of the section of step `i`. It changes nothing: Next idea ended the sitting, and the next step opens a new one. After the last idea, the walk page has the end."
        if not (j := walk_of(jid, i)): return missing()
        sec, ix = next((sec, ix) for sec, ix in walk_state(j).sections if i in ix)
        if ix[-1] + 1 >= len(j.steps): return RedirectResponse(ui.at(Routes.one, jid), status_code=303)
        slugs = {j.steps[k]['slug'] for k in ix}
        s = (sessions.get(sid) or Session.load(tutor, sid)) if (sid := j.get('sitting')) else None
        rows = [r for r in (s.log if s else ()) if r['concept'] in slugs]
        return Page('Section done', *ui.SectionDone(j, sec, ix, moved(rows), ix[-1] + 1, by()), on='Home', crumbs=[*up, (j.title, ui.at(Routes.one, jid))], extra=ui.assets())

    def img(jid:str, i:int):
        "The figure of step `i`, only from inside the vault assets and only as an image file."
        if not (j := walk_of(jid, i)) or not (f := (j.steps[i].get('read') or {}).get('figure')): return Response(status_code=404)
        root = Path(lr.vault.assets()).resolve()
        p = (root/f).resolve()
        if not p.is_relative_to(root) or p.suffix.lower() not in FIGURES or not p.is_file(): return Response(status_code=404)
        return FileResponse(p)

    def result(jid:str, i:int, n:str):
        """One image of a run that Leela filed for step `i`: only `<assets>/leela/<jid>/<k>/<n>.png` (`k` is the place of the step when Leela
        ran it, which a move can change), `n` one digit, listed by the run of the step that `run_ok` accepts, and a PNG file of at most `MAX_RESULT` bytes."""
        if not re.fullmatch(r'[0-9]', n) or not (j := walk_of(jid, i)): return Response(status_code=404)
        run = (leela_found(lr, j).get(i) or AttrDict(run=None)).run
        k = run.get('step') if run else None
        if type(k) is not int or f'leela/{jid}/{k}/{n}.png' not in run.get('images', []): return Response(status_code=404)
        root = (Path(lr.vault.assets())/'leela').resolve()
        p = (root/jid/str(k)/f'{n}.png').resolve()
        try:
            ok = p.is_relative_to(root) and p.is_file() and p.stat().st_size <= MAX_RESULT
            if ok:
                with p.open('rb') as f: ok = f.read(8) == PNG
        except OSError: ok = False
        if not ok: return Response(status_code=404)
        return FileResponse(p, media_type='image/png', headers={'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': "default-src 'none'"})

    # --- the walk path editor: each change saves at once with an Undo (core/edit.py); steps are found by their concept -------

    def talks_of(jid): return [t for t in lr.talks() if (t.get('src') or {}).get('walk') == jid]

    def not_walk(jid):
        "None for a walk of yours, else the page that says there is no such walk (a side walk of a talk is for the room)."
        j = walk_of(jid)
        return None if j and not for_talk(j) else missing()

    def old_path(req, jid:str):
        "An old link to a path (`/path/{jid}`, `/j/{jid}`), from a page, Leela or a vault document: the path becomes a walk, then the walk page opens, with the same query."
        if (j := lr.journey(jid)): walk_path(lr, j, ctx.sources)
        return RedirectResponse(ui.at(Routes.one, jid) + (f'?{q}' if (q := req.url.query) else ''), status_code=301)

    @hook('today_top')
    def paths(subject=None):
        "Before Home lists your walks: each old path becomes a topic walk, one time. Nothing on the page."
        try: walk_paths(lr, ctx.sources)
        except Exception as e: log.warning('abhyasa could not make the old paths walks: %r', e)
        return None

    def attach(jid:str, slug:str):
        "Add a concept to a walk, from its concept page."
        if not (j := walk_of(jid)) or for_talk(j) or not lr.concept(slug): return P('No such walk or concept.', cls='mute')
        j = lr.journey_add(jid, slug, why='you added it')
        return P('Added to ', A(j.title, href=ui.at(Routes.step, jid, len(j.steps) - 1)), '.', cls='mute')

    @hook('concept_more')
    def in_walks(c):
        "On a concept page: the walks that have this idea, and a way to add it to another walk."
        rows, js = walks_of(c.slug), [j for j in lr.journeys() if j.get('mode') == 'walk' and not for_talk(j) and not j.get('depth')]
        return ui.InWalks(c, rows, js) if rows or js else None

    @hook('lesson_extra')
    def step_done(r):
        "A note in a session of a walk when the close makes one of its ideas learned."
        if not (r.get('correct') and r.get('floor', 0) >= val('checks.goal') and r.get('depth') == r.get('floor')): return None
        s = lr.session(r.get('session') or '') if r.get('session') else None
        if not (s and s.get('journey') and (j := walk_of(s.journey))) or r.concept not in [x['slug'] for x in j.steps]: return None
        b = by(); i = walk_state(j, b).current
        return ui.StepDone(lr.concept(r.concept), ui.name(b, j.steps[i]) if i is not None else '')

    def editor(req, jid:str):
        "The old page Change the walk: the plan is on the walk page now."
        return RedirectResponse(ui.at(Routes.one, jid) + (f'?{q}' if (q := req.url.query) else '') + '#plan', status_code=301)

    def bar(j, said, rows, row=''):
        "The Undo bar after a change: what changed, and Undo for the newest change."
        return UndoBar(said, ui.at(Routes.undo, j.id), ui.walk_url(j.id, 'history'), step=rows[0].id if rows else '', row=row,
                       hx_target='#steps', hx_swap='outerHTML')

    def view(j, opened='', fresh=''): return ui.Steps(j, by(), opened=opened, fresh=fresh), ui.Hands(j, oob=True)

    def new_check(j, s, way):
        "The check of step `s` for the choice `way`: a kind of the editor (short, predict, order, code, notebook) or a way of the walk. The question that you wrote stays (the change adds it)."
        old, tool = s.get('check') or {}, bool(j.get('tool'))
        if way == 'short': w, kind = (old.get('way') if old.get('way') in TEXT_WAYS and old.get('way') != 'code' else 'words'), 'short'
        elif way in ui.CHOICE_OF: w, kind = ui.CHOICE_OF[way]
        elif way in (TOOL_WAYS if tool else WALK_WAYS): w, kind = way, CHECK_KIND.get(way, 'short')
        else: raise ValueError('Pick a check kind.')
        floor = (lr.concept(s['slug']) or {}).get('floor') or 0
        return {'way': w, 'kind': kind, 'depth': (2 if floor < 2 else 3) if kind == 'short' else DEPTH[kind], 'why': 'you chose it'}

    def queue_new(j, old):
        "After an idea came in: look for a web source for each new step with no passage, and write the notebook of each new notebook step."
        new = [i for i, s in enumerate(j.steps) if s['slug'] not in old]
        if val('research.on') and (ix := [i for i in new if wants_source(j.steps[i])]): look_for(j.id, ix)
        for i in new:
            if j.steps[i]['check']['kind'] == 'notebook': write_notebook(j.id, i)
        return j.steps[new[0]]['slug'] if new else ''

    async def edit(req, jid:str):
        "One change to the path of walk `jid`. The step is named by `slug` (its concept), never by its place."
        form = await req.form()
        f = {k: CTRL.sub('', v) for k, v in {**dict(req.query_params), **{k: v for k, v in form.items() if isinstance(v, str)}}.items()}
        if not (j := walk_of(jid)) or for_talk(j): return Response('No such walk.', status_code=404)
        act, slug, live = f.get('act', ''), f.get('slug', ''), f.get('act') == 'set'
        if live: act = 'note' if 'note' in f else 'q' if 'q' in f else ''
        if act not in EDIT_ACTS: return bad(f'Unknown change: {act}.')
        slugs, b = [s['slug'] for s in j.steps], by()
        if act != 'add' and slug not in slugs: return Response('This idea is not in the walk now.', status_code=404)
        if act == 'rewrite': return redo(j, slug, f)
        k = slugs.index(slug) if slug in slugs else None
        nm = lambda x: ui.name(b, dict(slug=x))
        text = (f.get(act, '') if live else f.get('text', '')).strip()
        field, opened, row, fresh = None, '', slug, ''
        try:
            if act == 'move':
                to = place(f.get('to', ''), len(slugs))
                op, said = (lambda ss: move_step(ss, slug, to)), f'Moved “{nm(slug)}” to idea {to + 1}.'
            elif act in ('skip', 'back'):
                op, said = (lambda ss: skip_step(ss, slug, act == 'skip')), f"{'Skipped' if act == 'skip' else 'Brought back'} “{nm(slug)}”."
            elif act == 'remove':
                op, said = (lambda ss: remove_step(ss, slug)), f'Removed “{nm(slug)}”.'
            elif act == 'merge':
                if k + 1 >= len(slugs): raise ValueError('This is the last idea. It has no next idea to merge with.')
                op, said, opened = (lambda ss: merge_steps(ss, slug)), f'Merged “{nm(slug)}” and “{nm(slugs[k + 1])}”.', slug
            elif act == 'note':
                if len(text) > NOTE_MOST: raise ValueError(f'Write the note in at most {NOTE_MOST} characters.')
                op, said, field = on_step(slug, lambda s: s.update(note=text or None)), f'Changed the note of idea {k + 1}.', f'{slug}/note'
            elif act == 'q':
                if (j.steps[k].get('check') or {}).get('kind', 'short') != 'short': raise ValueError('Only a short-answer check asks a question that you write.')
                if len(text) > Q_MOST: raise ValueError(f'Write the check question in at most {Q_MOST} characters.')
                def setq(s):
                    ck = {x: v for x, v in (s.get('check') or {}).items() if x != 'q'}
                    s['check'] = {**ck, **({'q': text} if text else {})}
                op, said, field = on_step(slug, setq), f'Changed the check question of idea {k + 1}.', f'{slug}/q'
            elif act == 'check':
                ck = new_check(j, j.steps[k], f.get('way', ''))
                op, said, opened = on_step(slug, lambda s: s.update(check={**ck, **({'q': s['check']['q']} if (s.get('check') or {}).get('q') else {})})), f"Changed the check of “{nm(slug)}” to {ui.SAY_KIND[ck['kind']]}.", slug
            elif act == 'pick':
                read = pick_read(lr, j, k, text, sources=ctx.sources)
                op, said, opened = on_step(slug, lambda s: s.update(read=read)), f'Changed the passage of idea {k + 1}.', slug
            if act in ('add', 'split'):
                old = set(slugs)
                try:
                    if act == 'add':
                        at = slugs.index(f['after']) + 1 if f.get('after') in slugs else len(slugs)
                        name, concept = f.get('name', '').strip(), f.get('concept', '').strip()
                        if len(name) > NAME_MOST: raise ValueError(f'Write the name of the idea in at most {NAME_MOST} characters.')
                        read = pick_read(lr, j, None, text, name=name or nm(concept), sources=ctx.sources) if text else None
                        j2 = add_step(lr, ask, jid, at, name=name, slug=concept, read=read, sources=ctx.sources)
                    else: j2 = split_step(lr, ask, jid, slug, ctx.sources)
                except (ValueError, KeyError): raise
                except Exception as e:   # never the words of a library
                    log.warning('the tutor could not %s an idea: %r', act, e)
                    return bad(NO_ADD if act == 'add' else NO_SPLIT)
                run_hook('concepts_added')   # the concepts block places a new concept
                rows, got = lr.edits('walk', jid), queue_new(j2, old)
                if act == 'add': return (*view(j2, opened=got, fresh=got), bar(j2, rows[0].what, rows, got))
                return (*view(j2), bar(j2, rows[0].what, rows, slug))
            j2, rows = edit_walk(lr, jid, op, said, field=field)
        except KeyError as e: return Response(str(e.args[0] if e.args else 'Not found.'), status_code=404)
        except ValueError as e: return bad(str(e))
        if rows is None: return Response(status_code=204) if live else view(j2, opened=opened)
        if act == 'check' and j2.steps[k2 := [s['slug'] for s in j2.steps].index(slug)]['check']['kind'] == 'notebook': write_notebook(jid, k2)
        if live: return bar(j2, said, rows, row)   # a live field: the text that you type stays, and only the bar changes
        return (*view(j2, opened=opened), bar(j2, said, rows, row))

    def redo(j, slug, f):
        "Rewrite the note and the check question of a step with a short instruction. The model call runs outside the lock; a failed rewrite changes nothing."
        ins = ' '.join((f.get('chip') or f.get('text') or '').split()).rstrip('.')
        if not ins: return bad('Tell the tutor what to change.')
        k = [s['slug'] for s in j.steps].index(slug)
        if not j.steps[k].get('note'):   # the note that the step would show: written now (outside the lock), and kept with its own Undo
            try: n = tutor_note(lr, ctx.ask, j, k, ctx.sources, save=False)
            except Exception: n = ''
            if n:
                def first_note(t):
                    if not t.get('note'): t['note'] = n
                try: j = edit_walk(lr, j.id, on_step(slug, first_note), f'The tutor wrote the note of idea {k + 1}.', who='tutor')[0]
                except (KeyError, ValueError): return bad(NO_REWRITE)
                k = [s['slug'] for s in j.steps].index(slug)
        s = j.steps[k]
        short = (s.get('check') or {}).get('kind', 'short') == 'short'   # only a short-answer check asks a question that you can write
        was = dict(note=s.get('note') or '', q=(s.get('check') or {}).get('q') or '' if short else '')
        fields = {x: v for x, v in was.items() if v.strip()}
        if not fields: return bad('Write a note or a check question first.')
        try: new = tutor_rewrite(ask, fields, ins, context=(s.get('read') or {}).get('text') or '')
        except Exception: return bad(NO_REWRITE)   # never the words of a library
        kept = []
        def apply(t):
            now = dict(note=t.get('note') or '', q=(t.get('check') or {}).get('q') or '')
            kept[:] = [x for x in fields if now[x] != was[x]]
            if len(kept) == len(fields): raise Kept()
            if 'note' in fields and 'note' not in kept: t['note'] = new['note']
            if 'q' in fields and 'q' not in kept: t['check'] = {**t['check'], 'q': new['q']}
        names = ' and the '.join(ui.FIELDS[x] for x in fields)
        said = lambda old, now: f'Rewrote the {names} of idea {k + 1}: {ins}.' + (f' Your edit of the {ui.FIELDS[kept[0]]} was kept.' if kept else '')
        try: j2, rows = edit_walk(lr, j.id, on_step(slug, apply), said, who='tutor')   # on the step as it is now: a field that you changed keeps your edit
        except Kept: return bad(KEPT)
        except KeyError: return Response('This idea is not in the walk now.', status_code=404)
        except ValueError: return bad(NO_REWRITE)
        if rows is None: return view(j2, opened=slug)
        return (*view(j2, opened=slug), bar(j2, rows[0].what, rows, slug))

    def undo_(jid:str, step:str=''):
        "Take back the newest change of the path (`step` is its id, so an old bar does nothing)."
        if not (j := walk_of(jid)) or for_talk(j): return Response('No such walk.', status_code=404)
        try: e, line = undo_walk(lr, jid, step or None)
        except ValueError as x: return bad(str(x))
        j = lr.journey(jid)
        said = f"Undone: {e.what}" + (f' {line}' if line else '') if e else 'Nothing to undo.'
        return (*view(j), bar(j, said, lr.edits('walk', jid)))

    def history(req, jid:str):
        "The earlier versions of the walk: the fold on the walk page loads them; a plain GET goes to that fold."
        if (no := not_walk(jid)): return no
        if not req.headers.get('HX-Request'): return RedirectResponse(ui.walk_url(jid, 'history'), status_code=301)
        return ui.History(lr.journey(jid), lr.edits('walk', jid))

    def restore(jid:str, id:str='', k:str=''):
        "Go back to the version of the path before one change (by its `id`, or by its place `k` in the history, newest first). A restore is a change too."
        if not (j := walk_of(jid)) or for_talk(j): return Response('No such walk.', status_code=404)
        es = lr.edits('walk', jid)
        try: n = int(k) if k.strip().isdecimal() else None
        except ValueError: n = None
        e = first(x for x in es if x.id == id) if id else es[n] if n is not None and n < len(es) else None
        if not e: return Response('No such change.', status_code=404)
        try: restore_walk(lr, jid, e.id)
        except (KeyError, ValueError) as x: return bad(str(x))
        return Response(headers={'HX-Redirect': ui.walk_url(jid, 'plan')})

    def pick_list(jid:str, i:str='', q:str='', name:str=''):
        "The real passages that idea `i` (or a new idea `name`) can pick, with the words `q`. A GET only reads."
        if not (j := walk_of(jid)) or for_talk(j): return Response(status_code=404)
        k = int(i) if i.strip().isdecimal() and int(i) < len(j.steps) else None
        name, q = ' '.join(CTRL.sub('', name).split())[:NAME_MOST], CTRL.sub('', q)[:200]
        if k is None and not name: return P('Write the name of the idea first.', cls='mute')
        ps = real_passages(lr, j, k, q, name=name, sources=ctx.sources)
        return ui.PickList(jid, ps, slug=j.steps[k]['slug'] if k is not None else '', name=name)

    # --- Improve the walk: your words, a proposal of changes with the ops of the editor, and the ones that you keep, with one Undo ---------

    def improve_job(jid, words, st):
        "On the pool: file each link in `words` (it joins the sources of the walk, with its Undo), then ask the tutor for the changes."
        docs = {}
        for u in links_in(words):
            st.update(said=f'Getting the pages from {u}')
            o = file_one(f'link:{u}', st)
            join(jid, f'link:{u}', o)
            if o.get('docs'): docs[u] = [dict(shelf=d.shelf, doc_id=d.doc_id) for d in o.docs]
        st.update(said='The tutor reads what you asked', docs=docs)
        j, b = lr.journey(jid), by()
        return propose(ask, j, {k: c.name for k, c in b.items()}, words, ui.weak_of(j), list(docs))

    def improve(jid:str, words:str=''):
        "Improve the walk: start the job that files the links in `words` and asks the tutor for changes. The answer is the pending line."
        if not (j := walk_of(jid)) or for_talk(j): return Response(status_code=404)
        if not (words := ' '.join(CTRL.sub('', words).split())[:WORDS_MOST]): return P('Write what should change, or pick a chip.', cls='req-err')
        key = f'improve:{jid}:' + hashlib.sha1(words.encode()).hexdigest()[:12]
        if not (st := links.get(key)) or st.job.done():
            st = links[key] = AttrDict(said='The tutor reads what you asked')
            st.job = ctx.pool.submit(improve_job, jid, words, st)
        return ui.ImprovePending(jid, key, st.said)

    def proposal(jid:str, key:str=''):
        "The proposal as it is now: the pending line, the changes to keep or skip, or a plain line when the tutor could not make one. A GET only reads."
        if not key.startswith(f'improve:{jid}:') or not (st := links.get(key)): return P('This proposal is gone. Ask the tutor again.', cls='mute')
        if not st.job.done(): return ui.ImprovePending(jid, key, st.said)
        if (e := st.job.exception()):
            log.warning('the tutor could not propose changes to %s: %r', jid, e)
            return P('The tutor could not propose changes. Try again.', cls='req-err')
        return ui.Proposal(jid, key, st.job.result(), by())

    def said_out(*c): return Div(*c, id='improve-out', aria_live='polite', hx_swap_oob='true')

    async def improve_apply(req, jid:str):
        "Apply the changes that you kept (`c<k>` is keep or skip) as one change with an Undo. The ideas that the changes do not touch keep their progress."
        form = await req.form()
        key = form.get('key', '')
        if not (j := walk_of(jid)) or for_talk(j) or not key.startswith(f'improve:{jid}:') or not (st := links.get(key)) or not st.job.done() or st.job.exception():
            return said_out(P('This proposal is gone. Ask the tutor again.', cls='mute')), HttpHeader('HX-Reswap', 'none')
        kept = [c for k, c in enumerate(st.job.result()) if form.get(f'c{k}', 'keep') == 'keep']
        if not kept: return said_out(P('You skipped each change. Nothing changed.', cls='mute')), HttpHeader('HX-Reswap', 'none')
        old = {s['slug'] for s in j.steps}
        try: j2, rows = improve_walk(lr, ask, jid, kept, ctx.sources, st.get('docs'))
        except (KeyError, ValueError) as e: return bad(str(e))
        except Exception as e:   # never the words of a library
            log.warning('the tutor could not improve %s: %r', jid, e)
            return bad('The tutor could not make these changes. Nothing changed.')
        links.pop(key, None)
        if rows is None: return said_out(P('Nothing changed.', cls='mute')), HttpHeader('HX-Reswap', 'none')
        run_hook('concepts_added')
        got = queue_new(j2, old)
        return (*view(j2, fresh=got), bar(j2, rows[0].what, rows), said_out(P(f"Applied {n_of(len(kept), 'change')}. Undo takes them back.", cls='mute')))

    def walks_of(slug):
        "`(walk, index)` for each walk that has a step on concept `slug`."
        return [(j, i) for j, i in with_step(lr, slug) if j.get('mode') == 'walk' and not for_talk(j)]

    @hook('pane_title')
    def pane_title(url):
        "The title of the walk at `url` (`/w/<id>/<step>`) in the side pane; None for another page."
        m = re.match(r'/w/([^/?#]+)/\d+(?:[?#]|$)', url or '')
        return (j := m and walk_of(m.group(1))) and j.title or None

    @hook('concept_actions')
    def open_in(c):
        "The main action of a concept page in a walk: Open it in {walk}, at its idea in the walk that you used last. The walk has its passage."
        if not (rows := walks_of(c.slug)): return None
        j, i = max(rows, key=lambda x: max((x[0].get('here') or {}).get('at') or 0, x[0].get('started') or 0, x[0].get('updated') or 0))
        return ui.Primary(f'Open it in {j.title}', href=ui.at(Routes.step, j.id, i), rank=1, data_act='open-in-walk')

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

    app.get(Routes.gather)(gather_band)   # before the step route `/w/{jid}/{i}`, which would take `gather` as a step
    app.get(Routes.edit)(editor)          # these too: before the step route
    app.post(Routes.edit)(edit)
    app.post(Routes.undo)(undo_)
    app.get(Routes.history)(history)
    app.post(Routes.restore)(restore)
    app.get(Routes.passages)(pick_list)
    app.post(Routes.improve)(improve)
    app.get(Routes.improve)(proposal)
    app.post(Routes.improve_apply)(improve_apply)
    app.get(Routes.gather_log)(gather_log)
    app.post(Routes.gather_stop)(stop_gather)
    app.post(Routes.gather_again)(again)
    app.get(Routes.status)(status); app.router.routes.insert(0, app.router.routes.pop())   # before the static route for `.json`
    app.post(Routes.new)(new)
    app.get(Routes.job)(job)
    app.post(Routes.unfile)(unfile_)
    app.get(Routes.one)(one)
    app.get(Routes.path)(old_path)
    app.get(Routes.old)(old_path)
    app.post(Routes.attach)(attach)
    app.post(Routes.start)(start)
    app.post(Routes.data_drop)(data_drop)
    app.get(Routes.step)(step)
    app.get(Routes.note)(note)
    app.get(Routes.check)(check)
    app.post(Routes.check)(nb_again)
    app.post(Routes.answer)(answer)
    app.post(Routes.hint)(hint)
    app.post(Routes.giveup)(giveup)
    app.post(Routes.predict)(predict)
    app.post(Routes.keep)(keep)
    app.get(Routes.ladder)(ladder)
    app.post(Routes.ladder)(ask_ladder)
    app.post(Routes.next)(next_)
    app.get(Routes.done)(done)
    app.get(Routes.img)(img)
    app.get(Routes.result)(result); app.router.routes.insert(0, app.router.routes.pop())   # before fast_app's static route for `.png`
    app.post(Routes.leela)(open_leela)
    app.get(Routes.leela)(open_leela)   # Abhyasa.app opens the target=_blank form of Open in Leela as a GET
    app.get(Routes.source)(source)
    app.post(Routes.source)(find_source)
