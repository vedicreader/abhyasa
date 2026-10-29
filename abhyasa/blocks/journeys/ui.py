"A walk as a path: a vertical line of steps, each with its state, its depth and why it is there; the current step in the accent."
import json
from pathlib import Path
from urllib.parse import quote, urlparse
from fasthtml.common import *
from abhyasa.core.hooks import run
from abhyasa.core import Md, DepthBar, asset_css, asset_js, ago, Primary, n_of, Onward
from abhyasa.journey import parent_step, walk_state, paper_id
from abhyasa.sources import is_paper
from abhyasa.settings import val
from .cfg import Routes

_P = Path(__file__).parent
STATE = dict(new='new', started='started', learned='learned', known='you know it', skipped='skipped', missing='not on the shelf')
PLANNING = 'Planning a path. This takes about half a minute…'

def assets(): return asset_css(_P/'journeys.css'), asset_js(_P/'journeys.js')

def at(r, j): return Routes.of(r, jid=j.id)
def go(j): return Routes.of(Routes.walk, jid=j.id) if j.get('mode') == 'walk' else f"{Routes.start}?journey={j.id}"

def kind_of(j) -> str:
    "What walk `j` reads, for its pill: `path` (planned from a goal), `repo`, `paper`, `site`, `text` or `topic`."
    if j.get('mode') != 'walk': return 'path'
    src = j.get('source') or {}
    url = src.get('url') or ''
    if j.get('tool') or urlparse(url).hostname in ('github.com', 'www.github.com'): return 'repo'
    if paper_id(j) or is_paper(url) or src.get('doc_id'): return 'paper'
    if src.get('docs'): return 'site'
    if j.get('id') and any((s.get('read') or {}).get('doc_id') == j['id'] for s in j.get('steps') or []): return 'text'
    return 'topic'

def Bar(done, total): return Span(I(style=f"width:{100 * done // max(total, 1)}%"), cls='prog', role='progressbar', aria_valuenow=str(done), aria_valuemax=str(total))

def GoalForm(compact=False, label=True):
    "The box where a walk starts: say or type a goal. The planner suggests a path that you can change. `label=False` when a fold names it."
    return Form(Label('What do you want to learn?', fr='goal') if label else '',
                Textarea(name='goal', id='goal', rows=1 if compact else 2, data_mic='label', aria_label='Your goal',
                         placeholder='For example: how LLMs work, from tokens to training. ⌘↵ plans a path.'),
                Div(Button('Plan a path', cls='plan', data_wait=PLANNING, data_skel='#plan-out'),
                    Span('The tutor suggests the steps. You can change each one.', cls='mute'), cls='row'),
                P('The tutor searches the web for sources. The search sees your topic.', cls='mute') if val('research.on') else '',
                Div(id='plan-out'), hx_post=Routes.new, hx_target='#plan-out', cls='goal-form' if compact else 'goal-form raised')

def beside(j, js):
    "The step that opened side walk `j`, with the side walk at its current step in the pane (`?rh=`); its own page when that step is gone."
    pj, i = parent_step(None, j, js)
    if not pj: return go(j)
    k = walk_state(j).current
    return f"/w/{pj.id}/{i}?rh=" + quote(f"/w/{j.id}/{k if k is not None else 0}", safe='/')

def SideWalk(j, pg, js=None):
    "One side walk under the walk that opened it: its title, the idea it was for, and its progress. It opens beside the step that opened it."
    i = (j.get('parent') or {}).get('step')
    return Li(A(j.title, href=beside(j, js or {})), Span(f"  for idea {i + 1} · {pg.done} of {n_of(pg.total, 'idea')}" if isinstance(i, int) else f"  {pg.done} of {n_of(pg.total, 'idea')}", cls='mute'))

def Row(j, pg, sides=(), lead=False, js=None):
    """One walk in a list: its title, its progress, the step to do now, the way on, and its side walks. Only the `lead` row
    (the current walk) has a button; the others have a quiet `Continue →` link."""
    now = f"Now: {pg.current.name}" if pg.current else 'Finished'
    go_on = (A('Continue the walk' if j.get('mode') == 'walk' else 'Continue', href=go(j), cls='btn small') if lead else
             Onward('Continue', go(j)) if pg.current else Onward('See what comes after', at(Routes.path, j)))
    return Li(Div(A(j.title, href=at(Routes.path, j), cls='jt'), Span(paper_id(j), cls='paper-id mute') if paper_id(j) else '', Span(f"  {pg.done} of {n_of(pg.total, 'step')} · {now}", cls='mute'), cls='jrow-head'),
              Bar(pg.done, pg.total), go_on, *(run('walk_actions', j, quiet=True) if j.get('mode') == 'walk' else ()),
              Div(Span('Side walks', cls='lbl'), Ul(*[SideWalk(*x, js=js) for x in sides], cls='plain'), cls='side-walks') if sides else '',
              cls='jrow')

def root_of(j, ids):
    "The id of the first walk up the parents of side walk `j` that is not a side walk, when it is in `ids`; else None."
    seen = set()
    while j and j.get('depth') and (p := (j.get('parent') or {}).get('walk')) in ids and p not in seen:
        seen.add(p); j = ids[p][0]
    return None if j is None or j.get('depth') else j.id

def JourneyList(js, empty='No walks yet. Say what you want to learn, and the tutor suggests a path.', lead=True):
    """The walks, each with its side walks under it. A side walk whose walk is gone has its own line.
    With `lead`, the first walk with a step to do (the newest, as Continue in the top bar) has the one button."""
    ids = {j.id: (j, pg) for j, pg in js}
    sides = {}
    for j, pg in js:
        if j.get('depth') and (r := root_of(j, ids)): sides.setdefault(r, []).append((j, pg))
    under = {j.id for x in sides.values() for j, _ in x}
    top = next((j.id for j, pg in js if j.id not in under and pg.current), None) if lead else None
    byid = {k: v[0] for k, v in ids.items()}
    rows = [Row(j, pg, sides.get(j.id, ()), j.id == top, byid) for j, pg in js if j.id not in under]
    return Ul(*rows, cls='plain journeys') if rows else P(empty, cls='mute')

def Act(j, s, act, label, title):
    return Button(label, type='button', cls='small quiet', title=title, hx_post=at(Routes.path_step, j), hx_vals=json.dumps(dict(slug=s.slug, act=act)),
                  hx_target='#path', hx_swap='outerHTML')

def Step(j, s, i, n, now):
    "One step: a dot on the line, the concept, its state, why it is in the path, and the changes you can make."
    acts = [Act(j, s, 'up', '↑', 'Move up') if i else '', Act(j, s, 'down', '↓', 'Move down') if i < n - 1 else '',
            Act(j, s, 'todo', 'Learn it', 'Put it back in the path') if s.state in ('known', 'skipped') else Act(j, s, 'known', 'I know it', 'Mark it known: the path goes on'),
            Act(j, s, 'skip', 'Skip', 'Leave it out for now') if s.state not in ('skipped', 'known') else '',
            Button('Split', type='button', cls='small quiet', title='Split it into smaller steps', hx_post=at(Routes.path_split, j), hx_vals=json.dumps(dict(slug=s.slug)),
                   hx_target='#path', hx_swap='outerHTML', data_wait='Splitting…') if s.state in ('new', 'started') else '',
            Act(j, s, 'remove', 'Remove', 'Take it out of the path')]
    head = Div(A(s.name, href=f'/c/{s.slug}', cls='name') if s.c else Span(s.name, cls='name'), DepthBar(s.c.floor) if s.c else '',
               Span(STATE[s.state] + (' · now' if now else ''), cls='st'), cls='step-head')
    learn = A('Learn this step', href=f"{Routes.start}?focus={s.slug}", cls='btn small quiet') if s.state in ('new', 'started') and not now else ''
    return Li(Span(cls='dot', aria_hidden='true'), head, P(s.why, cls='why') if s.get('why') else '', Div(learn, *acts, cls='acts'),
              cls=f"step {s.state}" + (' now' if now else ''), id=f'step-{s.slug}')

def Path_(j, pg):
    "The progress, the way on, the steps, and a box to add a topic. Each change returns this whole part."
    cur = pg.current.slug if pg.current else None
    way = (Primary('Continue the walk' if j.get('mode') == 'walk' else f'Continue: {pg.current.name}', href=go(j)) if pg.current
           else P('You finished this walk. See what comes after it, below.', cls='done-note'))
    return Div(Div(Span(f"{pg.done} of {n_of(pg.total, 'step')}", cls='lbl'), Bar(pg.done, pg.total), cls='phead'), Div(way, cls='row'),
               Ol(*[Step(j, s, i, len(pg.steps), s.slug == cur) for i, s in enumerate(pg.steps)], cls='path'),
               Form(Input(type='text', name='name', id='add-topic', data_mic='1', aria_label='Add a topic',
                          placeholder='Add a topic, for example: rotary position embeddings'),
                    Button('Add', data_wait='Adding…'), hx_post=at(Routes.path_add, j), hx_target='#path', hx_swap='outerHTML', cls='add-topic'),
               id='path')

def JourneyPage(j, pg, after=(), others=(), actions=()):
    near = [*([H2('After this' if pg.finished else 'Next to this path'),
               Ul(*[Li(A(c.name, href=f'/c/{c.slug}'), DepthBar(c.floor), ' ',
                       Button('Add to the path', type='button', cls='small quiet', hx_post=Routes.attach, hx_vals=json.dumps(dict(jid=j.id, slug=c.slug)),
                              hx_target='#path', hx_swap='outerHTML')) for c in after], cls='plain')] if after else []),
            *([H2('Your other walks'), JourneyList(others, lead=False)] if others else [])]
    return (H1(j.title), P('Your goal: ', Span(j.get('goal', ''), cls='goal'), Span(f"  · changed {ago(j.get('updated'))}", cls='mute'), cls='mute'),
            Div(*actions, cls='row') if actions else '', Path_(j, pg), Div(*near, cls='refs') if near else '',
            Form(Button('Remove this walk', cls='small quiet danger'), action=at(Routes.path_drop, j), method='post',
                 hx_confirm='Remove this walk? Its concepts and what you learned stay.', cls='drop'))

def InJourneys(c, rows, js):
    "On a concept page: the walks that have this concept, and a way to add it to one."
    have = {j.id for j, _ in rows}
    pick = [j for j in js if j.id not in have]
    return Div(*([Span('In your walks', cls='lbl'),
                  Ul(*[Li(A(j.title, href=at(Routes.path, j)), Span(f"  step {i + 1} of {len(j.steps)}", cls='mute')) for j, i in rows], cls='plain')] if rows else []),
               Form(Span('Add this idea to a walk', cls='lbl'), Select(*[Option(j.title, value=j.id) for j in pick], name='jid', aria_label='Add this idea to a walk'), Input(type='hidden', name='slug', value=c.slug), Input(type='hidden', name='src', value='concept'),
                    Button('Add to the walk', cls='small'), hx_post=Routes.attach, hx_target='this', hx_swap='outerHTML', cls='attach row') if pick else '',
               cls='in-journeys')

def StepDone(c, nxt):
    "A note in the thread when a step of the walk is learned."
    return Div(Span('Step done', cls='lbl'), P(f"You learned {c.name}. " + (f"Next in the walk: {nxt}." if nxt else 'That was the last step of the walk.')),
               cls='step-done')
