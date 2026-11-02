import json, time
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import Md, asset_css, DepthBar, Primary, Quiet, doc_title, SourceLinks
from .cfg import Routes

_P = Path(__file__).parent
RAMA = Path.home()/'.config/ramabana'

def css(): return asset_css(_P/'vault.css')

def when(t):
    "A date for an epoch time, or for a `YYYY-MM-DD hh:mm:ss` string."
    if isinstance(t, (int, float)): return time.strftime('%d %b %Y, %H:%M', time.localtime(t))
    try: return time.strftime('%d %b %Y', time.strptime(str(t)[:19], '%Y-%m-%d %H:%M:%S'))   # a stored date reads as a date, not a time stamp
    except ValueError: return str(t or '')

def memory_file(source):
    "The real file behind a ramabana memory document, if it is on this machine."
    ref = source.removeprefix('ramabana://')
    p = RAMA/(f'{ref}/MEMORY.md' if ref.startswith('memory/') else f'{ref}/SKILL.md' if ref.startswith('learned/skills/') else ref)
    return p if p.exists() else None

def Facts(d, meta):
    "One quiet line: the kind of document, its dates and where it came from."
    kind, src = d['kind'], d['source'] or ''
    bits = ['walk' if kind == 'journey' else kind]   # the stored kind stays
    if kind == 'session':
        bits += [f"{meta.get('turns', '?')} turns", when(meta.get('last_at') or meta.get('first_at')), meta.get('model', '')]
        if meta.get('roots'): bits.append(', '.join(meta['roots']))
    else: bits.append(when(d.get('added_at')))
    return P(' · '.join(b for b in bits if b), cls='mute')

def Actions(d, meta, shelf, leela=''):
    "What you can do with this document: resume a session, open a file or a page, open a notebook in Leela (`leela`), or learn from it: as a walk (the main button), or only find its ideas."
    src, out = d['source'] or '', [leela] if leela else []
    if d['kind'] == 'session' and (sid := meta.get('session')):
        cmd = f'ramabana --resume {sid}'
        out.append(Button('Copy the resume command', type='button', cls='btn', onclick=f"navigator.clipboard.writeText({json.dumps(cmd)}); this.textContent='Copied'"))
        out.append(Code(cmd, cls='cmd'))
    if src.startswith(('http://', 'https://')): out.append(A('Open the page', href=src, cls='btn'))
    if (f := memory_file(src)) or (src.startswith('/') and Path(src).exists() and (f := Path(src))):
        out.append(Code(str(f), cls='cmd'))
    out.append(Primary('Learn as a walk', key=None, hx_post='/walk/new', hx_vals=json.dumps(dict(shelf=shelf, ref=d['id'])), hx_target='#learned',
                       title='One idea at a time, in the order of the document', data_wait='Making the walk…', data_skel='#learned'))
    out.append(Quiet('Only find its ideas', hx_post=Routes.learn.format(shelf=shelf, doc_id=d['id']), hx_target='#learned', title='Add the ideas of the document to your concepts, with no walk',
                     data_wait='Reading the document…', data_skel='#learned'))
    return Div(*out, cls='row actions')

def Linked(cs):
    "The concepts whose links point at this document."
    if not cs: return P('No concept links here yet.', cls='mute')
    return Ul(*[Li(A(c.name, href=f'/c/{c.slug}'), DepthBar(c.floor), Span(f'  {c.subject}', cls='mute')) for c in cs], cls='plain')

def Thread(turns):
    "The conversation on one question, as the tutor and you had it."
    if not turns: return ()
    def turn(t):
        who = 'You' if t['who'] == 'you' else {'question': 'Question', 'nudge': 'Not yet', 'hint': 'Hint', 'close': (t.get('outcome') or 'Outcome').title()}.get(t.get('kind'), 'Tutor')
        return Li(Span(who, cls='lbl'), Md('\n\n'.join(x for x in (t.get('text'), t.get('lesson')) if x)),
                  Div(Span('Thinking: ', cls='k'), Md(t['thinking']), cls='mute') if t.get('thinking') else '', cls=f"turn {t['who']}")
    return H2('The conversation'), Ul(*map(turn, turns), cls='plain thread-doc')

def Transcript(tx):
    "The head of a lecture transcript: its links (the lesson notebook, the summary, the video), then its topics, each a jump to the paragraph where it starts."
    where = 'from the summary' if tx.where == 'summary' else 'from the ideas of your walks'
    topics = (H2(f'Topics, {where}'), Ol(*[Li(A(t, href=f'#tp{k}')) for t, k in tx.topics], cls='topics')) if tx.topics else ()
    return Div(SourceLinks(tx.links, cls='src-links tx-links'), *topics, cls='transcript-head')

def Paras(tx, kind):
    "The text of a transcript in its paragraphs, each with an id that a topic jumps to."
    return Div(*[Md(p, id=f'tp{k}') for k, p in enumerate(tx.paras)], cls=f'doc {kind} transcript')

def DocPage(d, meta, text, shelf, linked, imgs=(), tx=None, leela=''):
    """The document page; `imgs` are the image links of the text that the page sends. `tx` (`transcript_page`): the page of a lecture transcript, with its links, its topics and its paragraphs.
    `leela` is Open in Leela, for a notebook."""
    lbl = Span('Your vault' if shelf == 'store' else f'Your vault · {shelf}', cls='lbl')
    return (css(), lbl, *((Span(tx.title, cls='lbl tx-title'),) if tx else ()), H1(doc_title(d['title']) or d['id']), Facts(d, meta), *((Transcript(tx),) if tx else ()), Actions(d, meta, shelf, leela),
            Div(id='learned'), *Thread(meta.get('thread')), *((H2('Concepts linked here'), Linked(linked)) if linked else ()),
            H2('Text'), Paras(tx, d['kind']) if tx else Md(doc_title(text), cls=f"doc {d['kind']}", imgs=imgs))
