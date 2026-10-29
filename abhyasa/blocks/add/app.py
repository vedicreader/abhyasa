"""Start something new, in Learn: one box that reads what you paste or drop and says what abhyasa will do (`detect`).
Also Find concepts only (`POST /add`), and the vedicreader import."""
import asyncio, hashlib, logging, re, time
from fasthtml.common import *
from pathlib import Path
from abhyasa.core import hook, run as run_hook, Primary, Secondary, Quiet, Pill, asset_css, asset_js, n_of
from abhyasa.sources import extract, from_vault, from_vedicreader, folder_why, tree_files, vault_roots
from abhyasa.settings import val, roots
from abhyasa.detect import detect, vault_title, title_index, folder_names, named_sources, on_disk, fold, _goal
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask', 'pool')
_P = Path(__file__).parent
NO_DOC = 'No document in your vault has this name. To add a web page or a paper, paste its link.'
WEB_ONCE = 'The tutor will search the web for sources. Your topic goes to the search. Turn this off in Settings.'
DROP_MB = 50
DROP_WAIT = 60   # seconds that a drop waits for the vault to read the PDF; then the pool goes on and the request answers
STILL = 'abhyasa is still reading this PDF. It shows in your vault when it is done.'
WAIT = dict(paper='Reading the paper…', repo='Getting the repository…', site='Getting the pages from the link…', topic='Planning the walk…',
            goal='Planning the walk…', sources='Filing the sources…')
CHIP = dict(paper='paper', repo='repo', site='site', doc='vault', topic='topic', text='text', goal='goal', sources='sources', folder='folder')
NOT_YET = ('video', 'local', 'file_name')   # Start stays off: the line says why
FOUND = 'abhyasa found these by their names, on this Mac and in your vault. It has read nothing from the web yet.'
NO_GOAL = 'Write your goal in the box. abhyasa uses the sources below.'
NAMES_FOR, DISK_FOR = 300, 60   # seconds that the folder names, and the count of files in one folder, are kept
STATE = dict(gh='a GitHub repo · cloned when you press Start', folder='a folder on this Mac · added when you press Start',
             repo='a repo on this Mac · added when you press Start', link='a link · read when you press Start', vedic='on this Mac', doc='in your vault')
log = logging.getLogger(__name__)

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
    else: where, st = dict(folder=_home(c.path), repo=_home(c.path), gh=c.path, link=c.path, vedic='the Ramayana episodes').get(c.kind, ''), STATE.get(c.kind, '')
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
                   Button('Add', type='button', cls='quiet small', id='start-add-go'), cls='addf'),
               Input(type='hidden', name='chips', value='1'), cls='chips-src', aria_label='Sources for this goal')

def Read(r, f=None, told=True, q='', said=()):
    "What the box will do: the quiet line, the question or the options, the sources of a goal, and the Start button."
    f, cs = f or {}, r.get('chips') or []
    shown = r.kind in ('goal', 'sources') or (r.kind == 'empty' and cs)
    ok = [c for c in cs if not c.get('why')]
    go = r.kind not in ('empty', 'ask', *NOT_YET) and not r.ask and bool(r.send) and (r.kind != 'sources' or bool(ok))
    wait = WAIT.get(r.kind, 'Making the walk…')
    start = (Primary('Start', data_wait=wait, data_skel='#walk-out', id='start-go') if go else
             Button('Start', ' ', Kbd('⌥S'), disabled=True, id='start-go', type='button', hidden=bool(r.ask)))   # a question: its answers start
    drop = (FOUND if shown and ok else 'abhyasa gets it only when you press Start.' if go and r.kind in ('paper', 'repo', 'site') else 'You can also drop a file here.')
    foot = Div(start, Quiet('Find concepts only', hx_post=Routes.base, hx_target='#walk-out', data_wait='Reading and finding concepts…', data_skel='#walk-out')
               if 'find' in r.options else '', Span(drop, cls='start-drop'), cls='foot')
    line = P(NO_GOAL, cls='will', id='start-will') if r.kind == 'empty' and cs else Line(r) if r.kind != 'ask' else P(B(r.ask.q), cls='will', id='start-will')
    return (line, P(WEB_ONCE, cls='mute web-once') if r.kind in ('topic', 'goal') and val('research.on') and not told else '',
            Ask(r, cs[0].path if cs else q) if r.ask else Options(r, f), Chips(cs, said) if shown else '', foot)

def connect(app, ctx):
    lr = ctx.learning
    ask = ctx.ask   # the engine picks the model of each task (`for_task`) on each call, so a settings change works at once

    known = AttrDict(key=None, at=0, names={}, disk={})   # the folder names under `sources.roots`, and what one folder holds

    def names():
        "The folder names under `sources.roots`, two levels down. Read again when the setting changes, or after `NAMES_FOR` seconds."
        key = tuple(roots())
        if known.key != key or time.time() - known.at > NAMES_FOR: known.update(key=key, at=time.time(), names=folder_names(key))
        return known.names

    def disk(p):
        "What the folder `p` holds, for the folder line: the notebooks and the files, if it is a repo, or why abhyasa does not file it."
        if why := folder_why(p): return dict(why=why)
        if (got := known.disk.get(p)) and time.time() - got[0] < DISK_FOR: return got[1]
        fs = tree_files(p)
        known.disk[p] = (time.time(), d := dict(notebooks=sum(x.suffix == '.ipynb' for x in fs), files=len(fs), repo=(Path(p)/'.git').exists()))
        return d

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
        return Form(Label('Paste a link, a paper, a topic, a file name or some text', fr='start-q'),
                    Textarea(q, name='q', id='start-q', rows=2, data_mic='label', aria_describedby='start-will'),
                    Input(type='hidden', name='file', value=file, id='start-file'), Say(r := reading(q, file=file, doc=doc)[0]), Doc(r, file, doc),
                    Div(id='start-keep', hidden=True),   # the sources that you added (`extra`) and removed (`drop`): start.js keeps them over each read
                    Div(*Read(r, told=val('research.told'), q=q), id='start-read', data_quiet='1'),
                    hx_post='/walk/new', hx_target='#walk-out', id='start-form', cls='start raised', data_read=Routes.read, data_drop=Routes.file)

    def read(q:str='', pick:str='', file:str='', pages:str='', tool:str='', title:str='', subject:str='', opts:str='', doc:str='',
             extra:list[str]=None, drop:list[str]=None):
        f = dict(pages=pages, title=title, subject=subject, **({'tool': tool or 'off'} if 'tool' in opts.split(',') else {}))   # the box was shown and you set it
        r, said = reading(q, pick, file, pages, doc, extra or (), set(drop or ()))
        return (*Read(r, f, told=val('research.told'), q=q, said=said), Say(r, oob=True), Doc(r, file, doc, oob=True))

    async def drop(f:UploadFile):
        "A dropped PDF: file it in the vault on the pool, then show the box with its name in it and its id in the form."
        name, most = Path(f.filename or 'dropped.pdf').name, DROP_MB * 2**20
        big = P(f'This file is too big. The most is {DROP_MB} MB.', cls='req-err')
        if not name.lower().endswith('.pdf'): return P('Drop a PDF, a .md or a .txt file.', cls='req-err')
        if f.size is not None and f.size > most: return big
        data = await f.read(most + 1)   # never more than the limit in memory
        if len(data) > most: return big
        if b'%PDF-' not in data[:1024]: return P('This file is not a PDF.', cls='req-err')
        stem = Path(name).stem.strip() or 'dropped'
        safe = re.sub(r'[^\w.-]+', '-', stem)[:80]
        p = Path(lr.vault.assets('drops'))/f'{hashlib.sha1(data).hexdigest()[:10]}-{safe}.pdf'   # one file for each content: a second drop never writes over the first
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists(): p.write_bytes(data)
        fut = ctx.pool.submit(lr.vault.pdf, str(p), title=stem)
        try: d = await asyncio.wait_for(asyncio.shield(asyncio.wrap_future(fut)), DROP_WAIT)
        except asyncio.TimeoutError: return P(STILL, cls='req-err')   # `shield`: the pool job goes on
        except Exception as e:
            log.warning('abhyasa could not file the dropped PDF: %r', e)
            return P('abhyasa could not read this PDF.', cls='req-err')
        d = d or {}
        return Box(d.get('title') or stem, name, d.get('doc_id') or d.get('id') or '')

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

    def page(): return RedirectResponse(Routes.start, status_code=303)   # the old Add page: the Start box in Learn has its place

    def vedicreader(): return P(', '.join(f'{v} {k}' for k, v in from_vedicreader(lr).items()) + ' added.')

    ctx.pool.submit(names)   # read the folder names one time, before the first read of the box

    @hook('learn_start')
    def start():
        "Start something new, in Learn: the box, the place for its result, and More (`start_more`: the goal box of the walks block)."
        return (Box(), Div(id='walk-out'), Details(Summary('More'), *run_hook('start_more'), cls='more start-more'),
                asset_css(_P/'add.css'), asset_js(_P/'start.js', defer=True))

    app.get(Routes.base)(page)
    app.post(Routes.base)(add)
    app.get(Routes.read)(read)
    app.post(Routes.file)(drop)
    app.post(Routes.vedicreader)(vedicreader)
