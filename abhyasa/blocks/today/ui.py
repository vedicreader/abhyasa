"Your courses and walks on Home: one list, courses first with their stages folded, then each walk that is in no course, with its side walks under it."
from pathlib import Path
from urllib.parse import quote, urlparse
from fasthtml.common import *
from abhyasa.core.hooks import run
from abhyasa.core import asset_css, n_of, Onward, Pill, Part
from abhyasa.journey import parent_step, walk_state, paper_id
from abhyasa.sources import is_paper

_P = Path(__file__).parent

def css(): return asset_css(_P/'home.css')

def walk_at(jid, i=None): return f'/w/{jid}' + (f'/{i}' if i is not None else '')

def kind_of(j) -> str:
    "What walk `j` reads, for its pill: `repo`, `paper`, `site`, `text` or `topic`."
    src = j.get('source') or {}
    url = src.get('url') or ''
    if j.get('tool') or urlparse(url).hostname in ('github.com', 'www.github.com'): return 'repo'
    if paper_id(j) or is_paper(url) or src.get('doc_id'): return 'paper'
    if src.get('docs'): return 'site'
    if j.get('id') and any((s.get('read') or {}).get('doc_id') == j['id'] for s in j.get('steps') or []): return 'text'
    return 'topic'

def Bar(done, total): return Span(I(style=f"width:{100 * done // max(total, 1)}%"), cls='prog', role='progressbar', aria_valuenow=str(done), aria_valuemax=str(total))

def beside(j, js):
    "The step that opened side walk `j`, with the side walk at its current step in the pane (`?rh=`); its own page when that step is gone."
    pj, i = parent_step(None, j, js)
    if not pj: return walk_at(j.id)
    k = walk_state(j).current
    return walk_at(pj.id, i) + '?rh=' + quote(walk_at(j.id, k if k is not None else 0), safe='/')

def SideWalk(j, ws, js):
    "One side walk under the walk that opened it: its title, the idea it was for, and its progress. It opens beside the step that opened it."
    i = (j.get('parent') or {}).get('step')
    return Li(A(j.title, href=beside(j, js)), Span(f"  for idea {i + 1} · " if isinstance(i, int) else '  ', f"{ws.done} of {n_of(ws.total, 'idea')}", cls='mute'))

def Row(j, ws, by, sides=(), lead=False, js=None):
    """One walk, as two quiet lines: its title, its kind and its paper id; then its progress and the idea to do now.
    At the right, one way on and a quiet Present (`walk_actions` with `row`). Only the `lead` row has a button."""
    i = ws.current
    word = 'Start the walk' if not j.get('started') else 'Continue'
    go = walk_at(j.id, i) if j.get('started') and i is not None else walk_at(j.id)
    go_on = (A(word, href=go, cls='btn small') if lead and i is not None else Onward(word, go) if i is not None else Onward('See the end of the walk', walk_at(j.id)))
    pid = paper_id(j)
    now = f"Now: {(by.get(ws.steps[i]['slug']) or {}).get('name') or ws.steps[i]['slug']}" if i is not None else 'Finished'
    head = Div(Div(A(j.title, href=walk_at(j.id), cls='jt'), Pill(kind_of(j)), Span(pid, cls='paper-id mute') if pid else '', cls='jrow-l1'),
               Div(Bar(ws.done, ws.total), Span(f"{ws.done} of {n_of(ws.total, 'idea')}", cls='mute'), Span(now, cls='mute now', title=now), cls='jrow-l2'),
               cls='jrow-head')
    folded = Details(Summary(n_of(len(sides), 'side walk')), Ul(*[SideWalk(*x, js=js) for x in sides], cls='plain'), cls='side-walks') if sides else ''
    return Li(head, Div(go_on, *run('walk_actions', j, row=True), cls='lrow-acts'), folded, cls='jrow lrow')

def root_of(j, ids):
    "The id of the first walk up the parents of side walk `j` that is not a side walk, when it is in `ids`; else None."
    seen = set()
    while j and j.get('depth') and (p := (j.get('parent') or {}).get('walk')) in ids and p not in seen:
        seen.add(p); j = ids[p][0]
    return None if j is None or j.get('depth') else j.id

def walk_rows(js, by):
    "The rows of the walks `js` (`(walk, walk_state)`), each with its side walks under it. The first walk with an idea to do has the one button."
    ids = {j.id: (j, ws) for j, ws in js}
    sides = {}
    for j, ws in js:
        if j.get('depth') and (r := root_of(j, ids)): sides.setdefault(r, []).append((j, ws))
    under = {j.id for x in sides.values() for j, _ in x}
    top = next((j.id for j, ws in js if j.id not in under and ws.current is not None), None)
    byid = {k: v[0] for k, v in ids.items()}
    return [Row(j, ws, by, sides.get(j.id, ()), j.id == top, byid) for j, ws in js if j.id not in under]

STAGE = dict(done='done', known='you know it', skipped='skipped', building='abhyasa plans it now', planned='planned')

def Stage(r):
    "One stage of a course: its name (a link to its walk when it has one), and its state or its progress."
    said = f"{r.done} of {n_of(r.total, 'idea')}" if r.j and r.state == 'ready' else STAGE.get(r.state, r.state)
    return Li(A(r['name'], href=walk_at(r.j.id)) if r.j else Span(r['name']), Span(f'  {said}', cls='mute'))

def CourseRow(c, rows):
    "One course: its title and its stages done, then its stages folded under it."
    left = [r for r in rows if r.state != 'skipped']
    done = sum(r.state in ('done', 'known') for r in left)
    head = Div(Div(A(c.title, href=f'/course/{c.id}', cls='jt'), Pill('course'), cls='jrow-l1'),
               Div(Bar(done, len(left)), Span(f"{done} of {n_of(len(left), 'stage')}", cls='mute'), cls='jrow-l2'), cls='jrow-head')
    folded = Details(Summary(n_of(len(rows), 'stage')), Ul(*map(Stage, rows), cls='plain'), cls='side-walks') if rows else ''
    return Li(head, Div(Onward('Open the course', f'/course/{c.id}'), cls='lrow-acts'), folded, cls='jrow lrow')

def Walks(courses, walks, by):
    "Your courses and walks: `courses` is `(course, stage rows)`, `walks` is `(walk, walk_state)` for each walk that is in no course."
    rows = [*[CourseRow(*x) for x in courses], *walk_rows(walks, by)]
    return Part('Your courses and walks', Ul(*rows, cls='plain journeys'), data_part='walks') if rows else ''
