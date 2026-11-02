"The parts of a detour: the needs line under the title of a step, the chooser of three depths, the gap line, the link to its own course, and the way back."
import json
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import asset_css, asset_js, Primary, meta, n_of, pane_link, side_link, short_title
from abhyasa.learner import val
from .cfg import Routes

_P = Path(__file__).parent
STATE = dict(learned='learned', today='learned on the way today', missing='not learned yet')

def assets(): return asset_css(_P/'detour.css'), asset_js(_P/'detour.js')

def step_url(jid, i): return Routes.of(Routes.step, jid=jid, i=i)
def course_url(cid): return Routes.of(Routes.course, cid=cid)

def Ask(label, t, *c, cls='rh-ask', **kw):
    "A button that opens the chooser for idea or term `t` (detour.js). `data_at` names the place when the page has no needs line."
    return Button(label, *c, type='button', cls=f'quiet small {cls}', data_t=t, **kw)

def Need(n, state, first):
    "One idea that the step needs: its name, its state, and Learn it on each one that you have not learned. Only the first shows ⌥B."
    go = '' if state != 'missing' else Ask('Learn it ', n.slug, Kbd('⌥B')) if first else Ask('Learn it', n.slug)
    return Span(side_link(n.name, f'/c/{n.slug}', n.name, cls='pane-link n'), Span(f' · {STATE[state]}', cls=f'st {state}'), go, cls='need')

def Strip(name, ok, sid, outs):
    "The strip after a side walk: what you learned on the way, and how the checks went. When you left before a check, the way to finish it."
    url = Routes.of(Routes.walk, jid=sid)
    if not outs:
        return Div(P('Back on the paper. You looked at ', B(name), ' on the way. You did not do its check yet.'),
                   P(pane_link('Finish the side walk', url, name), cls='mute'), cls='rh-strip')
    solid, shaky = sum(o == 'solid' for o in outs), sum(o in ('fragile', 'gap', 'misconception') for o in outs)
    counts = meta(n_of(len(outs), 'idea'), ', '.join(x for x in (solid and f'{solid} solid', shaky and f'{shaky} shaky') if x))
    return Div(P('Back on the paper. You ', 'learned ' if ok else 'looked at ', B(name), ' on the way.'),
               P(counts, ' · ', A('See the side walk', href=url), cls='mute'), cls='rh-strip')

def OwnCourse(c, st):
    "The line on the step that opened its own course for an idea: the link to the course, and how far you got when you came back."
    link = A('Open the course', href=course_url(c['id']), data_act='own-course')
    if not (c.get('origin') or {}).get('back_at'): return P('You are learning ', B(c['title']), ' as its own course. ', link, cls='rh-own-course')
    got = f"{st.done} of {n_of(st.total, 'idea')} done" if st and st.total else 'no stage yet'
    return P('Back from the course ', B(c['title']), f': {got}. ', link, cls='rh-own-course back')

def Needs(at, rows, strip=None, own=()):
    "The needs line, the strip when you just came back, the lines of its own courses, and the place for the chooser. `rows` is `(need, state)`."
    first = next((n.slug for n, st in rows if st == 'missing'), None)
    line = Div(Span('This needs', cls='lbl'), *[Need(n, st, n.slug == first) for n, st in rows], cls='rh-line') if rows else ''
    return Div(strip or '', *own, line, Div(id='rh-offer', aria_live='polite'), *assets(), cls='rh-needs', data_at=at, data_part='needs')

def GapLine(gaps, new=False):
    """After a miss that names a gap: the ideas your answer points at, and a way to learn the first one beside the step.
    The chooser opens under this line. When the first gap is not in your concepts yet (`new`), the click adds it, then opens the chooser."""
    names = ', '.join(name for _, name in gaps)
    go = Ask('Learn this gap ', gaps[0][0], Kbd('⌥B'), cls='rh-ask rh-gap', data_add='1' if new else None,
             title='Learn this idea beside the step: a quick look, a side walk or its own course. Your place here stays.')
    return P('Your answer shows a gap: ', B(names), '. ', go, cls='rh-gapline')

WAYS = dict(primer='A quick look', walk='A side walk', course='Its own course')

def Way(k, how, slug, meta, pick=False, why=''):
    "One depth: its key, its name and where it opens. The tutor's pick also has its reason."
    return Button(Span(str(k), cls='k'), B(WAYS[how]), Span(f' · {meta}', cls='meta'), Span(f"The tutor's pick: {why}.", cls='why') if pick else '',
                  type='button', cls='rh-way' + (' pick' if pick else ''), data_how=how, data_slug=slug)

def Offer(c, pick, chain, here, limit=False, own=False):
    """The chooser for "I don't get X": the tutor's pick first, with its reason, then the other two depths as quiet options.
    Quick and Side walk open beside this page; Its own course opens the course page. At the depth limit, only its own course.
    On the page of X itself (`own`), the head does not say to learn X first."""
    n = len(chain)
    meta = dict(primer='beside this page · 2 min · one check',
                walk=f"beside this page · {n_of(n, 'idea')}" if n > 1 else f"beside this page · up to {val('walks.chain')} ideas",
                course='a new goal · where you start, then stages')
    order = ['course'] if limit else [pick.how, *(h for h in WAYS if h != pick.how)]
    why = 'you are two side walks down, so it opens as its own course' if limit else pick.why
    ways = [Way(k, h, c.slug, meta[h], pick=k == 1, why=why) for k, h in enumerate(order, 1)]
    return Section(H2(f"Pick a way to learn {c.name}" if own else f"Learn {c.name} first"), Div(ways[0], cls='rh-pick'), Div(*ways[1:], cls='rh-ways') if ways[1:] else '',
                   Div(Span(f"Your place stays: {here}.", cls='mute'), Button('Not now ', Kbd('Esc'), type='button', cls='quiet small rh-shut'), cls='rh-foot-row'),
                   cls='rh-offer-card', role='dialog', aria_label=f'Learn {c.name}')

def NotFound(t, at):
    "A term that is not on the shelf: a GET writes nothing, so adding it is a choice."
    return Section(P(f"“{t}” is not in your concepts yet."),
                   Div(Button('Add it and learn it', type='button', cls='small', hx_post=Routes.term, hx_vals=json.dumps(dict(t=t, at=at)),
                              hx_target='#rh-offer', hx_swap='innerHTML', data_wait='Adding…'),
                       Button('Not now ', Kbd('Esc'), type='button', cls='quiet small rh-shut'), cls='row'),
                   cls='rh-offer-card', role='dialog', aria_label=f'Learn {t}')

def EndNote(name, ok, back, here, slug, outcome, walk=''):
    "The end of a side walk: what you learned, and the way back. detour.js sends `rh:done` from `data-rh-done`."
    return Div(P('You ', 'learned ' if ok else 'looked at ', B(name), ' on the way.', cls='lead-sum'),
               Primary(f"← Back to {short_title(walk) or 'the paper'}: {here}", href=back, rank=0), *assets(),
               cls='rh-end', data_rh_done=json.dumps(dict(slug=slug, outcome=outcome)))
