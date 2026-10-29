"Your strengths and weak spots, from how well you know each concept, and the ways you learn best."
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import Page, hook, Primary
from abhyasa.settings import val
from abhyasa.model import understanding
from abhyasa.method import EXAMPLES_TO, methods_text
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning',)

def connect(app, ctx):
    lr = ctx.learning

    def rows(subject=None): return [(c, understanding(c)) for c in lr.concepts(subject)]

    def page(subject:str=''):
        rs, p, st = rows(subject or None), lr.profile(), lr.stats()
        prior = [EXAMPLES_TO[e] for e in p.examples if e in EXAMPLES_TO]
        subs = {}
        for c, u in (rs if not subject else rows()): subs.setdefault(c.get('subject') or '', []).append((c, u))
        weak = sorted((x for x in rs if x[1].weak), key=lambda x: x[1].score)[:val('lists.strengths')]
        strong = sorted((x for x in rs if x[1].strong), key=lambda x: -x[1].score)[:val('lists.strengths')]
        q = f'&subject={subject}' if subject else ''
        return Page('Strengths', *ui.assets(), H1('Your strengths and weak spots' + (f' in {subject}' if subject else '')),
                    P('This comes from your answers: how deep you know each concept, how well you recall it now, and what went wrong.', cls='mute'),
                    H2('By subject'), Ul(*[ui.Subject(k, v) for k, v in sorted(subs.items(), key=lambda kv: -len(kv[1]))], cls='plain subjects'),
                    H2('Weak spots'),
                    Div(Ul(*[ui.Concept(*x) for x in weak], cls='plain concepts'),
                        Primary('Practice my weak spots', href=f'/start?drill=1{q}'), cls='weak') if weak
                    else P('No weak spots now.', cls='mute'),
                    H2('Strong'), Ul(*[ui.Concept(*x) for x in strong], cls='plain concepts') if strong else P('Nothing is strong yet: that takes depth 3 and good recall.', cls='mute'),
                    H2('Ways you learn' + (f' {subject}' if subject else '')), ui.Ways(st, subject, prior),
                    H2('How often to try a new way'),
                    P('The tutor teaches a weak concept in your best way. For a concept that is not weak, it sometimes uses a different way. This makes you better at that way too.', cls='mute'),
                    ui.Explore(p.get('explore', 'sometimes')),
                    on='You', sub='Your learning', crumbs=[('Today', '/'), ('You', '/learning'), ('Your learning', '/learning')])

    @hook('today_end')
    def line(subject=None):
        return A('Your strengths', href=Routes.base) if any(c.get('seen') for c in lr.concepts()) else None

    @hook('concept_more')
    def known(c):
        if not c.get('seen') and not c.get('gaps'): return None
        u, by = understanding(c), {x.slug: x for x in lr.concepts()}
        gaps = [by[g] for g in c.get('gaps') or () if g in by]
        return Section(H3('How well you know it'), P(f"{ui.STATES[u.state].capitalize()}. " + ('; '.join(u.reasons) + '.' if u.reasons else ''), cls='mute'),
                       P('Gaps you named: ', *[A(g.name, href=f'/c/{g.slug}') for g in gaps], cls='mute gaps') if gaps else '',
                       P(t, cls='mute') if (t := methods_text(lr.stats(), c.get('subject', ''))) else '', cls='known')

    app.get(Routes.base)(page)
