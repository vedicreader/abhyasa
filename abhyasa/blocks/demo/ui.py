from pathlib import Path
from fasthtml.common import *
from rupaka.render import Demo, version
from abhyasa.core import asset_css, asset_js
from .cfg import Routes

_P = Path(__file__).parent

def assets():
    "The rupaka runtime, served by this app, and the block's own style and script."
    v = version()
    return (Link(rel='stylesheet', href=f'{Routes.css}?v={v}'), Script(src=f'{Routes.js}?v={v}'),
            asset_css(_P/'demo.css'), asset_js(_P/'demo.js'))

AIMS = dict(simpler='A simpler demo')   # the aim of a demo that shows under a lesson -> its label; '' is a plain demo

def DemoCard(d, session='', lead=True, link=True):
    "One demo: a short lead, the figure, and a link to its own page. Each prediction goes to `Routes.predict`."
    return Div(Span(AIMS.get(d.get('aim', ''), 'Demo'), cls='lbl'),
               P('Predict first. Then the demo shows the rest.', cls='mute lead') if lead else '',
               Demo(d.spec), *assets(),
               P(A('Open the demo on its own page', href=Routes.of(Routes.page, slug=d.slug)), cls='mute') if link else '',
               cls='demo-card', data_demo=d.slug, data_session=session, data_url=Routes.of(Routes.predict, slug=d.slug), id=f'demo-{d.slug}')

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
