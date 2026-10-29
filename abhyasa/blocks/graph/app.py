"The concept graph on a canvas, with levers to arrange it. The arrangement stays in the browser."
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import Page, RouteOverrides, hook, asset_js, asset_css
from abhyasa.model import understanding
from .cfg import Routes
from .ui import Stage, Empty_

__all__ = ['CAPS', 'connect']
CAPS = ('learning',)
_P = Path(__file__).parent

def connect(app, ctx):
    lr = ctx.learning

    def page(subject:str='', focus:str=''):
        subs = [r['subject'] for r in lr.subjects() if r['subject']]
        if not lr.concepts(): return Page('Graph', Empty_(), on='Library', sub='Graph', wide=True, extra=(asset_css(_P/'graph.css'),))
        return Page('Graph', Stage(Routes.data, subs, subject, focus),
                    Script(src='/vendor/d3.min.js'), asset_js(_P/'graph.js', defer=True),
                    on='Library', sub='Graph', wide=True, extra=(asset_css(_P/'graph.css'),))

    def data(subject:str=''):
        "The graph, with how well you know each concept: its state and the reasons."
        g, by = lr.graph(subject or None), {c.slug: c for c in lr.concepts(subject or None)}
        for n in g['nodes']:
            u = understanding(by[n['id']]); n.update(state=u.state, reasons=u.reasons)
        return JSONResponse(g)

    @hook('concept_actions')
    def see(c): return A('See in the graph', href=f'{Routes.base}?subject={c.subject}&focus={c.slug}', cls='btn')

    RouteOverrides.subtabs.setdefault('Library', []).append(('Graph', Routes.base, 2))
    app.get(Routes.base)(page)
    app.get(Routes.data)(data)
