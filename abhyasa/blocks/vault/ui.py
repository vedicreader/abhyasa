import json, time
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import Md, asset_css, DepthBar
from .cfg import Routes

_P = Path(__file__).parent
RAMA = Path.home()/'.config/ramabana'

def css(): return asset_css(_P/'vault.css')

def when(t):
    "A date for an epoch time, or for a `YYYY-MM-DD hh:mm:ss` string."
    if isinstance(t, (int, float)): return time.strftime('%d %b %Y, %H:%M', time.localtime(t))
    return str(t or '')

def memory_file(source):
    "The real file behind a ramabana memory document, if it is on this machine."
    ref = source.removeprefix('ramabana://')
    p = RAMA/(f'{ref}/MEMORY.md' if ref.startswith('memory/') else f'{ref}/SKILL.md' if ref.startswith('learned/skills/') else ref)
    return p if p.exists() else None

def Facts(d, meta):
    "One quiet line: the kind of document, its dates and where it came from."
    kind, src = d['kind'], d['source'] or ''
    bits = [kind]
    if kind == 'session':
        bits += [f"{meta.get('turns', '?')} turns", when(meta.get('last_at') or meta.get('first_at')), meta.get('model', '')]
        if meta.get('roots'): bits.append(', '.join(meta['roots']))
    else: bits.append(when(d.get('added_at')))
    return P(' · '.join(b for b in bits if b), cls='mute')

def Actions(d, meta, shelf):
    "What you can do with this document: resume a session, open a file or a page, or learn from it."
    src, out = d['source'] or '', []
    if d['kind'] == 'session' and (sid := meta.get('session')):
        cmd = f'ramabana --resume {sid}'
        out.append(Button('Copy the resume command', type='button', cls='btn', onclick=f"navigator.clipboard.writeText({json.dumps(cmd)}); this.textContent='Copied'"))
        out.append(Code(cmd, cls='cmd'))
    if src.startswith(('http://', 'https://')): out.append(A('Open the page', href=src, cls='btn'))
    if (f := memory_file(src)) or (src.startswith('/') and Path(src).exists() and (f := Path(src))):
        out.append(Code(str(f), cls='cmd'))
    out.append(Button('Learn from this', cls='go', hx_post=Routes.learn.format(shelf=shelf, doc_id=d['id']), hx_target='#learned', data_wait='Reading the document…', data_skel='#learned'))
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

def DocPage(d, meta, text, shelf, linked):
    return (css(), Span(f'{shelf} shelf', cls='lbl'), H1(d['title'] or d['id']), Facts(d, meta), Actions(d, meta, shelf),
            Div(id='learned'), *Thread(meta.get('thread')), H2('Concepts linked here'), Linked(linked),
            H2('Text'), Md(text, cls=f"doc {d['kind']}"))
