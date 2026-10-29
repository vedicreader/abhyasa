"""Start something new, in Learn: one box that reads what you paste or drop and says what abhyasa will do (`detect`).
Also Find concepts only (`POST /add`), and the vedicreader import."""
import logging, re, time
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
WAIT = dict(paper='Reading the paper…', repo='Getting the repository…', site='Getting the pages from the link…', topic='Planning the walk…')
CHIP = dict(paper='paper', repo='repo', site='site', doc='vault', topic='topic', text='text')
NOT_YET = ('video', 'local', 'folder', 'sources')   # Start stays off: the line says why
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
    if 'pages' in o: c.append(Label('Pages to read', Input(type='number', name='pages', min=1, max=val('links.cap'), value=f.get('pages') or val('links.pages'))))
    if 'tool' in o: c.append(Label(Input(type='checkbox', name='tool', checked=f.get('tool', 'on') == 'on'), ' It is a library or a command-line tool', cls='tick'))
    if 'title' in o: c.append(Label('Title', Input(type='text', name='title', value=f.get('title') or r.send.get('title', ''), placeholder='optional')))
    if 'subject' in o: c.append(Label('Subject', Input(type='text', name='subject', value=f.get('subject', ''), placeholder='optional, for example: ml, sanskrit')))
    return Div(*c, Input(type='hidden', name='opts', value='1'), cls='opts') if c else ''

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

    def reading(q, pick='', file='', pages=''):
        p = int(pages) if str(pages).strip().isdigit() else val('links.pages')
        t = vault_title(lr.vault, q) if not file else None
        return detect(q, (t,) if t else (), research=val('research.on'), pages=p, file=file, pick=pick)

    def Box(q='', file=''):
        "The Start box. The read part comes from `/learn/read` after 250 ms with no typing (start.js)."
        return Form(Label('Paste a link, a paper, a topic, a file name or some text', fr='start-q'),
                    Textarea(q, name='q', id='start-q', rows=2, data_mic='label', aria_describedby='start-will'),
                    Input(type='hidden', name='file', value=file, id='start-file'), Say(r := reading(q, file=file)),
                    Div(*Read(r, told=val('research.told')), id='start-read', data_quiet='1'),
                    hx_post='/walk/new', hx_target='#walk-out', id='start-form', cls='start raised', data_read=Routes.read, data_drop=Routes.file)

    def read(q:str='', pick:str='', file:str='', pages:str='', tool:str='', title:str='', subject:str='', opts:str=''):
        f = dict(pages=pages, title=title, subject=subject, **({'tool': tool or 'off'} if opts else {}))
        r = reading(q, pick, file, pages)
        return (*Read(r, f, told=val('research.told')), Say(r, oob=True))

    async def drop(f:UploadFile):
        "A dropped PDF: file it in the vault on the pool, then show the box with its name in it."
        name = Path(f.filename or 'dropped.pdf').name
        if not name.lower().endswith('.pdf'): return P('Drop a PDF, a .md or a .txt file.', cls='req-err')
        data = await f.read()
        if len(data) > DROP_MB * 2**20: return P(f'This file is too big. The most is {DROP_MB} MB.', cls='req-err')
        p = Path(lr.vault.assets('drops'))/re.sub(r'[^\w.-]+', '-', name)
        p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
        try: d = ctx.pool.submit(lr.vault.pdf, str(p), title=p.stem).result()
        except Exception as e:
            log.warning('abhyasa could not file the dropped PDF: %r', e)
            return P('abhyasa could not read this PDF.', cls='req-err')
        return Box((d or {}).get('title') or p.stem, name)

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
