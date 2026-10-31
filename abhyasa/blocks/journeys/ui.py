"A walk as a path: a vertical line of steps, each with its state, its depth and why it is there; the current step in the accent."
import json
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import DepthBar, asset_css, ago, Primary, n_of
from .cfg import Routes

_P = Path(__file__).parent
STATE = dict(new='new', started='started', learned='learned', known='you know it', skipped='skipped', missing='not in your concepts')

def assets(): return asset_css(_P/'journeys.css'),

def at(r, j): return Routes.of(r, jid=j.id)
def go(j, pg=None):
    "Where Continue goes: the idea to do now of a walk (or its page), or a session on a path."
    if j.get('mode') != 'walk': return f"{Routes.start}?journey={j.id}"
    i = (pg.current or {}).get('i') if pg is not None else None
    return Routes.of(Routes.walk, jid=j.id) + (f'/{i}' if i is not None else '')

def Bar(done, total): return Span(I(style=f"width:{100 * done // max(total, 1)}%"), cls='prog', role='progressbar', aria_valuenow=str(done), aria_valuemax=str(total))

def Act(j, s, act, label, title):
    return Button(label, type='button', cls='small quiet', title=title, hx_post=at(Routes.path_step, j), hx_vals=json.dumps(dict(slug=s.slug, act=act)),
                  hx_target='#path', hx_swap='outerHTML')

def Step(j, s, i, n, now):
    "One step: a dot on the line, the concept, its state, why it is in the path, and the changes you can make."
    acts = [Act(j, s, 'up', '↑', 'Move up') if i else '', Act(j, s, 'down', '↓', 'Move down') if i < n - 1 else '',
            Act(j, s, 'todo', 'Learn it', 'Put it back in the walk') if s.state in ('known', 'skipped') else Act(j, s, 'known', 'I know it', 'Mark it known. The walk goes on.'),
            Act(j, s, 'skip', 'Skip', 'Leave it out for now') if s.state not in ('skipped', 'known') else '',
            Button('Split', type='button', cls='small quiet', title='Split it into smaller ideas', hx_post=at(Routes.path_split, j), hx_vals=json.dumps(dict(slug=s.slug)),
                   hx_target='#path', hx_swap='outerHTML', data_wait='Splitting…') if s.state in ('new', 'started') else '',
            Act(j, s, 'remove', 'Remove', 'Take it out of the walk')]
    head = Div(A(s.name, href=f'/c/{s.slug}', cls='name') if s.c else Span(s.name, cls='name'), DepthBar(s.c.floor) if s.c else '',
               Span(STATE[s.state] + (' · now' if now else ''), cls='st'), cls='step-head')
    learn = A('Learn this idea', href=f"{Routes.start}?focus={s.slug}", cls='btn small quiet') if s.state in ('new', 'started') and not now else ''
    return Li(Span(cls='dot', aria_hidden='true'), head, P(s.why, cls='why') if s.get('why') else '', Div(learn, *acts, cls='acts'),
              cls=f"step {s.state}" + (' now' if now else ''), id=f'step-{s.slug}')

def Path_(j, pg):
    "The progress, the way on, the steps, and a box to add a topic. Each change returns this whole part."
    cur = pg.current.slug if pg.current else None
    way = (Primary('Continue the walk' if j.get('mode') == 'walk' else f'Continue: {pg.current.name}', href=go(j)) if pg.current
           else P('You finished this walk. See what comes after it, below.', cls='done-note'))
    return Div(Div(Span(f"{pg.done} of {n_of(pg.total, 'idea')}", cls='lbl'), Bar(pg.done, pg.total), cls='phead'), Div(way, cls='row'),
               Ol(*[Step(j, s, i, len(pg.steps), s.slug == cur) for i, s in enumerate(pg.steps)], cls='path'),
               Form(Input(type='text', name='name', id='add-topic', data_mic='1', aria_label='Add a topic',
                          placeholder='Add a topic, for example: rotary position embeddings'),
                    Button('Add', data_wait='Adding…'), hx_post=at(Routes.path_add, j), hx_target='#path', hx_swap='outerHTML', cls='add-topic'),
               id='path')

def UseSources(j):
    "On a walk with no source: make it a walk that reads your sources, with a passage and a check on each step."
    if j.get('mode') == 'walk': return ''
    return Form(Button('Use sources for this walk', cls='small', data_wait='Reading your sources…'),
                Span('abhyasa finds a passage in your sources for each step, and gives each step a check.', cls='mute'),
                hx_post=at(Routes.path_sources, j), hx_swap='outerHTML', cls='use-sources row')

def JourneyPage(j, pg, after=(), actions=()):
    near = [*([H2('After this' if pg.finished else 'Near this walk'),
               Ul(*[Li(A(c.name, href=f'/c/{c.slug}'), DepthBar(c.floor), ' ',
                       Button('Add to the walk', type='button', cls='small quiet', hx_post=Routes.attach, hx_vals=json.dumps(dict(jid=j.id, slug=c.slug)),
                              hx_target='#path', hx_swap='outerHTML')) for c in after], cls='plain')] if after else [])]
    return (H1(j.title), P('Your goal: ', Span(j.get('goal', ''), cls='goal'), Span(f"  · changed {ago(j.get('updated'))}", cls='mute'), cls='mute'),
            Div(*actions, cls='row') if actions else '', UseSources(j), Path_(j, pg), Div(*near, cls='refs') if near else '',
            Form(Button('Remove this walk', cls='small quiet danger'), action=at(Routes.path_drop, j), method='post',
                 hx_confirm='Remove this walk? Its concepts and what you learned stay.', cls='drop'))

def InJourneys(c, rows, js):
    "On a concept page: the walks that have this concept, and a way to add it to one."
    have = {j.id for j, _ in rows}
    pick = [j for j in js if j.id not in have]
    return Div(*([H2('In your walks'),
                  Ul(*[Li(A(j.title, href=at(Routes.path, j)), Span(f"  idea {i + 1} of {len(j.steps)}", cls='mute')) for j, i in rows], cls='plain')] if rows else []),
               Form(Label('Add this idea to a walk', fr='attach-jid', cls='lbl'), Select(*[Option(j.title, value=j.id) for j in pick], name='jid', id='attach-jid'), Input(type='hidden', name='slug', value=c.slug), Input(type='hidden', name='src', value='concept'),
                    Button('Add to the walk', cls='small'), hx_post=Routes.attach, hx_target='this', hx_swap='outerHTML', cls='attach row') if pick else '',
               cls='in-journeys')

def StepDone(c, nxt):
    "A note in the thread when a step of the walk is learned."
    return Div(Span('Idea done', cls='lbl'), P(f"You learned {c.name}. " + (f"Next in the walk: {nxt}." if nxt else 'That was the last idea of the walk.')),
               cls='step-done')
