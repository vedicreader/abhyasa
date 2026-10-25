from pathlib import Path
from fasthtml.common import *
from abhyasa.core import Md, DepthBar, Spin, when, run, asset_css, asset_js
from abhyasa.model import DEPTHS
from .cfg import Routes

_P = Path(__file__).parent
OUTCOME = {'solid': 'Solid', 'fragile': 'Right, but shaky', 'misconception': 'A misconception', 'gap': 'A gap'}

def assets(): return asset_css(_P/'session.css'), asset_js(_P/'session.js')

def Head(q):
    return P(f"{q.name} · {DEPTHS[q.depth]}", DepthBar(q.get('floor', 0), asked=q.depth), Br(), Span(q.why, cls='why'), cls='mute')

def QuestionCard(sid, q):
    "One question: why it was chosen, the question, and the answer form."
    at = lambda r: Routes.at(r, sid)
    if q.get('options'):
        opts = [Button(Md(o), name='answer', value=str(i), cls='opt', hx_post=at(Routes.answer), hx_target='#fb',
                       hx_include='#conf', hx_indicator='#sp') for i, o in enumerate(q.options)]
        return Div(Head(q), Md(q.question, cls='q'), *opts,
                   Label('Confidence', Input(type='range', name='confidence', min=0, max=100, value=50, id='conf')),
                   Div(Spin(), id='sp'), Div(id='fb'), id='card')
    form = Form(
        Label('Your answer', fr='ans'), Textarea(name='answer', id='ans', rows=3, autofocus=True),
        Label('Think aloud: how you got there, and what you are unsure of', fr='think'), Textarea(name='thinking', id='think', rows=4),
        Div(*run('answer_tools', q, 'think'), cls='row'),
        Label('Confidence', Input(type='range', name='confidence', min=0, max=100, value=50)),
        Div(Button('Send ', Kbd('⌥S'), cls='go', id='send'),
            Button('Hint ', Kbd('⌥W'), type='button', id='hint', hx_post=at(Routes.hint), hx_target='#hints', hx_swap='beforeend', hx_indicator='#sp'),
            Button("I don't know", type='button', hx_post=at(Routes.giveup), hx_vals='{"dont_know": 1}', hx_target='#fb', hx_indicator='#sp'),
            Spin(), cls='row', id='sp'),
        hx_post=at(Routes.answer), hx_target='#fb', hx_indicator='#sp')
    return Div(Head(q), Md(q.question, cls='q'), Ol(id='hints', cls='hints'), form, Div(id='fb'), id='card')

def Feedback(sid, r):
    "A nudge to try again, or the outcome, the lesson and what comes next."
    at = lambda x: Routes.at(x, sid)
    if not r.done:
        return Div(Span('Not yet', cls='tag'), Md(r.feedback),
                   P(f'{r.tries_left} more tries. Or ', A('teach me', href='#', hx_post=at(Routes.giveup), hx_target='#fb'), '.', cls='mute'),
                   cls='fb no')
    return Div(Span(OUTCOME[r.outcome], cls='tag'), Md(r.feedback) if r.feedback else '', Md(r.lesson) if r.lesson else '',
               P(f"Now: floor {DEPTHS[r.floor]}, next review {when(r.due)}.", cls='mute'),
               Div(Button('Next ', Kbd('⌥S'), cls='go', id='send', hx_post=at(Routes.next), hx_target='#card', hx_swap='outerHTML',
                          hx_indicator='#sp2', autofocus=True),
                   A('End session', href=at(Routes.end), cls='btn'), Spin(), cls='row', id='sp2'),
               cls=f"fb {'ok' if r.correct else 'no'}")

def Done(summary): return Div(H1('Done for now'), P(summary), A('Back to today', href='/'), id='card')
