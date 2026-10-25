"The concept graph: colour by floor, a ring when a review is due, arrows for prereqs, dashes for related."
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import Page, RouteOverrides, hook, asset_js, asset_css
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning',)
_P = Path(__file__).parent

def connect(app, ctx):
    lr = ctx.learning

    def page(subject:str='', focus:str=''):
        pick = Select(Option('all subjects', value=''), *[Option(r['subject'], selected=r['subject'] == subject)
                      for r in lr.subjects() if r['subject']], onchange=f"location='{Routes.base}?subject='+this.value")
        return Page('Graph', Div(pick, cls='row'), Svg(id='graph', data_url=f'{Routes.data}?subject={subject}', data_focus=focus),
                    Script(src='/vendor/d3.min.js'), asset_js(_P/'graph.js', defer=True),
                    on='Graph', wide=True, extra=(asset_css(_P/'graph.css'),))

    def data(subject:str=''): return JSONResponse(lr.graph(subject or None))

    @hook('concept_actions')
    def see(c): return A('See in the graph', href=f'{Routes.base}?subject={c.subject}&focus={c.slug}', cls='btn')

    RouteOverrides.nav.append(('Graph', Routes.base, 1))
    app.get(Routes.base)(page)
    app.get(Routes.data)(data)
