"Every concept, one concept's page, and the subjects on Today."
from abhyasa.core import Page, RouteOverrides, hook
from abhyasa.settings import val
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'sources')

def connect(app, ctx):
    lr = ctx.learning

    def index(subject:str=''):
        cs = sorted(lr.concepts(subject or None), key=lambda c: (c.subject, c.get('order', 1e9), c.name))
        return Page('Concepts', ui.H1(subject or 'Concepts'), ui.ConceptList(cs), on='Concepts',
                    crumbs=[('Today', '/'), *([('Concepts', Routes.base)] if subject else [])])

    def one(slug:str):
        c = lr.concept(slug)
        if not c: return Page('Concept', ui.P('No such concept.'))
        if lr.stale_links(c):
            try: lr.connect(slug, ctx.sources); c = lr.concept(slug)
            except Exception: pass
        return Page(c.name, *ui.ConceptPage(c, {x.slug: x for x in lr.concepts()}, lr.attempts(slug, limit=val('lists.attempts'))),
                    crumbs=[('Today', '/'), ('Concepts', Routes.base)])

    @hook('today')
    def subjects(subject=None): return ui.Subjects(lr.subjects())

    RouteOverrides.nav.append(('Concepts', Routes.base, 2))
    app.get(Routes.base)(index)
    app.get(Routes.one)(one)
