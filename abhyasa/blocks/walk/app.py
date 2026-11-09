"""The guided walk: a paper, a text, a topic or a link as one idea at a time, in reading order. The plan, the step page, its check,
Next idea, and the summary at the end of each section. A sitting is a `Session` that the walk feeds itself."""
import hashlib, json, logging, re, time
from urllib.parse import urlsplit
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, wait as wait_all
from threading import Lock
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import is_local, n_of, Page, NotFound, short_title, hook, run as run_hook, SourceLine, source_of, Md, edit_assets, UndoBar, JobStop
from abhyasa.core.leela import leela_line, leela_link, leela_open, LEELA_INSTALL, LEELA_OFF
from abhyasa.learner import val, set_val, CtxPool
from abhyasa.sources import detect, vault_title, transcript_read
from abhyasa.learner import clean_subject, profile_text, WALK_WAYS, CHECK_KIND, DEPTH, TEXT_WAYS
from abhyasa.tutor import Session, HINTS, public, moved
from abhyasa.sources import file_link, link_kind, LinkError, as_link, is_paper, folder_why, tree_files, unfile, vault_roots
from abhyasa.sources import named_sources, on_disk, title_index
from abhyasa.path import back_from, with_data, keep_data, journey_from_source, journey_from_text, journey_from_sources, walk_from_topic, walk_path, walk_paths, step_read, TOOL_WAYS, short_check, with_step, trail, parent_step, for_talk
from abhyasa.learner import walk_state, _jlock
from abhyasa.path import tutor_note, words_to_know, done_attempt, open_short, step_meta, leela_back, leela_found, course_of, drop_data
import abhyasa.path as walk_engine   # `walk_engine.nb_spec` is read on each call, so a test can put a fake in its place
import abhyasa.show   # adds Learning.talks: the editor links the talks made from a walk
from abhyasa.show import walk_changes
from abhyasa.path import edit_walk, undo_walk, restore_walk, move_step, skip_step, remove_step, CTRL, links_in, propose, improve_walk, lock_step, replan_walk, is_goal_walk
from abhyasa.path import to_research, wants_source, want_agent, research_state, learning_copy, copy_path
from abhyasa.learner import job_start, job_end, track, Said, seen_jobs, check_stop, halted as job_halted, STOPPED, JobStopped
from abhyasa.tutor import NoLesson
from abhyasa.models import Withheld
from abhyasa.show import queue_demo, job_state, job_age, job_key, rung, backed, other_way, demo_lesson, simpler_demo, said, show_ask
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
EMPTY = 'Type an answer first.'
WITHHELD = 'The tutor did not send this. It holds personal data, and your privacy setting blocks it. You can change the setting in Settings.'
FILE_WAIT = 20   # seconds that the plan of a goal waits for its sources; a slower one, such as a big clone, joins the walk when it is filed
FILERS = 3       # the sources that file at the same time, each on its own job, off the pool of the app
FIXING = 'The tutor looks at the ideas that are not locked'   # the pending line when your words ask to fix the rest
WORDS_MOST = 1000   # the most characters of what you ask the box to change
EDIT_ACTS = ('move', 'skip', 'back', 'remove', 'lock', 'unlock')   # the changes by hand: the row keys, Lock and the ⋯ menu. The box makes the others
FIX_WORDS = re.compile(r'\b(fix|redo)\b.*\b(rest|others?|walk|ideas)\b', re.I)   # words that ask the tutor to redo each idea that is not locked (the edit.fix prompt)

def bad(s): return Response(s, status_code=400, media_type='text/plain')

def place(s, n):
    "The index in `s` (digits only, as `isdecimal` reads them) in a list of `n`; else `ValueError`."
    s = str(s).strip()
    try: k = int(s) if s.isdecimal() else -1
    except ValueError: k = -1
    if not 0 <= k < n: raise ValueError('Give a place in the list.')
    return k

log = logging.getLogger(__name__)

def nb_sha(p) -> str:
    "A short hash of the file `p`: abhyasa notes it when it writes a learning copy, so it can tell when you changed the copy."
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]

def nb_head(p, j, back) -> Path:
    "The learning copy `p` of notebook walk `j` with a first cell that says what it is and links `back` to the walk."
    from fastcore.nbio import read_nb, write_nb, mk_cell
    nb, name = read_nb(p), Path(j['notebook']['path']).name
    nb.cells.insert(0, mk_cell(f"**A learning copy of {name}** for the walk *{j['title']}*. It runs in the folder of your notebook. Your notebook does not change.\n\n"
                               f"[Back to the walk ↗](<{back}>)", 'markdown'))
    write_nb(nb, p)
    return p

def copy_cell(p, j, i) -> int|None:
    "The place in the learning copy `p` of the first cell of the section of idea `i` of notebook walk `j`; None when it is not there."
    from fastcore.nbio import read_nb
    k = ((j['steps'][i].get('read') or {}).get('cells') or [None])[0] if i is not None else None
    if not isinstance(k, int): return None
    try: src, cells = read_nb(j['notebook']['path']).cells, read_nb(p).cells
    except (OSError, ValueError): return None
    if not 0 <= k < len(src): return None
    return next((x for x, c in enumerate(cells) if c.cell_type == src[k].cell_type and c.source == src[k].source), None)

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
    def missing(): return NotFound('Walk', H1('No such walk'), P(A('Your walks', href='/')), on='Home', crumbs=up)

    one_name = set()   # the walks whose stored specs have one data name for each folder now

    def walk_of(jid, i=None):
        "The walk `jid`, and step `i` when it is there; None for an unknown walk or step. The first read gives one data name to each folder of its specs."
        if jid not in one_name:
            one_name.add(jid)
            try: lr.join_data_names(jid)
            except Exception as e: log.warning('abhyasa could not join the data names of walk %s: %r', jid, e)
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

    def words(j, i, b=None):
        "The terms of Words to know of step `i`: from its passage, its statement and its check question, when the check is open or closed."
        q, ck = question(j, i), j.steps[i].get('check') or {}
        return words_to_know(lr, ctx.ask, j, i, [x for x in (ck.get('q'), q and q.get('question')) if x], b)

    def main_idea(j, i):
        "The name of the main idea when step `i` is the last idea of side walk `j`: the step of the walk that opened it. Else None."
        if i + 1 < len(j.steps) or not j.get('parent'): return None
        pj, k = parent_step(lr, j)
        return pj and ui.name(by(), pj.steps[k])

    def done_where(a):
        "Where attempt `a` was made, for the done card: the title and the page of its walk (or the walk of its session), else its past session."
        jid = a.get('walk') or (a.get('session') and (lr.session(a.session) or {}).get('journey'))
        if jid and (w := lr.journey(jid)): return short_title(w.title) or w.title, ui.at(Routes.one, jid)
        if a.get('session') and lr.session(a.session): return 'a past session', f"/you/s/{a.session}"
        return '', ''

    def card(j, i):
        "The check card of step `i`; a short-answer card adds what other blocks put after it (`check_after`). The last idea of a side walk goes back to the main idea."
        s = {**j.steps[i], 'main': main_idea(j, i)}
        if s.get('done') and not question(j, i) and (a := done_attempt(lr, j, i)): s.update(did=a, did_where=done_where(a))   # what you did, when the thread is gone
        k = s['check']['kind']
        if k == 'notebook': return nb_card(j, i)
        if k in AIM: return ui.CHECKS[k](j.id, i, s, demo(s))
        q = question(j, i)
        return ui.CHECKS.get(k, ui.Short)(j.id, i, s, q, after=run_hook('check_after', j, i, q) if q else ())

    def back_to(j):
        "The way back from side walk `j` to the step that opened it, and the trail for the side pane; None for a walk with no parent."
        pj, i = parent_step(lr, j)
        if not pj and (j.get('depth') or 0) > 0 and is_local(p := (j.get('parent') or {}).get('page')):   # a side walk from a concept page
            m = re.fullmatch(r'/c/([^/?#]+)', p)
            return AttrDict(href=p, here='its page', trail=[], title=(m and (lr.concept(m[1]) or {}).get('name')) or 'the page')
        if not pj: return None
        parts = [[f"Idea {t.step + 1}", ui.at(Routes.step, t.walk, t.step)] for t in trail(lr, j.id)[:-1] if t.step is not None]
        return AttrDict(href=ui.at(Routes.step, pj.id, i), here=f"idea {i + 1} of {len(pj.steps)}", trail=parts, title=short_title(pj.title))

    def ahead(j, i):
        "Start the demo of step `i` when its check is a demo or an order, it has no outcome, and it has no demo yet (spec 6.5)."
        if not 0 <= i < len(j.steps) or (s := j.steps[i]).get('done') or s['check']['kind'] not in AIM or demo(s): return
        if job_state(tutor, s['slug'], AIM[s['check']['kind']]) == 'stopped': return   # you stopped it: only Make it again starts it
        queue_demo(tutor, s['slug'], aim=AIM[s['check']['kind']], quiet=True)   # the page shows its wait; the chip does not list it

    def no_demo(j, i):
        "The pending card while the demo of step `i` is made; None when the wait is over, so the step uses a short answer."
        s = j.steps[i]
        slug, aim = s['slug'], AIM[s['check']['kind']]
        if job_state(tutor, slug, aim) == 'none': ahead(j, i)
        if job_state(tutor, slug, aim) == 'stopped' or (job_state(tutor, slug, aim) == 'running' and job_age(tutor, slug, aim) < val('walks.demo_wait')):
            return ui.Pending(j.id, i, s, job=job_key(slug, aim), row=lr.job(job_key(slug, aim)))   # Stop while it runs; Make it again after Stop
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

    def researching(jid):
        "Whether the research of walk `jid` runs now, from its job row: the row is the truth for the pages."
        return (r := lr.job(f'walk:{jid}:research')) is not None and r.state == 'running'

    def band(j, plan=False):
        "The line of research of walk `j`, as it is now."
        running = researching(j['id'])
        return ui.GatherBand(j, research_state(j, running), running and halted(j['id']), plan)

    def seen(j):
        "The learner opened walk `j`: each job of the walk that ended is seen, so the activity chip stops showing it."
        seen_jobs(lr, f"walk:{j['id']}")

    nb_jobs, nb_lock = {}, Lock()   # (walk, concept of the step) -> the research pool job that writes the notebook spec of the step

    def nb_writing(jid, i):
        "Whether a job writes the notebook spec of step `i` of walk `jid` now."
        return (f := nb_jobs.get((jid, slug_at(jid, i)))) is not None and not f.done()

    def nb_now(j):
        "The concepts of the steps of walk `j` whose notebook a job writes now, from the job rows."
        rows = lr.jobs()
        return {s['slug'] for s in j['steps'] if (r := rows.get(f"walk:{j['id']}:nb:{s['slug']}")) and r.state == 'running'}

    def write_notebook(jid, i):
        "Start the job that writes the notebook spec of step `i` on the research pool, unless it runs or the step has a spec."
        with nb_lock:
            j = walk_of(jid, i)
            if not j or nb_writing(jid, i) or j.steps[i].get('nb') or j.steps[i]['check']['kind'] != 'notebook': return
            slug = j.steps[i]['slug']; key = f'walk:{jid}:nb:{slug}'
            nb_jobs[jid, slug] = track(lr, key, lambda: ctx.research.pool.submit(walk_engine.nb_spec, lr, ask, j, i, stop=lambda: check_stop(lr, key)), 'notebook',   # nb_spec writes to the step by its concept
                                       title=f"The notebook of {(lr.concept(slug) or {}).get('name', slug)}", said=ui.NB_WRITING, url=ui.at(Routes.step, jid, i), obj=f'walk:{jid}', quiet=True,
                                       again=dict(jid=jid, slug=slug))

    def with_folders(j, i):
        "Walk `j` with each of its data folders in the notebook spec of step `i`: a folder that you added after the tutor wrote the spec joins it, so Leela gets it."
        spec = j.steps[i].get('nb')
        if spec and (d := with_data(spec.get('data'), j.get('data'))) != list(spec.get('data') or ()): return put(j, i, nb={**spec, 'data': d})
        return j

    def nb_card(j, i):
        """The card of a notebook step: the notebook, the line while the tutor writes it, the reason when it could not, or Write the notebook.
        A load of the card starts no model call: only the press (a POST) starts the job."""
        j = with_folders(j, i)
        s, link = j.steps[i], leela_link(j, i, vault=vault)
        if s.get('nb'): return ui.NotebookCard(j.id, i, s, link)
        r = lr.job(f"walk:{j.id}:nb:{s['slug']}")
        if nb_writing(j.id, i): return ui.NbPending(j.id, i, link, s.get('leela_at'), row=r)
        if s.get('nb_why'): return ui.NbFailed(j.id, i, s['nb_why'], link, s.get('leela_at'))
        return ui.NbNotYet(j.id, i, link, s.get('leela_at'), stopped=r is not None and r.state == 'stopped')   # Write the notebook starts it again

    def from_leela(j, i, back=None):
        """The card "From Leela" of step `i`, or None. A done step, and a notebook step that is not done, get Next idea and the link to the lesson:
        the result came back, so the card does not say "Opened in Leela" again. Another step that is not done keeps its own check, so it gets no card."""
        if not (b := (leela_back(lr, j) if back is None else back).get(i)): return None
        j = lr.journey(j.id)
        s = j.steps[i]
        if not s.get('done') and s['check']['kind'] != 'notebook': return None
        return ui.FromLeela(j, i, b, (ui.GoOn(j.id, i, main=main_idea(j, i)), leela_line(j, i, say='Open the lesson in Leela', vault=vault)))

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
        st.update(said=st.said)   # a safe point: after Stop, the pages are filed but no walk is made
        said = (lambda k, n: paper_said(docs)) if is_paper(url) else (lambda k, n: f"Reading {k + 1} of {n_of(n, 'page')}…")
        j = kept(journey_from_sources(lr, ask, docs, progress=lambda k, n: st.update(said=said(k, n)), tool=tool, subject=subject), st)
        run_hook('concepts_added')   # the concepts block places the new concepts on the pool
        if not j.steps:
            lr.drop_journey(j.id)
            raise LinkError('The tutor found no ideas on these pages.')
        write_notebooks(j)
        return j.id

    def kept(j, st):
        "Walk `j` that the job of `st` made; after Stop, the walk goes and the job ends here."
        if job_halted(lr, st._key): lr.drop_journey(j.id); check_stop(lr, st._key)
        return j

    def retitle(jid):
        "On the pool: give a walk named by an arXiv id the title of its paper. A failure of the network keeps the id."
        try: lr.retitle_paper(jid) and lr.repair_id_titles()   # the steps of the walk keep the id too
        except Exception as e: log.warning('abhyasa could not get the title of the paper: %r', e)

    def link_walk(url, pages, tool=False, subject=''):
        "Start the pool job that makes a walk from `url`, unless one is running. The request does not wait for the network or the model."
        try: link_kind(url)
        except ValueError as e: return P(str(e) if isinstance(e, LinkError) else NO_LINK, cls='req-err')
        st = links.get(url)
        if not st or st.job.done():
            paper = is_paper(url)   # one paper: the count of pages to read does not apply
            st = links[url] = Said(lr, ui.build_key(url), said='Reading the paper…' if paper else 'Getting the pages from the link…')
            st.job = built(url, lambda: ctx.pool.submit(from_link, url, int(pages) if str(pages).strip().isdigit() and not paper else None, st, tool, subject),
                           f'A walk from {url}', st.said, again=dict(url=url, pages=str(pages or ''), tool=bool(tool), subject=subject))
        return ui.LinkPending(url, st.said, lr.job(ui.build_key(url)))

    def built(k, fut, title, said, again=None):
        "Give the pool job `fut` that makes a walk its job row: running, then `done` with the link of the walk, or `failed` with the reason. `again` keeps its inputs."
        return track(lr, ui.build_key(k), fut, 'build', title=title, said=said, again=again,
                     ok=lambda jid: dict(url=ui.at(Routes.one, jid), obj=f'walk:{jid}', title=(lr.journey(jid) or {}).get('title') or title, said='The walk is ready.'),
                     why=lambda e: str(e) if isinstance(e, LinkError) else NO_LINK)

    def file_chip(i, st):
        "On the pool: say in `st` what the chip id `i` files, then file it (`walk_engine.file_chip`). Returns (name, docs)."
        kind, _, v = i.partition(':')
        name = Path(v).name if kind in ('folder', 'repo', 'file') else (lr.vault.doc(v) or {}).get('title') or v if kind == 'doc' else v
        if kind in ('folder', 'repo'):
            fs = [] if folder_why(v) else tree_files(v)
            nb = sum(p.suffix == '.ipynb' for p in fs)
            st.update(said=f"Filing {name}: {n_of(nb, 'notebook') if nb else n_of(len(fs), 'file')}")
        elif (line := dict(gh=f'Cloning {v}', file=f'Filing {name}', link='Getting the pages from the link').get(kind)): st.update(said=line)
        return name, walk_engine.file_chip(lr, i)

    filer = CtxPool(FILERS, thread_name_prefix='abhyasa-file')

    def file_one(i, st):
        "On the filer: file the chip `i`. What it gave: `name`, `docs`, `notes`, `filed` (the Undo row, or None), and `bad` for a folder that is refused."
        kind, _, v = i.partition(':')
        try: name, ds = file_chip(i, st)
        except Exception as e:   # one source that fails never stops the walk
            log.warning('abhyasa could not file the source %r: %r', i, e)
            why = f' {e}' if isinstance(e, LinkError) and not str(e).startswith('abhyasa could not') else ''
            return AttrDict(notes=[(f'abhyasa could not clone {v}.' if kind == 'gh' else f'abhyasa could not file {Path(v).name or v}.') + why],
                            bad=kind in ('folder', 'repo', 'file'))   # a refused folder or file never reaches the plan or the agent
        added = getattr(ds, 'added', None)
        return AttrDict(name=name, docs=ds, notes=[f'{name}: {cut}'] if (cut := getattr(ds, 'cut', '')) else [],
                        filed=dict(root=str(Path(v).expanduser().resolve()) if kind == 'file' else name, docs=[dict(x) for x in added], at=time.time(),   # the root of the docs (`file_file`)
                                   notebooks=sum(str(x.url).endswith('.ipynb') for x in added)) if added else None)

    def still(i): return f"abhyasa is still filing {i.partition(':')[2].rstrip('/').split('/')[-1]}. The walk uses it when it is filed."

    def joined(jid, i, fut):
        "On the filer, when the chip `i` is filed after its walk `jid` was made: it joins the chips of the walk, with its count, its Undo and its notes."
        try: o = fut.result()
        except Exception as e: o = AttrDict(notes=[f'abhyasa could not file {i}.'], bad=True); log.warning('abhyasa could not file %r: %r', i, e)
        join(jid, i, o)

    def join(jid, i, o):
        "The chip `i` that `file_one` filed as `o` joins walk `jid`. After Stop on the filing, it does not join; what it filed keeps its Undo."
        key = f'walk:{jid}:filing'
        if (lr.job(key) or {}).get('halt'): o = AttrDict(o, bad=True, notes=[])   # you stopped the filing: the chip leaves the walk
        with _jlock(jid):
            if not (j := lr.journey(jid)): return
            chips = [x for x in j.get('chips') or () if not (o.get('bad') and x == i)]
            if not o.get('bad') and i not in chips: chips.append(i)
            lr.put_journey({**j, 'chips': chips, 'filing': [x for x in j.get('filing') or () if x != i],
                            'chip_counts': {**(j.get('chip_counts') or {}), **({i: len(o.docs)} if 'docs' in o else {})},
                            'filed': [*(j.get('filed') or ()), *([o.filed] if o.get('filed') else [])],
                            'notes': [n for n in j.get('notes') or () if n != still(i)] + o.notes})
            if not lr.journey(jid).get('filing') and (r := lr.job(key)) is not None and r.state == 'running':   # the last one is in
                job_end(lr, key, 'stopped', said=STOPPED) if r.get('halt') else job_end(lr, key, said='The sources are filed.')

    @hook('walk_add_sources')
    def add_sources(jid, ids):
        "File the chips `ids` for the walk `jid` that it does not have, each on its own job. Each one joins the walk when it is filed. Gives the ids that it started."
        with _jlock(jid):
            if not (j := lr.journey(jid)): return []
            new = [i for i in dict.fromkeys(ids) if i and i not in (j.get('chips') or ()) and i not in (j.get('filing') or ())]
            if new:
                lr.put_journey({**j, 'filing': (now := [*(j.get('filing') or ()), *new])})
                job_start(lr, f'walk:{jid}:filing', 'filing', title=j.title, said=f"Filing {n_of(len(now), 'source')}",
                          url=ui.walk_url(jid, 'sources'), obj=f'walk:{jid}', quiet=for_talk(j), again=dict(jid=jid, ids=now))
        for i in new: filer.submit(file_one, i, AttrDict(said='')).add_done_callback(lambda f, i=i: joined(jid, i, f))
        return new

    def mine(paths, notes):
        "Your data folders `paths` as rows; a folder that abhyasa cannot use adds its line to `notes`."
        rows = []
        for p in paths:
            try: rows = keep_data(rows, p)
            except ValueError as e: notes.append(f'{Path(p).name}: {e}')
        return rows

    def from_goal(goal, ids, st, subject='', data=(), audience='', no_code=False):
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
        if goal: j = walk_from_topic(lr, ask, goal, profile_text(lr.profile()), ctx.sources, False, chips=ids, data=rows, audience=audience, no_code=no_code)   # the plan sees the documents of the chips and your data
        elif docs:
            n = val('links.pages')
            j = journey_from_sources(lr, ask, docs[:n], title=' and '.join(names), subject=subject, audience=audience, no_code=no_code,
                                     progress=lambda k, m: st.update(said=f"Reading {k + 1} of {n_of(m, 'document')}"))
        else: raise LinkError(' '.join(notes) or 'abhyasa found no text to read in these sources.')
        run_hook('concepts_added')
        if not j.steps:
            lr.drop_journey(j.id)
            raise LinkError('The tutor found no steps for this goal.' if goal else 'The tutor found no ideas in these sources.')
        kept(j, st)
        j = lr.merge_journey(j.id, filed=filed, notes=notes, chips=list(ids), chip_counts=counts, filing=late, **({'data': rows} if rows else {}))
        for i in late: jobs[i].add_done_callback(lambda f, i=i: joined(j.id, i, f))   # it can be done now: then it joins at once
        if goal:
            run_hook('goal_walk', j)   # the course block joins the walk to the course of its goal
            if want_agent(j): ctx.research.gather(j.id); write_notebooks(j)   # a big goal: the agent gathers the sources (D6)
            else: research_new(j)
            if val('research.on') and not val('research.told'): set_val('research.told', True)
        return j.id

    def goal_walk(goal, ids, subject='', data=(), audience='', no_code=False):
        "Start the pool job that files the chips `ids` and makes the walk with your `data` folders, for `audience` and with `no_code`, unless one is running. The request does not wait."
        key = 'goal:' + hashlib.sha1(json.dumps([goal, ids, list(data), audience, no_code]).encode()).hexdigest()[:12]
        st = links.get(key)
        if not st or st.job.done():
            st = links[key] = Said(lr, ui.build_key(key), said='Planning the walk')
            st.job = built(key, lambda: ctx.pool.submit(from_goal, goal, ids, st, subject, data, audience, no_code), goal or 'A walk through your sources', st.said,
                           again=dict(goal=goal, ids=list(ids), subject=subject, data=list(data), audience=audience, no_code=no_code))
        return ui.LinkPending(key, st.said, lr.job(ui.build_key(key)))

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
        r = lr.job(ui.build_key(url.strip()))
        if not st.job.done(): return ui.LinkPending(url.strip(), st.said, r)
        if (e := st.job.exception()) or (r is not None and r.state == 'stopped'):   # never the words of a library; what Start filed keeps its Undo
            line = f'{STOPPED} No walk was made.' if isinstance(e, JobStopped) or (r is not None and r.state == 'stopped') else str(e) if isinstance(e, LinkError) else NO_LINK
            return ui.LinkEnded(url.strip(), line, r, ui.Filed(dict(id='', filed=st.get('filed')), job=url.strip()))
        return Response(headers={'HX-Redirect': ui.at(Routes.one, st.job.result())})

    def new(ref:str='', shelf:str='store', text:str='', title:str='', topic:str='', url:str='', pages:str='', tool:str='', subject:str='',
            q:str='', pick:str='', file:str='', opts:str='', doc:str='', sources:list[str]=None, chips:str='', mine:list[str]=None, audience:str='', no_code:str='', talk:str=''):
        if (q.strip() or chips) and not any(x.strip() for x in (ref, text, topic, url)):   # the Start box: its reading says which field it is
            t = vault_title(lr.vault, q) if not file else None
            r = detect(q, dict([t]) if t else {}, research=val('research.on'), file=file, pick=pick, doc=doc, roots_in_vault=vault_roots(lr))   # `ref` is a document id
            ids = [x for x in (sources or []) if x] if chips else r.send.get('sources', [])   # the chips that the box showed, less the ones that you removed
            goal = r.kind == 'goal' or (chips and r.kind == 'topic')   # a topic with sources that you added is a goal
            if talk:   # Make a talk: your data folders are not sources
                ids, aim = [x for x in ids if x not in (mine or ())], q.strip() if r.kind in ('goal', 'topic') else ''
                if not aim and not ids: return P('Add a source or write a goal first.', cls='req-err')
                return first(run_hook('talk_from_sources', ids, aim, audience.strip(), bool(no_code))) or P('abhyasa cannot make a talk now.', cls='req-err')
            if (goal or r.kind in ('sources', 'folder')) and (r.send or chips):
                ours = [x for x in ids if x in (mine or ()) and x.startswith('folder:')]   # the folders that you ticked as your data: not filed
                ids = [x for x in ids if x not in ours]
                if not goal and not ids: return P('Add a source first.', cls='req-err')
                return goal_walk(q.strip() if goal else '', ids, clean_subject(subject), [x.partition(':')[2] for x in ours], audience.strip(), bool(no_code))
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
            elif topic.strip(): j = walk_from_topic(lr, ask, topic.strip(), profile_text(lr.profile()), ctx.sources, tool, audience=audience.strip(), no_code=bool(no_code))
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

    def one(jid:str, plan:str=''):
        """The walk page, in the state of the walk: new, going, finished, a side walk, or empty. The box and the plan change it in place.
        `?plan=1` was the build view: it goes to the sources."""
        if plan: return RedirectResponse(ui.walk_url(jid, 'sources'), status_code=301)
        if not (j := walk_of(jid)): return missing()
        leela_back(lr, j)   # a step that Leela checked is done, so the walk goes on from the next one
        j, b = lr.journey(jid), by()
        st = walk_state(j, b)   # an idea learned elsewhere is known
        seen(j)
        ph = ui.phase(j, st)
        bk = back_to(j) if ph == 'side' else None
        top = ended(j, b) if ph == 'finished' else Div(ui.SideTop(j, st, bk), *(run_hook('walk_end', j) if st.current is None else ())) if ph == 'side' else None   # a side walk that ends says what you learned on the way
        ts = talks_of(jid)
        plan_ = ui.PlanPart(j, b, nb_now(j), busy=replanning(jid)) if j.steps and not for_talk(j) else ''
        page = ui.WalkPage(j, st, b, plan_, band(j, plan=True), top=top, more=run_hook('walk_plan_more', j), talks=ts,
                           changed={t['id'] for t in ts if any(walk_changes(lr, t).values())}, actions=run_hook('walk_actions', j, quiet=True), vault=vault,
                           lead=ui.side_lead(j, b, bk), copy=str(copy_path(lr.vault.assets(), j)) if (j.get('notebook') or {}).get('path') else '', change=replan_part(jid))
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
        j = shown(j, i, b)
        line = [band(j)] if researching(jid) or j.get('research_start') or j.get('gather_at') else []   # the line of research is on each step
        page = ui.StepPage(j, walk_state(j, b), b, i, needs=[*line, *run_hook('step_needs', j, i, b.get(j.steps[i]['slug']))], back=back_to(j), vault=vault, words=words(j, i, b),
                       present=run_hook('walk_actions', j, quiet=True), looking=looking(jid, i), result=None if for_talk(j) else from_leela(j, i, back),
                       figure=figure_file(j, i) is not None, chips=[] if for_talk(j) else [y for t in ('question', 'hint') for y in run_hook('model_chip', t)])   # a figure whose file is not there draws no broken image
        return Page(ui.name(b, j.steps[i]), page, wide=True, extra=ui.assets(),
                    on='Home', crumbs=[*up, (j.title, ui.at(Routes.one, jid))])

    def shown(j, i, b):
        "Walk `j` with the passage of step `i` as the page shows it (`transcript_read`): a transcript gives a tight span and its links. Nothing is saved."
        s = j.steps[i]
        if (r := transcript_read(lr, s.get('read'), b.get(s['slug']))) is s.get('read'): return j
        return AttrDict({**j, 'steps': [*j.steps[:i], {**s, 'read': r}, *j.steps[i + 1:]]})

    def note(jid:str, i:int):
        "The tutor note of step `i`, loaded after the page; a failed note shows nothing."
        if not (j := walk_of(jid, i)): return Response(status_code=404)
        try:
            with held(jid, i):
                if (w := step_read(lr, jid, j.steps[i]['slug'], ctx.sources)):   # an old path: its passage comes now, when the idea opens
                    s = w.steps[i]
                    v = shown(w, i, by())
                    return ui.Note(tutor_note(lr, ctx.ask, w, i, ctx.sources)), ui.Passage(v, v.steps[i], lr.concept(s['slug']), i, looking(jid, i))(hx_swap_oob='true')
                return ui.Note(tutor_note(lr, ctx.ask, j, i, ctx.sources))
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
        j = lr.journey(jid)
        return (card(j, i), ui.Words(ws, oob=True)) if (ws := words(j, i)) else card(j, i)   # the check can name a term that the page did not

    def try_again(jid:str, i:int):
        "Try the check again: open the closed check of step `i` again, with a new question. The attempts of the last one stay in your record."
        if not (j := walk_of(jid, i)) or j.steps[i]['check']['kind'] == 'notebook': return Response(status_code=404)
        with _jlock(jid):
            if (qid := (j := lr.journey(jid)).steps[i].get('qid')) in tutor.open: tutor.open.pop(qid)
            lr.walk_step(jid, i, done=None, qid=None)
        return check(jid, i)

    def nb_again(jid:str, i:int):
        "Write the notebook: start the job that writes the notebook spec of step `i`, the first time or again after the tutor could not."
        if not (j := walk_of(jid, i)) or j.steps[i]['check']['kind'] != 'notebook': return Response(status_code=404)
        if j.steps[i].get('nb_why'): j = put(j, i, nb_why='')
        write_notebook(jid, i)
        return card(lr.journey(jid), i)

    def open_leela(jid:str, i:int):
        "Open in Leela: note the time on step `i` (`leela_at`), then go to the Leela link. When Leela does not run, go back to the step."
        with _jlock(jid):   # one read of the walk: the link, the concept opened at this place and the stamp all name the same idea
            if not (j := walk_of(jid, i)): return Response(status_code=404)
            if not (link := leela_link(j, i, vault=vault, go=True)): return RedirectResponse(ui.at(Routes.step, jid, i), status_code=303)
            j = with_folders(j, i)
            slug = j.steps[i]['slug']   # an older Leela lesson files no concept, so its results match only while the step at this place has it
            lr.put_journey({**j, 'leela_opened': {**(j.get('leela_opened') or {}), str(i): slug}})
            lr.walk_slug(jid, slug, leela_at=time.time())
        return RedirectResponse(link, status_code=303)

    def failed(what, jid, i, e):
        "A call to the model that failed: the log gets the error, and the page a plain line. A 503 keeps the answer in its box."
        if isinstance(e, Withheld): return Response(WITHHELD, status_code=403, media_type='text/plain')
        log.warning('the tutor could not %s on %s step %s: %r', what, jid, i, e)
        return Response(f'The tutor could not {what}. Try again.', status_code=503, media_type='text/plain')

    def answer(jid:str, i:int, answer:str='', thinking:str='', confidence:int=None):
        j, s = live(jid, i)
        if not s: return no_check(j, i)
        if (words := show_ask(answer)) is not None:   # "show me …" opens a demo under the title (the demo block); it uses no try
            return card(j, i), *run_hook('show_me', words, dict(where='walk', concept=j.steps[i]['slug'], walk=jid, step=i))
        if not str(answer).strip(): return Response(EMPTY, status_code=400, media_type='text/plain')   # no try is spent
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
            if not (text := demo_lesson(tutor, a, ld['way'])) or isinstance(text, NoLesson): return False   # an empty lesson or the fallback note is a failure
            check_stop(lr, f'lesson:{slug}')   # after Stop, the lesson is not kept
            with writing[jid, slug]:   # by its concept: the step can move while the lesson is written
                st = first(x for x in (lr.journey(jid) or {}).get('steps') or () if x['slug'] == slug)
                if st is not None: lr.walk_slug(jid, slug, ladder={**(st.get('ladder') or {}), 'lesson': text})
            return True
        c = lr.concept(slug)
        if a is not None:   # one rung of the ladder: a quiet row, so it does not crowd the chip
            tutor.jobs[k] = track(lr, f'lesson:{slug}', lambda: ctx.pool.submit(job), 'lesson', title=f"Lesson: {c.name if c else slug}", said='Writes a lesson in another way',
                                  url=ui.at(Routes.step, jid, i), obj=f'walk:{jid}', quiet=True, again=dict(jid=jid, slug=slug),
                                  ok=lambda r: dict(said='The lesson is ready.') if r else dict(state='failed', why='The tutor could not write a lesson this time.'))

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
            if jb is not None and not jb.done(): return ui.Ladder(jid, i, ld, pending='The tutor is writing a lesson in another way. You can read the passage while you wait.', job=f'lesson:{slug}', stop=JobStop(lr.job(f'lesson:{slug}')))
            lost = first(x for x in lr.attempts(slug) if x.id == ld.get('aid')) is None   # no attempt: a new job cannot help
            if (r := lr.job(f'lesson:{slug}')) is not None and r.state == 'stopped': return ui.Ladder(jid, i, ld, failed=STOPPED, retry=not lost, again='Do it again')
            return ui.Ladder(jid, i, ld, failed='The tutor could not write a lesson this time.', retry=not lost)
        # the simpler demo: after the second wrong prediction, or when you asked for it
        if (d := lr.demo_for(slug, aim='simpler')) and not said(lr, slug, 'unclear'): return ui.Ladder(jid, i, ld, demo=d, show=bool(show) or bool(ld.get('asked')))   # after "Not clear", a new one
        st = job_state(tutor, slug, 'simpler')
        if stop and st != 'failed': return ui.Ladder(jid, i, ld)
        if st == 'running': return ui.Ladder(jid, i, ld, pending='The tutor is making a simpler demo of this idea. You can read the passage while you wait.', job=job_key(slug, 'simpler'), stop=JobStop(lr.job(job_key(slug, 'simpler'))))
        if st == 'stopped': return ui.Ladder(jid, i, ld, failed=STOPPED, retry=True, again='Make it again')
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
                                 kind=s['check']['kind'], method=s['check']['way'], ask=ask, **step_meta(j, i))
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

    def next_(jid:str, i:int, req):
        """Skip step `i` when it has no outcome yet, then go to the next step, or to the summary at the end of a section. After the last idea
        of a side walk, go back to the main idea, with what you learned on the way (`back_from`); in the side pane, the walk page has the end note, which closes the pane."""
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
        pane = 'pane=1' in f"{req.url.query}&{urlsplit(req.headers.get('hx-current-url') or req.headers.get('referer') or '').query}"
        if last and not pane and (pj := back_from(lr, jid)) and (k := parent_step(lr, lr.journey(jid))[1]) is not None:
            return RedirectResponse(ui.at(Routes.step, pj.id, k), status_code=303)   # the main idea, with the strip of what you learned
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

    def figure_file(j, i):
        "The file of the figure of step `i`: only inside the vault assets, and only an image file that is there. None when there is none."
        if not (f := (j.steps[i].get('read') or {}).get('figure')): return None
        root = Path(lr.vault.assets()).resolve()
        p = (root/f).resolve()
        return p if p.is_relative_to(root) and p.suffix.lower() in FIGURES and p.is_file() else None

    def img(jid:str, i:int):
        "The figure of step `i`, only from inside the vault assets and only as an image file."
        if not (j := walk_of(jid, i)) or not (p := figure_file(j, i)): return Response(status_code=404)
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
        if not (j := lr.journey(jid)): return missing()
        walk_path(lr, j)
        return RedirectResponse(ui.at(Routes.one, jid) + (f'?{q}' if (q := req.url.query) else ''), status_code=301)

    def migrate():
        "On the research pool: each old path becomes a topic walk, one time, with its job row. No row when there is no path."
        if not any(j.get('mode') != 'walk' for j in lr.journeys()): return []
        job_start(lr, 'walk:paths', 'migrate', title='Your old paths become walks', said='Making your old paths walks', quiet=True)
        try: ids = walk_paths(lr)
        except Exception as e:
            log.warning('abhyasa could not make the old paths walks: %r', e)
            job_end(lr, 'walk:paths', 'failed', why='abhyasa could not make your old paths walks. It tries again at the next start.')
            return []
        job_end(lr, 'walk:paths', 'done')
        return ids

    @hook('app_start')
    def paths():
        "At the start: make the old paths walks on the research pool, as the scan for pending sources does. The start and Home do not wait for it."
        return ctx.research.pool.submit(migrate)

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

    def view(j, fresh='', oob=False): return ui.Steps(j, by(), fresh=fresh, nb=nb_now(j), oob=oob), ui.Hands(j, oob=True), ui.Size(j, oob=True)

    def queue_new(j, old):
        "After an idea came in: look for a web source for each new step with no passage, and write the notebook of each new notebook step."
        new = [i for i, s in enumerate(j.steps) if s['slug'] not in old]
        if val('research.on') and (ix := [i for i in new if wants_source(j.steps[i])]): look_for(j.id, ix)
        for i in new:
            if j.steps[i]['check']['kind'] == 'notebook': write_notebook(j.id, i)
        return j.steps[new[0]]['slug'] if new else ''

    async def edit(req, jid:str):
        "One change by hand to the path of walk `jid`: move, skip, bring back, remove, lock or unlock. The step is named by `slug` (its concept), never by its place."
        form = await req.form()
        f = {k: CTRL.sub('', v) for k, v in {**dict(req.query_params), **{k: v for k, v in form.items() if isinstance(v, str)}}.items()}
        if not (j := walk_of(jid)) or for_talk(j): return Response('No such walk.', status_code=404)
        act, slug = f.get('act', ''), f.get('slug', '')
        if act not in EDIT_ACTS: return bad(f'Unknown change: {act}.')
        slugs, b = [s['slug'] for s in j.steps], by()
        if slug not in slugs: return Response('This idea is not in the walk now.', status_code=404)
        nm = lambda x: ui.name(b, dict(slug=x))
        try:
            if act in ('lock', 'unlock'):
                op, said = (lambda ss: lock_step(ss, slug, act == 'lock')), (f'Kept “{nm(slug)}”. The builder and the box do not change it.' if act == 'lock' else f'“{nm(slug)}” can change again.')
            elif act == 'move':
                to = place(f.get('to', ''), len(slugs))
                op, said = (lambda ss: move_step(ss, slug, to)), f'Moved “{nm(slug)}” to idea {to + 1}.'
            elif act in ('skip', 'back'):
                op, said = (lambda ss: skip_step(ss, slug, act == 'skip')), f"{'Skipped' if act == 'skip' else 'Brought back'} “{nm(slug)}”."
            else: op, said = (lambda ss: remove_step(ss, slug)), f'Removed “{nm(slug)}”.'
            j2, rows = edit_walk(lr, jid, op, said, touch=None if act in ('lock', 'unlock') else slug)   # a change by hand unlocks the idea
        except KeyError as e: return Response(str(e.args[0] if e.args else 'Not found.'), status_code=404)
        except ValueError as e: return bad(str(e))
        if rows is None: return view(j2)
        run_hook('hand_edit', 'walk', jid, said)   # the builder says it in its conversation, as a quiet line
        return (*view(j2), bar(j2, said, rows, slug))

    def undo_(jid:str, step:str=''):
        "Take back the newest change of the path (`step` is its id, so an old bar does nothing)."
        if not (j := walk_of(jid)) or for_talk(j): return Response('No such walk.', status_code=404)
        try: e, line = undo_walk(lr, jid, step or None)
        except ValueError as x: return bad(str(x))
        j = lr.journey(jid)
        said = f"Undone: {e.what}" + (f' {line}' if line else '') if e else 'Nothing to undo.'
        return (*view(j), bar(j, said, lr.edits('walk', jid)), Div(id='change-out', aria_live='polite', hx_swap_oob='true'))   # what the box changed goes: it is undone

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

    # --- the box: your words, the changes that the tutor makes with the ops of the editor, and one Undo ---------

    def improve_job(jid, words, st, fix=False):
        """On the pool: file each link in `words` (it joins the sources of the walk, with its Undo), ask the tutor for the changes, and make them
        as one change with an Undo. With `fix`, the tutor redoes each idea that is not locked. A locked idea never changes. Gives `(changes, id of the change)`."""
        docs = {}
        for u in links_in(words):
            st.update(said=f'Getting the pages from {u}')
            o = file_one(f'link:{u}', st)
            join(jid, f'link:{u}', o)
            if o.get('docs'): docs[u] = [dict(shelf=d.shelf, doc_id=d.doc_id) for d in o.docs]
        st.update(said=FIXING if fix else 'The tutor reads what you asked')
        j, b = lr.journey(jid), by()
        cs = propose(ask, j, {k: c.name for k, c in b.items()}, words, ui.weak_of(j), list(docs), fix=fix)
        if not cs: return [], ''
        st.update(said='The tutor changes the walk')
        old = {s['slug'] for s in j.steps}
        j2, rows = improve_walk(lr, ask, jid, cs, ctx.sources, docs, fix=fix)
        run_hook('concepts_added')
        queue_new(j2, old)
        slugs = [s['slug'] for s in j2.steps]
        for c in cs:   # a check that the box made a notebook gets its notebook spec
            if c.op == 'kind' and c.kind == 'notebook' and c.slug in slugs: write_notebook(jid, slugs.index(c.slug))
        if (ix := [slugs.index(c.slug) for c in cs if c.op == 'source' and c.slug in slugs]): look_for(jid, ix)   # "add sources for idea 2": research looks now
        return cs, rows[0].id if rows else ''

    def improve(jid:str, words:str=''):
        "The box: start the job that files the links in `words`, asks the tutor for changes and makes them. The answer is the pending line."
        if not (j := walk_of(jid)) or for_talk(j): return Response(status_code=404)
        if not (words := ' '.join(CTRL.sub('', words).split())[:WORDS_MOST]): return P('Write what should change.', cls='req-err')
        fix = bool(FIX_WORDS.search(words))
        key = f'improve:{jid}:' + hashlib.sha1(words.encode()).hexdigest()[:12]
        if not (st := links.get(key)) or st.job.done():
            st = links[key] = Said(lr, key, said=FIXING if fix else 'The tutor reads what you asked')
            st.job = track(lr, key, lambda: ctx.pool.submit(improve_job, jid, words, st, fix), 'improve', title=f'Change the walk: {j.title}', said=st.said, again=dict(jid=jid, words=words),
                           url=ui.walk_url(jid, 'change'), obj=f'walk:{jid}', ok=lambda r: dict(said='The tutor changed the walk.' if r[0] else 'The tutor found nothing to change.'),
                           why=lambda e: 'The tutor could not change the walk.')
        return ui.ImprovePending(jid, key, st.said, lr.job(key))

    def proposal(jid:str, key:str=''):
        "The box as it is now: the pending line, or what changed with Undo (and the plan, out of band), or a plain line when the tutor could not. A GET only reads."
        if not key.startswith(f'improve:{jid}:') or not (st := links.get(key)): return P('This change is gone. Write it again.', cls='mute')
        r = lr.job(key)
        if not st.job.done(): return ui.ImprovePending(jid, key, st.said, r)
        if isinstance(e := st.job.exception(), JobStopped) or (r is not None and r.state == 'stopped'): return ui.ImproveEnded(jid, key, f'{STOPPED} Nothing changed.', r)
        if e:
            log.warning('the tutor could not change %s: %r', jid, e)
            return ui.ImproveEnded(jid, key, 'The tutor could not change the walk. Nothing changed.', r)
        cs, eid = st.job.result()
        if not (j := walk_of(jid)): return Response(status_code=404)
        return ui.Changed(jid, cs, by(), eid), *(view(j, oob=True) if cs else ())

    # --- Make this walk again: the job that plans the walk again from its source; locked ideas stay, and one Undo takes it back -----

    def replan_key(jid): return f'walk:{jid}:replan'

    def replan_job(jid, st, chips=None, asks='', audience=None, no_code=None):
        """On the pool: plan walk `jid` again from its source, keep its locked ideas, and save it as one change. Then look for sources of the new ideas. The id of the change.
        With `chips`, the new plan uses only these sources: a new one is filed first, and one that abhyasa cannot file stops the job. `asks`, `audience` and `no_code` go to the planner."""
        j = lr.journey(jid)
        old, kw = {s['slug'] for s in j.steps}, {k: v for k, v in dict(audience=audience, no_code=no_code).items() if v is not None}
        if chips is not None:
            counts = dict(j.get('chip_counts') or {})
            for i in [x for x in chips if x not in (j.get('chips') or ())]:
                o = file_one(i, st)
                if o.get('bad') or 'docs' not in o: raise ValueError(' '.join(o.notes) or f'abhyasa could not file {i}.')
                counts[i] = len(o.docs)
                if o.filed: lr.merge_journey(jid, filed=[*(lr.journey(jid).get('filed') or ()), o.filed])   # its Undo
            kw.update(chips=list(chips), chip_counts={k: n for k, n in counts.items() if k in chips})
        j2, rows = replan_walk(lr, ask, jid, ctx.sources, profile_text(lr.profile()), said=lambda x: st.update(said=x), asks=asks, **kw)
        run_hook('concepts_added')
        queue_new(j2, old)
        return rows[0].id if rows else ''

    def replan_form(j, sources, add, audience, no_code, asks):
        "The inputs of the job from the form of Make this walk again, or the lines that say why it cannot start."
        said, kw = [], dict(asks=asks.strip())
        add = '\n'.join(x.strip() for x in add or () if x.strip())   # the typed field and each picked path, one on each line
        if is_goal_walk(j) or j.get('chips'):
            ids = [x for x in sources or () if x in (j.get('chips') or ())]
            found = on_disk(named_sources(add, dict(title_index(lr.vault).values()), {}, vault_roots(lr))) if add else []
            if add and not found: said.append(f'abhyasa cannot use {add[:80]} as a source. Add the path of a folder or a file, owner/name of a GitHub repo, or a link.')
            said += [f'{c.name}: {c.why}' for c in found if c.get('why')]
            ids += [c.id for c in found if not c.get('why') and c.id not in ids]
            if not ids and not is_goal_walk(j): said.append('Keep one source or add one. A walk through its sources needs a source.')
            kw['chips'] = ids
        if is_goal_walk(j) or j.get('chips'): kw.update(audience=audience.strip(), no_code=bool(no_code))
        return said, kw

    def replan(req, jid:str, form:str='', sources:list[str]=None, add:list[str]=None, audience:str='', no_code:str='', asks:str=''):
        """Make this walk again: start the job, unless it runs, then open the walk page at the box, where its line has Stop. With `form`, the job uses
        the sources that you kept, picked (`add`) and typed (`add`), who the walk is for, No code and what you ask; a source that abhyasa cannot use shows the form again with its line.
        The form posts with htmx. On the walk page itself, the answer swaps in place: the menu closes, the line goes in the box and the plan shows as a skeleton.
        A redirect to the same page with only another `#part` does not load the page again, so the browser would show nothing new."""
        if not (j := walk_of(jid)) or for_talk(j): return missing()
        said, kw = replan_form(j, sources, add, audience, no_code, asks) if form else ([], {})
        if said: return ui.WalkMenu(j, said)
        start_replan(j, kw)
        if form and urlsplit(req.headers.get('hx-current-url', '')).path == ui.walk_url(jid):
            j = walk_of(jid)   # a job that already ended sends its plan, since no line waits to put it in the place of a skeleton
            return ui.WalkMenu(j), Div(replan_part(jid), id='change-out', aria_live='polite', hx_swap_oob='true'), *((ui.PlanBusy(j, oob=True),) if replanning(jid) else view(j, oob=True))
        if form: return Response(headers={'HX-Redirect': ui.walk_url(jid, 'change')})   # from another page, such as Home: the walk page opens
        return RedirectResponse(ui.walk_url(jid, 'change'), status_code=303)

    def start_replan(j, kw):
        "Start the job of Make this walk again for walk `j` with the inputs `kw` of `replan_job`, unless it runs. Its row keeps them for Plan it again."
        key, jid = replan_key(j['id']), j['id']
        if not (st := links.get(key)) or st.job.done():
            st = links[key] = Said(lr, key, said='Making the plan again')
            st.job = track(lr, key, lambda: ctx.pool.submit(replan_job, jid, st, **kw), 'replan', title=f'Make the walk again: {j.title}', said=st.said,
                           url=ui.walk_url(jid, 'change'), obj=f'walk:{jid}', again=dict(jid=jid, **kw),
                           ok=lambda eid: dict(said=' '.join(['The tutor made the plan again.', replan_said(lr.journey(jid), eid) if eid else '']).strip(), eid=eid),
                           why=lambda e: str(e) if isinstance(e, ValueError) else 'The tutor could not make the plan again. The plan did not change.')

    def replanning(jid):
        "Make this walk again runs for walk `jid`: its plan shows as a skeleton."
        return (r := lr.job(replan_key(jid))) is not None and r.state == 'running'

    def replan_said(j, eid) -> str:
        "What change `eid` of Make this walk again did to walk `j`, in one or two sentences: the ideas that it removed and the ideas that it added."
        e = next((x for x in lr.edits('walk', j.id) if x.id == eid), None)
        if e is None or not isinstance(e.get('before'), list): return ''
        b, was, now = by(), {s['slug']: s for s in e.before}, {s['slug']: s for s in j.steps}
        def names(ss): return ', '.join(f'“{ui.name(b, s)}”' for s in ss)
        gone, new = [s for k, s in was.items() if k not in now], [s for k, s in now.items() if k not in was]
        if not gone and not new: return f"The plan has the same {n_of(len(now), 'idea')}."
        return ' '.join([f"Removed {n_of(len(gone), 'idea')}: {names(gone)}." if gone else 'Removed no ideas.',
                         f"Added {n_of(len(new), 'idea')}: {names(new)}." if new else 'Added no ideas.',
                         f"The plan has {n_of(len(now), 'idea')} now."])

    def replan_part(jid):
        "The line of Make this walk again on the walk page: while its job runs, and for 10 minutes after it ended in this run of the app."
        r = lr.job(key := replan_key(jid))
        if r is None or (r.state != 'running' and (key not in links or time.time() - (r.get('end') or 0) > 600)): return ''
        return ui.Replanned(jid, key, r, eid := r.get('eid') or '', replan_said(lr.journey(jid), eid) if r.state == 'done' and eid else '')

    def replan_state(jid:str, key:str=''):
        """The line of Make this walk again as it is now. When the job ends, the plan comes too, out of band, in the place of its skeleton.
        Done: the Undo bar under the plan says what changed. A GET only reads."""
        if not (j := walk_of(jid)) or key != replan_key(jid): return Response(status_code=404)
        r = lr.job(key)
        if r is None or r.state == 'running': return ui.Replanned(jid, key, r)
        eid = r.get('eid') or '' if r.state == 'done' else ''
        said = replan_said(j, eid) if eid else ''
        tell = (UndoBar(f'{ui.REPLAN_DONE} {said}'.strip(), ui.at(Routes.undo, j.id), ui.walk_url(j.id, 'history'), step=eid, hx_target='#steps', hx_swap='outerHTML'),) if eid else ()
        return ui.Replanned(jid, key, r, eid, said), *view(j, oob=True), *tell

    @hook('job_stop')
    def stop_job_of(r):
        "Stop in the jobs list on research: the research of the walk stops as with its own Stop. Other jobs of the walk stop at their next safe point."
        if r.get('kind') == 'research' and (jid := (r.get('obj') or '')[5:]): ctx.research.stop(jid); return True
        return None

    @hook('job_again')
    def again_of(r):
        "Do it again on a job of a walk: the same job with the inputs that its row kept."
        a, k = r.get('again'), r.get('kind')
        if not isinstance(a, dict): return None
        jid = a.get('jid') or ''
        if k == 'build' and a.get('url'): link_walk(a['url'], a.get('pages') or '', bool(a.get('tool')), a.get('subject') or '')
        elif k == 'build' and 'ids' in a: goal_walk(a.get('goal') or '', a.get('ids') or [], a.get('subject') or '', a.get('data') or (), a.get('audience') or '', bool(a.get('no_code')))
        elif not walk_of(jid): return None
        elif k == 'research': again(jid)
        elif k == 'replan': start_replan(walk_of(jid), {x: a[x] for x in ('chips', 'asks', 'audience', 'no_code') if x in a})
        elif k == 'improve': improve(jid, a.get('words') or '')
        elif k == 'filing': add_sources(jid, a.get('ids') or [])
        elif k in ('notebook', 'lesson') and (i := next((n for n, s in enumerate(lr.journey(jid).steps) if s['slug'] == a.get('slug')), None)) is not None:
            if k == 'notebook': nb_again(jid, i)
            elif lr.journey(jid).steps[i].get('ladder'): lesson_job(jid, i, a['slug'])
            else: return None
        else: return None
        return True

    def drop(jid:str):
        """Delete walk `jid`: its plan, its history of changes, and its side walks (they belong to its ideas, so they go with it).
        Answers, attempts, demos and what you learned stay in the vault. Then the list of walks (Home)."""
        if not (j := lr.journey(jid)) or j.get('mode') != 'walk' or for_talk(j): return missing()
        if (ev := ctx.research.stops.get(jid)) is not None: ev.set()   # research of the walk stops at its next step
        gone, todo = set(), [jid]
        while todo:
            k = todo.pop()
            if k in gone: continue
            gone.add(k)
            todo += [w.id for w in lr.journeys() if (w.get('parent') or {}).get('walk') == k]
        for k in gone:
            lr.drop_edits('walk', k)
            lr.drop_journey(k)
        return RedirectResponse('/', status_code=303)

    def open_notebook(req, jid:str, i:int=None):
        """Learn the notebook in Leela: write the learning copy of the notebook of walk `jid` in the folder of the walk, with a line back to the walk at
        the top and each demo of the walk as a rupaka cell after its section, note its path on the walk, and go to Leela, which opens the copy at the
        section of idea `i` (else the idea you are on) and runs it in the folder of your notebook. The learner's own notebook never changes. A copy
        that you changed in Leela stays as it is. A demo that is not made yet starts now, and the next press puts it in a new copy."""
        if not (j := walk_of(jid)) or not (j.get('notebook') or {}).get('path'): return missing()
        i = i if i is not None and 0 <= i < len(j.steps) else walk_state(j).current
        for k in range(len(j.steps)): ahead(j, k)
        demos = {s['slug']: d.spec for s in j.steps if s['check']['kind'] in AIM and (d := demo(s)) and isinstance(d.get('spec'), dict)}
        dest = copy_path(lr.vault.assets(), j)
        kept = dest.is_file() and j.notebook.get('wrote') not in (None, nb_sha(dest))   # you changed the copy in Leela: it stays
        try: p = dest if kept else nb_head(learning_copy(j, dest, demos), j, f"{str(req.base_url).rstrip('/')}{ui.at(Routes.one, jid)}")
        except (OSError, ValueError) as e:
            log.warning('abhyasa could not write the learning copy of %s: %r', jid, e)
            return Page('Leela', H1(j.title), P('abhyasa could not read your notebook, so it wrote no copy. Check that the file is still there.', cls='req-err'), on='Home', crumbs=up)
        nb = {**j.notebook, 'copy': str(p), **({} if kept else {'wrote': nb_sha(p)})}
        if not (link := leela_open(j, i, cell=copy_cell(p, j, i), vault=vault)):
            lr.merge_journey(jid, notebook=nb)
            return Page('Leela', H1(j.title), P(LEELA_OFF, cls='mute'), on='Home', crumbs=up)
        lr.merge_journey(jid, notebook={**nb, 'opened': time.time()})   # the step says when its notebook opened in Leela
        return RedirectResponse(link, status_code=303)

    @hook('walk_actions')
    def walk_menu(j, quiet=False, row=False):
        "On the row of a walk in the list of walks: its ⋯ menu, with Delete this walk."
        return ui.WalkMenu(j) if row and not for_talk(j) else None

    def walks_of(slug, side=False):
        "`(walk, index)` for each walk that has a step on concept `slug`. A side walk (it has a `parent`) only with `side`: it belongs to the idea that opened it."
        return [(j, i) for j, i in with_step(lr, slug) if j.get('mode') == 'walk' and not for_talk(j) and (side or not j.get('parent'))]

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
        rows = [(j, i) for j, i in walks_of(r.concept, side=True) if (j.steps[i].get('read') or {}).get('text')]
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
    app.post(Routes.improve)(improve)
    app.get(Routes.improve)(proposal)
    app.post(Routes.replan)(replan)
    app.get(Routes.replan)(replan_state)
    app.post(Routes.drop)(drop)
    app.post(Routes.notebook)(open_notebook)
    app.get(Routes.gather_log)(gather_log)
    app.post(Routes.gather_stop)(stop_gather)
    app.post(Routes.gather_again)(again)
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
    app.post(Routes.again)(try_again)
    app.get(Routes.done)(done)
    app.get(Routes.img)(img)
    app.get(Routes.result)(result); app.router.routes.insert(0, app.router.routes.pop())   # before fast_app's static route for `.png`
    app.post(Routes.leela)(open_leela)
    app.get(Routes.leela)(open_leela)   # Abhyasa.app opens the target=_blank form of Open in Leela as a GET
    app.get(Routes.source)(source)
    app.post(Routes.source)(find_source)
