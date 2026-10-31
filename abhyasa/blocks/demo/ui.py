import json
from pathlib import Path
from fasthtml.common import *
from rupaka.render import Demo, version
from abhyasa.core import asset_css, asset_js, Feedback, Quiet
from abhyasa.core.leela import LEELA_INSTALL
from abhyasa.demo import KINDS
from .cfg import Routes

_P = Path(__file__).parent

def assets():
    "The rupaka runtime, served by this app, and the block's own style and script."
    v = version()
    return (Link(rel='stylesheet', href=f'{Routes.css}?v={v}'), Script(src=f'{Routes.js}?v={v}'),
            asset_css(_P/'demo.css'), asset_js(_P/'demo.js'))

AIMS = dict(simpler='A simpler demo')   # the aim of a demo that shows under a lesson -> its label; '' is a plain demo
LABELS = {**AIMS, '3d': 'A 3D explainer'}
THREE_LEAD = 'A 3D explainer: watch it step by step.'

def DemoCard(d, session='', lead=True, link=True, ask=''):
    """One demo: a short lead, the figure, the feedback row, and a link to its own page. Each prediction goes to `Routes.predict`.
    After "Not clear" on a plain demo, a quiet button makes a simpler demo under the card. A 3D explainer always has its lead, and its scene has its own step controls."""
    three = d.get('aim') == '3d'
    more = None if d.get('aim') in ('simpler', '3d') else dict(hx_post=Routes.make, hx_vals=json.dumps(dict(concept=d.concept, aim='simpler')),
                                                        hx_target='closest .demo-card', hx_swap='afterend')
    return Div(Span(LABELS.get(d.get('aim', ''), 'Demo'), cls='lbl'),
               P(THREE_LEAD if three else 'Predict first. Then the demo shows the rest.', cls='mute lead') if lead or three else '',
               Demo(d.spec), *assets(), Feedback('demo', slug=d.slug, simpler=more),
               P(A('Open the demo on its own page', href=Routes.of(Routes.page, slug=d.slug)), cls='mute') if link else '',
               cls='demo-card', data_demo=d.slug, data_session=session, data_url=Routes.of(Routes.predict, slug=d.slug), data_ask=ask or None, id=f'demo-{d.slug}')

def Pending(concept, aim=''):
    "A note that asks the server again in two seconds, until the demo with the aim `aim` is ready."
    what = 'a simpler demo' if aim == 'simpler' else 'a demo'
    return Div(Span(AIMS.get(aim, 'Demo'), cls='lbl'), P(f'The tutor is making {what} for this concept. This can take a minute.', cls='mute making'),
               hx_get=Routes.of(Routes.wait, concept=concept) + (f'?aim={aim}' if aim else ''), hx_trigger='load delay:2s', hx_swap='outerHTML', cls='demo-card pending')

def Failed():
    return Div(Span('Demo', cls='lbl'), P('No demo this time. The model did not make a demo that passes the checks. The lesson stays.', cls='mute'),
               cls='demo-card')

def ShowButton(c):
    "The concept-page action: show the newest demo, or make one."
    return (Button('Show me a demo ', Kbd('⌥E'), type='button', id='show-demo', hx_post=Routes.make, hx_vals=f'{{"concept": "{c.slug}"}}',
                   hx_target='#demo-slot', hx_swap='innerHTML'),
            Div(id='demo-slot', cls='demo-slot'), asset_js(_P/'demo.js'))

# --- Show me: a demo from your words, on a walk step and in a session ------------------------------------------------

def ShowMe(at, label='Show me ', key=True):
    "The button Show me (⌥E): a demo made from the open check, or from the idea. `at` names the place: `where`, and `concept`, `walk` and `step`, or `qid`."
    vals = json.dumps({k: str(v) for k, v in at.items() if v not in (None, '')})
    tgt = dict(hx_target=f"#tl-{at['qid']}", hx_swap='beforeend') if at.get('where') == 'session' else dict(hx_target='#show-slot', hx_swap='innerHTML')
    return Button(label, Kbd('⌥E') if key else '', type='button', id='show-demo', cls='quiet', hx_post=Routes.ask, hx_vals=vals,
                  data_wait='Making a demo…', title='A demo of this idea, made from the open check. You can also type "show me …" in the answer box.', **tgt)

def StepShow(at):
    "The walk step: Show me under the title, and the place where its demo comes."
    return Div(ShowMe(at), Div(id='show-slot', cls='demo-slot show-slot'), asset_js(_P/'demo.js'), cls='row show-row')

def SessionShow(qid):
    "The session: Show me in the composer of question `qid`. Its demo comes as a tutor message in the thread."
    return ShowMe(dict(where='session', qid=qid)), asset_js(_P/'demo.js')

def ThreeD(attrs):
    "Show it in 3D: a quiet button that asks again for a 3D explainer. `attrs` are its htmx attributes."
    return Quiet('Show it in 3D', type='button', data_wait='Making a 3D explainer…', **attrs)

def TryLeela(href):
    "Try it in Leela: the link when Leela runs; else a quiet note and how to get Leela."
    if href: return A('Try it in Leela ↗', href=href, target='_blank', rel='noopener', cls='btn quiet try-leela')
    return Span('Try it in Leela: Leela is not running. ', A('Get Leela', href=LEELA_INSTALL, target='_blank', rel='noopener'), cls='try-leela not-ready')

def Kind(kind, why, said=''):
    "The line on top of an ask: which kind of demo, and why, in one line."
    return Div(Span(KINDS[kind], cls='lbl'), P(why, *([' You asked: ', Q(said)] if said else []), cls='mute kind-why'), cls='ask-kind')

def AskCard(a, route, body, leela, two_d=None, three_d=None):
    """The answer to one ask: the kind and why, the demo (or its wait, or a note), then the other kinds and "Try it in Leela", one click away.
    `two_d` and `three_d` hold the htmx attributes of "Show a 2D demo" and "Show it in 3D" when the ask went to another kind."""
    links = Div(*([Quiet('Show a 2D demo', type='button', **two_d)] if two_d else []), *([ThreeD(three_d)] if three_d else []), TryLeela(leela), cls='row ask-links')
    return Div(Kind(route.kind, route.why, a.said), body, links, cls='ask-card', id=f'ask-{a.id}', data_ask=a.id)

def AskPending(a, kind=''):
    "The demo of ask `a` (with `kind`, its 3D explainer or its 2D demo) is not ready: the card asks the server again in 2 seconds."
    three = kind == '3d'
    return Div(Span('A 3D explainer' if three else 'Demo', cls='lbl'),
               P(f"The tutor is making {'a 3D explainer' if three else 'a demo'} for what you asked. This can take a minute.", cls='mute making'),
               hx_get=Routes.of(Routes.asked, aid=a.id) + (f'?kind={kind}' if kind else ''), hx_trigger='load delay:2s', hx_swap='outerHTML', cls='demo-card pending')
