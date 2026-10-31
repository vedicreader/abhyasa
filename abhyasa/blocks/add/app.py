"""Start something new, on Home: one box that reads what you paste or drop and says what abhyasa will do (`detect`).
Also Find concepts only (`POST /add`)."""
import asyncio, hashlib, logging, re, subprocess, sys, threading, time
from fasthtml.common import *
from pathlib import Path
from urllib.parse import urlencode
from abhyasa.core.leela import LOCAL_HOSTS
from abhyasa.core import hook, run as run_hook, Primary, Secondary, Quiet, Pill, asset_css, asset_js, n_of
from abhyasa.sources import extract, from_vault, folder_why, tree_files, vault_roots
from abhyasa.settings import val, roots
from abhyasa.journey import keep_data
from abhyasa.course import course_of, add_data
from abhyasa.detect import detect, vault_title, title_index, folder_names, named_sources, on_disk, fold, _goal
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask', 'pool')
_P = Path(__file__).parent
NO_DOC = 'No document in your vault has this name. To add a web page or a paper, paste its link.'
WEB_ONCE = 'The tutor searches the web for sources. Your topic goes to the search engine.'
OFF = ' Turn this off in Settings.'   # only when the `from the web` chip, with its own link, does not show
CAN = 'Paste a link, a paper or a topic. Add a folder or a repo, or drop a file.'
CUE = 'Drop files to add them as sources.'
PICK = 'Pick folders…'
PICK_SAY = 'Pick one or more folders to learn from. Hold ⌘ to pick more than one.'
PICK_WAIT = 600   # seconds that the folder chooser stays open
NOT_HERE = 'abhyasa opens the folder chooser only on this Mac.'
DROP_MB = 50
DROP_MOST = 20   # the most files in one drop
DROP_WAIT = 60   # seconds that a drop waits for the vault to read the PDF; then the pool goes on and the request answers
STILL = 'abhyasa is still reading this PDF. It shows in your vault when it is done.'
WAIT = dict(paper='Reading the paper…', repo='Getting the repository…', site='Getting the pages from the link…', topic='Planning the walk…',
            goal='Planning the walk…', sources='Filing the sources…')
CHIP = dict(paper='paper', repo='repo', site='site', doc='vault', topic='topic', text='text', goal='goal', sources='sources', folder='folder')
NOT_YET = ('video', 'local', 'file_name')   # Start stays off: the line says why
FOUND = 'abhyasa found these by their names, on this Mac and in your vault. It has read nothing from the web yet.'
NO_GOAL = 'Write your goal in the box. abhyasa uses the sources below.'
MORE = 'Add a folder, a repo or a link. abhyasa files it in your vault for this walk, and the tutor looks in it too.'
USE = (('learn', 'Learn from it'), ('data', 'My data for the exercises'))   # what a folder that you add is for
DATA_ONLY = 'Only a folder on this Mac can be your data.'
KEPT = 'Kept {} as your data for the exercises. abhyasa does not file it.'
NAMES_FOR, DISK_FOR = 300, 60   # seconds that the folder names, and the count of files in one folder, are kept
STATE = dict(gh='a GitHub repo · cloned when you press Start', folder='a folder on this Mac · added when you press Start',
             repo='a repo on this Mac · added when you press Start', link='a link · read when you press Start', doc='in your vault')
log = logging.getLogger(__name__)
_osa, _picking = subprocess.run, threading.Lock()   # the runner of osascript (a test fakes it), and one chooser at a time

def can_pick() -> bool:
    "The folder chooser of macOS opens only when abhyasa runs on a Mac."
    return sys.platform == 'darwin'

PICK_ASK = (f'set fs to choose folder with prompt "{PICK_SAY}" with multiple selections allowed', 'set out to ""',
            'repeat with f in fs', 'set out to out & POSIX path of f & linefeed', 'end repeat', 'return out')   # one path on each line

def choose_folder() -> list:
    "Open the folder chooser of macOS and give the path of each folder that you pick, or [] when you cancel or it times out."
    if not _picking.acquire(blocking=False): return []   # a chooser is open already
    try: r = _osa(['osascript', *[x for l in PICK_ASK for x in ('-e', l)]], capture_output=True, text=True, timeout=PICK_WAIT)
    except (OSError, subprocess.SubprocessError) as e:
        log.info('abhyasa did not get a folder from the chooser: %r', e)
        return []
    finally: _picking.release()
    if r.returncode: return []   # Cancel: osascript stops with an error (-128)
    return list(dict.fromkeys(x.rstrip('/') or '/' for x in r.stdout.splitlines() if x.strip()))

def Use():
    "One choice for what you add: learn from it (the default), or your data, which the exercises run on and abhyasa does not file."
    return Div(*[Label(Input(type='radio', name='use', value=v, checked=v == 'learn'), ' ', t, cls='tick') for v, t in USE],
               Input(type='text', name='note', placeholder='A note on your data (optional)', aria_label='A note on your data', autocomplete='off'), cls='use')

def Pick(): return Button(PICK, type='button', cls='quiet small', id='start-pick') if can_pick() else ''

def Line(r):
    "The quiet line: a small chip with the kind, the first sentence in bold, then the rest."
    if r.kind == 'empty': return P(r.line, cls='will', id='start-will')   # the hint stays quiet
    head, _, rest = r.line.partition('. ')
    return P(Pill(CHIP[r.kind]) if r.kind in CHIP else '', ' ' if r.kind in CHIP else '',
             B(head + ('.' if rest else '')), (' ' + rest) if rest else '', cls='will', id='start-will')

def Ask(r, q=''):
    "One question with two answers. Each answer starts at once: the first is the main button. `Use it for a goal` only moves the folder into a chip (start.js)."
    (la, ka), (lb, kb) = r.ask.a, r.ask.b
    return Div(Primary(la, name='pick', value=ka, data_wait='Filing the folder…' if ka == 'walk' else 'Making the walk…', data_skel='#walk-out'),
               Secondary(lb, type='button', data_goal=q.strip(), id='start-as-goal') if kb == 'goal' else
               Secondary(lb, name='pick', value=kb, data_wait='Planning the walk…' if kb == 'topic' else 'Making the walk…', data_skel='#walk-out'),
               P('The first choice reads your vault document word for word. The second choice plans ideas on the topic and looks for sources.', cls='mute')
               if ka == 'doc' else '', cls='ask')

def Options(r, f):
    "Only the fields that change the result. `f` keeps what you typed in them."
    o, c = r.options, []
    if 'pages' in o: c.append(Label('Pages to read', Input(type='number', name='pages', id='start-pages', min=1, max=val('links.cap'), value=f.get('pages') or val('links.pages'))))
    if 'tool' in o: c.append(Label(Input(type='checkbox', name='tool', id='start-tool', checked=f.get('tool', 'on') == 'on'), ' It is a library or a command-line tool', cls='tick'))
    if 'title' in o: c.append(Label('Title', Input(type='text', name='title', id='start-title', value=f.get('title') or r.send.get('title', ''), placeholder='optional')))
    if 'subject' in o: c.append(Label('Subject', Input(type='text', name='subject', id='start-subject', value=f.get('subject', ''), placeholder='optional, for example: ml, sanskrit')))
    return Div(*c, Input(type='hidden', name='opts', value=','.join(o)), cls='opts') if c else ''

def Say(r, oob=False):
    "The line for a screen reader. It stays on the page and only its words change, so a reader hears each change."
    return P(r.line, id='start-say', cls='sr', aria_live='polite', **({'hx_swap_oob': 'innerHTML'} if oob else {}))

def _home(p) -> str:
    "The path `p`, with `~` for the home folder."
    h = str(Path.home())
    return '~' + p[len(h):] if p == h or p.startswith(h + '/') else p

def Chip(c):
    "One source of the goal: its name, where it is, and what Start does with it. `×` removes it (start.js). A refused folder sends nothing."
    if c.kind == 'folder' and c.filed: where, st = n_of(c.count, 'document') if c.count else '', 'in your vault'
    else: where, st = dict(folder=_home(c.path), repo=_home(c.path), gh=c.path, link=c.path).get(c.kind, ''), STATE.get(c.kind, '')
    bad = c.get('why')
    return Div(B(c.name), Span(Span(where, cls='where') if where else '', Span(bad or st, cls='st'), cls='w'),
               Button('×', type='button', cls='x', aria_label=f'Remove {c.name}', data_chip=c.id),
               '' if bad else Input(type='hidden', name='sources', value=c.id),
               cls='schip' + (' bad' if bad else '' if c.filed else ' new'))

def Chips(cs, said=()):
    "The sources for this goal, the web when research is on, and the field that adds a source."
    web = (Div(B('from the web'), Span('for what your sources do not have'), A('Turn this off in Settings', href='/settings#g-research', cls='st'), cls='schip web')
           if val('research.on') else '')
    return Div(Span('Sources for this goal', cls='lbl'), *map(Chip, cs), web, *[P(x, cls='req-err') for x in said],
               Div(Input(type='text', id='start-add', placeholder='Add a folder, a repo or a link', aria_label='Add a folder, a repo or a link', autocomplete='off'),
                   Button('Add', type='button', cls='quiet small', id='start-add-go'), Pick(), cls='addf'),
               Input(type='hidden', name='chips', value='1'), cls='chips-src', aria_label='Sources for this goal')

def Read(r, f=None, told=True, q='', said=()):
    "What the box will do: the quiet line, the question or the options, the sources of a goal, and the Start button."
    f, cs = f or {}, r.get('chips') or []
    shown = r.kind in ('goal', 'sources') or (r.kind == 'empty' and cs)
    ok = [c for c in cs if not c.get('why')]
    go = r.kind not in ('empty', 'ask', *NOT_YET) and not r.ask and bool(r.send) and (r.kind != 'sources' or bool(ok))
    wait = WAIT.get(r.kind, 'Making the walk…')
    start = (Primary('Start', data_wait=wait, data_skel='#walk-out', id='start-go', rank=6, data_act='start') if go else
             Primary('Start', disabled=True, id='start-go', type='button', hidden=bool(r.ask), rank=6, data_act='start'))   # off until it can start; a question: its answers start
    drop = (FOUND if shown and ok else 'abhyasa gets it only when you press Start.' if go and r.kind in ('paper', 'repo', 'site') else CAN)
    foot = Div(start, Quiet('Find concepts only', hx_post=Routes.base, hx_target='#walk-out', data_wait='Reading and finding concepts…', data_skel='#walk-out')
               if 'find' in r.options else '', '' if shown else Pick(), Span(drop, cls='start-drop'), cls='foot')   # the chooser is beside the field when the field shows
    line = P(NO_GOAL, cls='will', id='start-will') if r.kind == 'empty' and cs else Line(r) if r.kind != 'ask' else P(B(r.ask.q), cls='will', id='start-will')
    return (line, P(WEB_ONCE + ('' if shown else OFF), cls='mute web-once') if r.kind in ('topic', 'goal') and val('research.on') and not told else '',
            Ask(r, cs[0].path if cs else q) if r.ask else Options(r, f), Chips(cs, said) if shown else '', foot)

def connect(app, ctx):
    lr = ctx.learning
    ask = ctx.ask   # the engine picks the model of each task (`for_task`) on each call, so a settings change works at once

    known = AttrDict(key=None, at=0, names={}, disk={}, busy=set())   # the folder names under `sources.roots`, what one folder holds, and the refreshes on the pool

    def later(what, f):
        "Run `f` on the pool, one at a time for each `what`. The request goes on with the old value."
        if what in known.busy: return
        known.busy.add(what)
        def go():
            try: f()
            finally: known.busy.discard(what)
        ctx.pool.submit(go)

    def read_names(key): known.update(key=key, at=time.time(), names=folder_names(key))

    def names():
        "The folder names under `sources.roots`, two levels down. A change of the setting reads them at once; after `NAMES_FOR` seconds the pool reads them again."
        key = tuple(roots())
        if known.key != key: read_names(key)
        elif time.time() - known.at > NAMES_FOR: later('names', lambda: read_names(key))
        return known.names

    def count(p):
        fs = tree_files(p)
        known.disk[p] = (time.time(), d := dict(notebooks=sum(x.suffix == '.ipynb' for x in fs), files=len(fs), repo=(Path(p)/'.git').exists()))
        return d

    def disk(p):
        "What the folder `p` holds, for the folder line: the notebooks and the files, if it is a repo, or why abhyasa does not file it. An old count is read again on the pool."
        if why := folder_why(p): return dict(why=why)
        if not (got := known.disk.get(p)): return count(p)
        if time.time() - got[0] > DISK_FOR: later(p, lambda: count(p))
        return got[1]

    def reading(q, pick='', file='', pages='', doc='', extra=(), drop=()):
        "The reading of the box, and its chips: the sources that the text names, and the ones that you added (`extra`), less the ones that you removed (`drop`)."
        p = max(1, min(int(pages), val('links.cap'))) if str(pages).strip().isdigit() else val('links.pages')   # the line says what the walk reads
        t = vault_title(lr.vault, q) if not file else None
        nm, rv, s = names(), vault_roots(lr), q.strip()
        path = (s if s.startswith(('/', '~')) and '\n' not in s else str((nm.get(fold(s)) or [''])[0]) if ' ' not in s else '')
        counts = {str(Path(path).expanduser()): disk(str(Path(path).expanduser()))} if path else None
        docs = dict(title_index(lr.vault).values())
        r = detect(q, dict([t]) if t else {}, research=val('research.on'), pages=p, file=file, pick=pick, doc=doc, names=nm, roots_in_vault=rv, counts=counts, docs=docs)
        said, more = [], []
        for e in (x.strip() for x in extra if x.strip()):
            if e.startswith('doc:'):   # a dropped file, filed in the vault
                if d := lr.vault.doc(e[4:]): more.append(AttrDict(kind='doc', name=d['title'], path='', count=None, filed=True, id=e))
                continue
            got = named_sources(e, docs, nm, rv)
            more += got
            if not got: said.append(f'abhyasa cannot use {e[:80]} as a source. Add the path of a folder, owner/name of a GitHub repo, or a link.')
        cs = {c.id: c for c in [*(r.chips if r.kind in ('goal', 'sources') else ()), *more] if c.id not in drop}
        cs = on_disk(list(cs.values()))
        if r.kind == 'goal' or (more and r.kind == 'topic'): r = _goal(s, cs, val('research.on'))   # the line follows the chips; a topic with sources that you added is a goal
        elif r.kind in ('sources', 'empty'): r = AttrDict(r, chips=cs)
        return r, said

    def Doc(r, file='', doc='', oob=False):
        "The id of the vault document that Start uses: the dropped PDF, or the document that the question names."
        v = doc if file else ((r.ask or {}).get('doc') or '')
        return Input(type='hidden', name='doc', value=v, id='start-doc', **({'hx_swap_oob': 'true'} if oob else {}))

    def Box(q='', file='', doc=''):
        "The Start box. The read part comes from `/learn/read` after 250 ms with no typing (start.js)."
        return Form(Label('What do you want to learn?', fr='start-q'),
                    Textarea(q, name='q', id='start-q', rows=2, data_mic='label', aria_describedby='start-will'),
                    Input(type='hidden', name='file', value=file, id='start-file'), Say(r := reading(q, file=file, doc=doc)[0]), Doc(r, file, doc),
                    Div(id='start-keep', hidden=True),   # the sources that you added (`extra`) and removed (`drop`): start.js keeps them over each read
                    Div(*Read(r, told=val('research.told'), q=q), id='start-read', data_quiet='1'),
                    P(CUE, cls='drop-cue', aria_hidden='true'),   # shows only while you drag files over the box (start.js, add.css)
                    hx_post='/walk/new', hx_target='#walk-out', id='start-form', cls='start raised', data_read=Routes.read, data_drop=Routes.file, data_drops=Routes.files, data_pick=Routes.pick)

    def read(q:str='', pick:str='', file:str='', pages:str='', tool:str='', title:str='', subject:str='', opts:str='', doc:str='',
             extra:list[str]=None, drop:list[str]=None):
        f = dict(pages=pages, title=title, subject=subject, **({'tool': tool or 'off'} if 'tool' in opts.split(',') else {}))   # the box was shown and you set it
        r, said = reading(q, pick, file, pages, doc, extra or (), set(drop or ()))
        return (*Read(r, f, told=val('research.told'), q=q, said=said), Say(r, oob=True), Doc(r, file, doc, oob=True))

    async def keep_drop(f, kinds=('.pdf',)):
        "File the dropped file `f` in the vault on the pool: `(doc, stem, name)`, or `(None, line, name)` with what went wrong."
        name, most = Path(f.filename or 'dropped.pdf').name, DROP_MB * 2**20
        big, ext = f'This file is too big. The most is {DROP_MB} MB.', Path(name).suffix.lower()
        if ext not in kinds: return None, 'Drop a PDF, a .md or a .txt file.', name
        if f.size is not None and f.size > most: return None, big, name
        data = await f.read(most + 1)   # never more than the limit in memory
        if len(data) > most: return None, big, name
        if ext == '.pdf' and b'%PDF-' not in data[:1024]: return None, 'This file is not a PDF.', name
        stem = Path(name).stem.strip() or 'dropped'
        safe = re.sub(r'[^\w.-]+', '-', stem)[:80]
        p = Path(lr.vault.assets('drops'))/f'{hashlib.sha1(data).hexdigest()[:10]}-{safe}{ext}'   # one file for each content: a second drop never writes over the first
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists(): p.write_bytes(data)
        fut = ctx.pool.submit(lr.vault.pdf, str(p), title=stem) if ext == '.pdf' else ctx.pool.submit(lr.vault.add_file, str(p), title=stem)
        try: d = await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(fut)), DROP_WAIT)
        except asyncio.TimeoutError: return None, STILL, name   # `shield`: the pool job goes on
        except Exception as e:
            log.warning('abhyasa could not file the dropped file: %r', e)
            return None, 'abhyasa could not read this PDF.' if ext == '.pdf' else f'abhyasa could not read {name}.', name
        return d or {}, stem, name

    async def drop(f:UploadFile):
        "A dropped PDF: file it in the vault on the pool, then show the box with its name in it and its id in the form."
        d, stem, name = await keep_drop(f)
        if d is None: return P(stem, cls='req-err')   # `stem` is the line that says what went wrong
        return Box(d.get('title') or stem, name, d.get('doc_id') or d.get('id') or '')

    async def drops(fs:list[UploadFile]):
        "Several dropped files: file each one in the vault. The ids go back to start.js, which adds each one as a source of the goal."
        ids, said = [], []
        for f in fs[:DROP_MOST]:
            d, stem, name = await keep_drop(f, ('.pdf', '.md', '.txt'))
            if d is None: said.append(f'{name}: {stem}')
            elif i := d.get('doc_id') or d.get('id'): ids.append(f'doc:{i}')
        if len(fs) > DROP_MOST: said.append(f'abhyasa adds at most {DROP_MOST} files in one drop.')
        return JSONResponse(dict(ids=ids, said=said))

    async def pick(req):
        "Open the folder chooser of this Mac, for a click in the box. The paths go back to start.js, which adds each one as you add a typed path."
        if not can_pick() or (req.client.host if req.client else '') not in LOCAL_HOSTS: return Response(NOT_HERE, status_code=403)
        return JSONResponse(dict(paths=await asyncio.to_thread(choose_folder)))

    def add(subject:str='', text:str='', ref:str='', q:str=''):
        text = text or q   # the Start box sends its text as `q`
        if not (text.strip() or ref.strip()): return P('Paste text or name a document.', cls='mute')
        try: slugs = from_vault(lr, ask, ref, subject) if ref.strip() else extract(lr, ask, text, subject, dict(src='pasted', at=time.time()))
        except ValueError as e:
            if not ref.strip(): return P(str(e), cls='mute')
            log.warning('no concepts from the vault: %r', e)
            return P(NO_DOC, cls='mute')
        run_hook('concepts_added')   # the concepts block places the new concepts on the pool
        return Ul(*[Li(A(lr.concept(s).name, href=f'/c/{s}')) for s in slugs], cls='plain')

    def page(): return RedirectResponse(Routes.start, status_code=303)   # the old Add page: the Start box on Home has its place

    def Filing(j, said=(), told=()):
        "What Add a source does now for walk `j`: each source that is still filing, and the lines of the last add. It asks again while a source files."
        fs = j.get('filing') or ()
        rows = [P(f"Filing {i.partition(':')[2].rstrip('/').split('/')[-1]}…", cls='mute') for i in fs]
        poll = dict(hx_get=f'{Routes.walk_source}?{urlencode(dict(jid=j.id))}', hx_trigger='every 3s', hx_swap='outerHTML') if fs else {}
        return Div(*rows, *[P(x, cls='mute') for x in told], *[P(x, cls='req-err') for x in said], id='walk-src-out', **poll)

    def keep_mine(j, cs, note, said) -> list:
        "Keep each folder in `cs` as your data: on the course of walk `j` and its walks, else on the walk. Nothing is filed. The lines to show."
        told, c = [], course_of(lr, j.id)
        for x in cs:
            if x.kind != 'folder' or not x.path: said.append(f'{x.name}: {DATA_ONLY}'); continue
            try:
                if c: add_data(lr, c.id, x.path, note)
                else: lr.merge_journey(j.id, data=keep_data((lr.journey(j.id) or j).get('data'), x.path, note))
                told.append(KEPT.format(x.name))
            except ValueError as e: said.append(f'{x.name}: {e}')
        return told

    @hook('walk_plan_more')
    def more_sources(j):
        "Add a source, in the sources of each walk: the same parts as the Start box. abhyasa files each source on its own job."
        return Div(H3('Add a source'), P(MORE, cls='mute'),
                   Form(Input(type='hidden', name='jid', value=j.id),
                        Input(type='text', name='q', id='walk-src-q', placeholder='Add a folder, a repo or a link', aria_label='Add a folder, a repo or a link', autocomplete='off'),
                        Button('Add', cls='quiet small', id='walk-src-go'),
                        Button(PICK, type='submit', name='pick', value='1', cls='quiet small', id='walk-src-pick') if can_pick() else '', Use(),
                        hx_post=Routes.walk_source, hx_target='#walk-src-out', hx_swap='outerHTML', cls='addf', id='walk-src-form', data_act='add-source'),
                   Filing(j), asset_css(_P/'add.css'), cls='walk-src')

    async def walk_source(req, jid:str, q:str='', pick:str='', use:str='learn', note:str=''):
        """Add the sources in `q` (or the folders that you pick) to walk `jid`: one chip for each, with the checks of the Start box. The walk block files each one.
        With `use=data`, each folder is your data, with `note`: it is kept on the course and the walk, and it is not filed."""
        if not (j := lr.journey(jid)): return Response(status_code=404)
        said, qs = [], [q] if q.strip() else []
        if pick:
            if not can_pick() or (req.client.host if req.client else '') not in LOCAL_HOSTS: said.append(NOT_HERE)
            else: qs += await asyncio.to_thread(choose_folder)
        found = [c for x in qs for c in named_sources(x, dict(title_index(lr.vault).values()), names(), vault_roots(lr))]
        if q.strip() and not found: said.append(f'abhyasa cannot use {q.strip()[:80]} as a source. Add the path of a folder, owner/name of a GitHub repo, or a link.')
        if use == 'data': return Filing(lr.journey(jid) or j, said, keep_mine(j, found, note, said))
        cs = on_disk(found)
        said[:0] = [f'{c.name}: {c.why}' for c in cs if c.get('why')]
        run_hook('walk_add_sources', jid, [c.id for c in cs if not c.get('why')])   # the walk block files each one on its own job
        return Filing(lr.journey(jid) or j, said)

    def walk_filing(jid:str):
        "The filing line of walk `jid`, asked again while a source files. A GET only reads."
        return Filing(j) if (j := lr.journey(jid)) else Response(status_code=404)

    later('names', lambda: read_names(tuple(roots())))   # read the folder names one time, before the first read of the box

    @hook('learn_start')
    def start():
        "Start something new, on Home: the box and the place for its result."
        return Box(), Div(id='walk-out'), asset_css(_P/'add.css'), asset_js(_P/'start.js', defer=True)

    app.get(Routes.base)(page)
    app.post(Routes.base)(add)
    app.get(Routes.read)(read)
    app.post(Routes.file)(drop)
    app.post(Routes.files)(drops)
    app.post(Routes.pick)(pick)
    app.post(Routes.walk_source)(walk_source)
    app.get(Routes.walk_source)(walk_filing)
