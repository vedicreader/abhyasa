"Your strengths and weak spots, from how well you know each concept, and the ways you learn best."
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import hook, Primary, moved_to
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

    @hook('learning_top')
    def part(subject=''):
        """You → Progress, after This week: how well you know each subject, the weak spots with a way to practice them, the strong concepts,
        and in a closed part the ways you learn. `subject` keeps one subject."""
        rs, p, st = rows(subject or None), lr.profile(), lr.stats()
        head = H2('Your strengths' + (f' in {subject}' if subject else ''))
        if not any(c.get('seen') for c, _ in rs):
            return Section(head, P('Your strengths show here after your first answers.', cls='mute'), id='strengths', cls='strengths', data_part='strengths')
        prior = [EXAMPLES_TO[e] for e in p.examples if e in EXAMPLES_TO]
        subs = {}
        for c, u in (rs if not subject else rows()): subs.setdefault(c.get('subject') or '', []).append((c, u))
        weak = sorted((x for x in rs if x[1].weak), key=lambda x: x[1].score)[:val('lists.strengths')]
        strong = sorted((x for x in rs if x[1].strong), key=lambda x: -x[1].score)[:val('lists.strengths')]
        q = f'&subject={subject}' if subject else ''
        return Section(*ui.assets(), head,
                       P('This comes from your answers: how deep you know each concept, how well you recall it now, and what went wrong.', cls='mute'),
                       H3('By subject'), Ul(*[ui.Subject(k, v) for k, v in sorted(subs.items(), key=lambda kv: -len(kv[1]))], cls='plain subjects'),
                       H3('Weak spots'),
                       Div(Ul(*[ui.Concept(*x) for x in weak], cls='plain concepts'), Primary('Practice my weak spots', href=f'/start?drill=1{q}'), cls='weak') if weak
                       else P('No weak spots now.', cls='mute'),
                       H3('Strong'), Ul(*[ui.Concept(*x) for x in strong], cls='plain concepts') if strong else P('Nothing is strong yet: that takes depth 3 and good recall.', cls='mute'),
                       Details(Summary('The ways you learn' + (f' {subject}' if subject else '')), ui.Ways(st, subject, prior),
                               H3('How often to try a new way'),
                               P('The tutor teaches a weak concept in your best way. For a concept that is not weak, it sometimes uses a different way. This makes you better at that way too.', cls='mute'),
                               ui.Explore(p.get('explore', 'sometimes')), cls='more ways-more'),
                       id='strengths', cls='strengths', data_part='strengths')

    @hook('today_end')
    def line(subject=None):
        return A('Your strengths', href=f'{Routes.you}#strengths') if any(c.get('seen') for c in lr.concepts()) else None

    @hook('concept_more')
    def known(c):
        "How well you know concept `c`: its state and the reasons, the gaps that you named, and the ways that work for its subject."
        u, by = understanding(c), {x.slug: x for x in lr.concepts()}
        gaps = [by[g] for g in c.get('gaps') or () if g in by]
        return Section(H3('How well you know it'), P(ui.STATES[u.state].capitalize() + (f": {'; '.join(u.reasons)}." if u.reasons else '.'), cls='mute'),
                       P('Gaps you named: ', *[A(g.name, href=f'/c/{g.slug}') for g in gaps], cls='mute gaps') if gaps else '',
                       P(t, cls='mute') if (t := methods_text(lr.stats(), c.get('subject', ''))) else '', cls='known', data_part='strength')

    app.get(Routes.base)(moved_to(Routes.you, 'strengths'))
