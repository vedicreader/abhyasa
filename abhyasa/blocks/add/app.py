"""Start something new, in Learn: one box that reads what you paste or drop and says what abhyasa will do (`detect`).
Also Find concepts only (`POST /add`), and the vedicreader import."""
import asyncio, hashlib, logging, re, time
from fasthtml.common import *
from pathlib import Path
from abhyasa.core import hook, run as run_hook, Primary, Secondary, Quiet, Pill, asset_css, asset_js
from abhyasa.sources import extract, from_vault, from_vedicreader
from abhyasa.settings import val
from abhyasa.detect import detect, vault_title
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'ask', 'pool')
_P = Path(__file__).parent
NO_DOC = 'No document in your vault has this name. To add a web page or a paper, paste its link.'
WEB_ONCE = 'The tutor will search the web for sources. Your topic goes to the search. Turn this off in Settings.'
DROP_MB = 50
DROP_WAIT = 60   # seconds that a drop waits for the vault to read the PDF; then the pool goes on and the request answers
STILL = 'abhyasa is still reading this PDF. It shows in your vault when it is done.'
WAIT = dict(paper='Reading the paper…', repo='Getting the repository…', site='Getting the pages from the link…', topic='Planning the walk…')
CHIP = dict(paper='paper', repo='repo', site='site', doc='vault', topic='topic', text='text')
NOT_YET = ('video', 'local', 'folder', 'sources', 'file_name')   # Start stays off: the line says why
log = logging.getLogger(__name__)

def Line(r):
    "The quiet line: a small chip with the kind, the first sentence in bold, then the rest."
    if r.kind == 'empty': return P(r.line, cls='will', id='start-will')   # the hint stays quiet
    head, _, rest = r.line.partition('. ')
    return P(Pill(CHIP[r.kind]) if r.kind in CHIP else '', ' ' if r.kind in CHIP else '',
             B(head + ('.' if rest else '')), (' ' + rest) if rest else '', cls='will', id='start-will')

def Ask(r):
    "One question with two answers. Each answer starts at once: the first is the main button."
    (la, ka), (lb, kb) = r.ask.a, r.ask.b
    return Div(Primary(la, name='pick', value=ka, data_wait='Making the walk…', data_skel='#walk-out'),
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

def Read(r, f=None, told=True):
    "What the box will do: the quiet line, the question or the options, and the Start button."
    f = f or {}
    go = r.kind not in ('empty', 'ask', *NOT_YET)
    wait = WAIT.get(r.kind, 'Making the walk…')
    start = (Primary('Start', data_wait=wait, data_skel='#walk-out', id='start-go') if go else
             Button('Start', ' ', Kbd('⌥S'), disabled=True, id='start-go', type='button', hidden=r.kind == 'ask'))   # a question: its answers start
    foot = Div(start, Quiet('Find concepts only', hx_post=Routes.base, hx_target='#walk-out', data_wait='Reading and finding concepts…', data_skel='#walk-out')
               if 'find' in r.options else '',
               Span('abhyasa gets it only when you press Start.' if go and r.kind in ('paper', 'repo', 'site') else 'You can also drop a file here.', cls='start-drop'), cls='foot')
    return (Line(r) if r.kind != 'ask' else P(B(r.ask.q), cls='will', id='start-will'),
            P(WEB_ONCE, cls='mute web-once') if r.kind == 'topic' and val('research.on') and not told else '',
            Ask(r) if r.kind == 'ask' else Options(r, f), foot)

def connect(app, ctx):
    lr = ctx.learning
    ask = ctx.ask   # the engine picks the model of each task (`for_task`) on each call, so a settings change works at once

    def reading(q, pick='', file='', pages='', doc=''):
        p = max(1, min(int(pages), val('links.cap'))) if str(pages).strip().isdigit() else val('links.pages')   # the line says what the walk reads
        t = vault_title(lr.vault, q) if not file else None
        return detect(q, dict([t]) if t else {}, research=val('research.on'), pages=p, file=file, pick=pick, doc=doc)

    def Doc(r, file='', doc='', oob=False):
        "The id of the vault document that Start uses: the dropped PDF, or the document that the question names."
        v = doc if file else ((r.ask or {}).get('doc') or '')
        return Input(type='hidden', name='doc', value=v, id='start-doc', **({'hx_swap_oob': 'true'} if oob else {}))

    def Box(q='', file='', doc=''):
        "The Start box. The read part comes from `/learn/read` after 250 ms with no typing (start.js)."
        return Form(Label('Paste a link, a paper, a topic, a file name or some text', fr='start-q'),
                    Textarea(q, name='q', id='start-q', rows=2, data_mic='label', aria_describedby='start-will'),
                    Input(type='hidden', name='file', value=file, id='start-file'), Say(r := reading(q, file=file, doc=doc)), Doc(r, file, doc),
                    Div(*Read(r, told=val('research.told')), id='start-read', data_quiet='1'),
                    hx_post='/walk/new', hx_target='#walk-out', id='start-form', cls='start raised', data_read=Routes.read, data_drop=Routes.file)

    def read(q:str='', pick:str='', file:str='', pages:str='', tool:str='', title:str='', subject:str='', opts:str='', doc:str=''):
        f = dict(pages=pages, title=title, subject=subject, **({'tool': tool or 'off'} if 'tool' in opts.split(',') else {}))   # the box was shown and you set it
        r = reading(q, pick, file, pages, doc)
        return (*Read(r, f, told=val('research.told')), Say(r, oob=True), Doc(r, file, doc, oob=True))

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
