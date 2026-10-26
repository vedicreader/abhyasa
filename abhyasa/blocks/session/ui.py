"The session page as a conversation: each question is a short thread in one scroll, and the composer stays at the bottom."
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import Cites, Md, DepthBar, when, run, asset_css, asset_js
from abhyasa.model import DEPTHS
from abhyasa.tutor import MAX_TRIES
from .cfg import Routes

_P = Path(__file__).parent
OUTCOME = {'solid': 'Solid', 'fragile': 'Right, but shaky', 'misconception': 'A misconception', 'gap': 'A gap'}
WORDS = {1: 'One more try', 2: 'Two more tries'}
STEPS = (10, 30, 50, 70, 90)
GRADING, HINTING, TEACHING, NEXT = 'Grading…', 'Writing a hint…', 'Writing a lesson…', 'Thinking of the next question…'
OPT_KEYS = 'QWER'

def assets(): return asset_css(_P/'session.css'), asset_js(_P/'session.js')

def tl_id(q): return f'tl-{q.id}'

# --- the chat: one section for each question ---------------------------------------------------------------------

def Head(q):
    "The concept and depth as a small label, then why the tutor chose it: the quiet rule between questions."
    return Div(Span(f"{q.name} · {DEPTHS[q.depth]}", DepthBar(q.get('floor', 0), asked=q.depth), cls='lbl'), P(q.why, cls='why'), cls='head')

def Options(sid, q, chosen=(), done=False, oob=False, right=None):
    "The options of a choice question, inline in the question. A wrong pick is struck, a right pick marked; all go off when the question closes."
    def opt(i, o):
        k = OPT_KEYS[i] if i < len(OPT_KEYS) else ''
        return Button(Md(o), Kbd(f'⌥{k}') if k and not done else '', name='answer', value=str(i), id=f'o{i}' if not done else None,
                      cls='opt' + (' right' if o == right else ' tried' if o in chosen else ''), disabled=done or o in chosen,
                      hx_post=Routes.at(Routes.answer, sid), hx_include='#composer', hx_target=f'#{tl_id(q)}', hx_swap='beforeend',
                      data_wait=GRADING, data_skel=f'#{tl_id(q)}')
    return Div(*[opt(i, o) for i, o in enumerate(q.options)], cls='opts', id=f'opts-{q.id}', hx_swap_oob='true' if oob else None)

def Asked(sid, q):
    "The first message of the tutor: the question, with its options for a choice question."
    return Li(Span('Question', cls='lbl'), Md(q.question, cls='q'), Options(sid, q) if q.get('options') else '', cls='m tutor ask')

def Section_(sid, q, entries=()):
    "One question and its thread so far."
    return Section(Head(q), Ol(Asked(sid, q), *entries, id=tl_id(q), cls='thread'), cls='qa', id=f'q-{q.id}')

def Chat(sid, past=(), cur=None, waiting=False):
    "Every question of this sitting in one scroll; the open one last."
    return Div(*[Section_(sid, q, es) for q, es in past], Section_(sid, *cur) if cur else '',
               Waiting(sid) if waiting else '', id='chat', data_sid=sid)

def You(text, thinking='', confidence=None):
    "One message of yours: what you said this time, quoted quietly at the right."
    return Li(Span('You' + (f' · {confidence}% sure' if confidence is not None else ''), cls='lbl'),
              P(text, cls='said') if text else P('No answer.', cls='said none'),
              P(Span('Thinking: ', cls='k'), Span(thinking, cls='pre'), cls='thought') if thinking else '', cls='m you')

def Nudge(r):
    "The tutor's reply to a wrong try: what to look at next, and the first error."
    return Li(Span('Not yet', cls='tag'), Md(r.feedback) if r.feedback else '',
              P(Span('First error: ', cls='k'), r.first_error, cls='err') if r.first_error else '', cls='m tutor fb no')

def Hint(n, text):
    "A hint, at the time you asked for it."
    return Li(Span(f'Hint {n}', cls='lbl'), Md(text), cls='m tutor hint')

def Close(r, said=''):
    "The last message on a question: the outcome, the lesson and the next review."
    fb = r.feedback if r.correct or not r.lesson else ''   # after a miss the lesson speaks; the last nudge would ask a question nobody answers
    return Li(Span(OUTCOME[r.outcome] + (f' · {said}' if said else ''), cls='tag'), Md(fb) if fb else '',
              Div(Span('Lesson', cls='lbl'), Md(r.lesson), cls='lesson') if r.lesson else '',
              Cites(r.get('grounds')),
              P(f"Now: floor {DEPTHS[r.floor]}, next review {when(r.due)}.", cls='mute now'),
              cls=f"m tutor fb close {'ok' if r.correct else 'no'}")

def Skeleton(label):
    "A placeholder question while the model writes it."
    return Div(Div(Span(label, cls='lbl'), cls='head'), Div(I(), I(), I(cls='short'), cls='skel q'), cls='skeleton')

def Waiting(sid):
    "A section that loads the question that is fetched ahead."
    return Section(Skeleton(NEXT), cls='qa waiting', data_wait=NEXT, hx_get=Routes.at(Routes.card, sid), hx_trigger='load', hx_swap='outerHTML')

# --- the composer: fixed at the bottom; its state follows the question -----------------------------------------------

def Confidence():
    "Five steps for how sure you are; ⌥1 to ⌥5 pick one."
    steps = [Label(Input(type='radio', name='confidence', value=v, id=f'c{i + 1}', checked=v == 50), Span(f'{v}%'), title=f'⌥{i + 1}')
             for i, v in enumerate(STEPS)]
    return Div(Span('Sure?', cls='lbl'), *steps, cls='steps', id='conf', role='radiogroup', aria_label='How sure you are')

def Left(n=None, **kw):
    "The tries that are left; empty before the first try."
    return Span(f'{WORDS.get(n, f"{n} more tries")}.' if n else '', id='left', cls='left mute', **kw)

def Composer(sid, q=None, ready=None, oob=False):
    "The bottom bar: your message, your thinking, how sure you are, and the actions. After the close it holds Next."
    at = lambda r: Routes.at(r, sid)
    kw = dict(id='composer', cls='composer', hx_swap_oob='true' if oob else None)
    if q is None:   # closed, or the first question is not written yet
        nxt = Button('Next ', Kbd('⌥S'), cls='go', id='send', hx_post=at(Routes.next), hx_target='#chat', hx_swap='beforeend',
                     data_wait=NEXT, data_skel='#chat', autofocus=True) if ready is not None else ''
        return Div(Div(Ready(sid, ready) if ready is not None else Span('Writing the first question', cls='ready mute wait'),
                       A('End session', href=at(Routes.end), cls='btn quiet'), nxt, cls='row bar'), **kw)
    tl = dict(hx_target=f'#{tl_id(q)}', hx_swap='beforeend', data_skel=f'#{tl_id(q)}')
    tried, out = bool(q.get('tries')), Out(sid, q)
    choice = bool(q.get('options'))
    boxes = ([] if choice else [Textarea(name='answer', id='ans', rows=2, autofocus=True, aria_label='Your answer',
                                         placeholder='Your answer, or a follow-up. ⌘↵ sends.')]) + [
             Textarea(name='thinking', id='think', rows=1, aria_label='Think aloud',
                      placeholder='Think aloud: how did you get there? What are you not sure of?')]
    acts = ([out] if choice else [out, Button('Hint ', Kbd('⌥W'), type='button', id='hint', cls='quiet', hx_post=at(Routes.hint), data_wait=HINTING, **tl),
                                   Button('Send ', Kbd('⌥S'), cls='go', id='send', data_wait=GRADING)])
    return Form(*boxes, Div(*run('answer_tools', q, 'think' if choice else 'ans'), Confidence(), Left(MAX_TRIES - len(q.tries) if tried else None),
                            Span(cls='grow'), *acts, cls='row bar'),
                hx_post=at(Routes.answer), **tl, **kw)

def Out(sid, q, oob=False):
    "The way out: I don't know before the first try, Teach me after it. ⌥X presses it."
    t = f'#{tl_id(q)}'
    return Button('Teach me ' if q.get('tries') else "I don't know ", Kbd('⌥X'), type='button', id='idk', cls='quiet',
                  hx_post=Routes.at(Routes.giveup, sid), hx_vals='{"dont_know": 1}', hx_include='#conf', hx_target=t, hx_swap='beforeend',
                  data_wait=TEACHING, data_skel=t, hx_swap_oob='true' if oob else None)

def Ready(sid, ready):
    "Whether the next question is written yet; it asks again each second, out of the progress bar."
    if ready: return Span('The next question is ready.', cls='ready mute', id='ready')
    return Span('Writing the next question', cls='ready mute wait', id='ready', data_quiet='1',
                hx_get=Routes.at(Routes.ready, sid), hx_trigger='load delay:1s', hx_swap='outerHTML')

def Done(summary):
    return Section(H1('Done for now'), P(summary), A('Back to today', href='/'), cls='qa done'), Div(id='composer', hx_swap_oob='true')
