"The parts of a detour: the needs line under the title of a step, the offer of three ways down, the gap line, and the way back."
import json
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import asset_css, asset_js
from abhyasa.settings import val
from .cfg import Routes

_P = Path(__file__).parent
STATE = dict(learned='learned', today='learned on the way today', missing='you have not learned it')

def assets(): return asset_css(_P/'detour.css'), asset_js(_P/'detour.js')

def step_url(jid, i): return Routes.of(Routes.step, jid=jid, i=i)

def Ask(label, t, *c, cls='rh-ask'):
    "A button that opens the offer for idea or term `t` (detour.js)."
    return Button(label, *c, type='button', cls=f'quiet small {cls}', data_t=t)

def Need(n, state, first):
    "One idea that the step needs: its name, its state, and Open beside on the first one that you have not learned."
    return Span(A(n.name, href=f'/c/{n.slug}', cls='n'), Span(f' · {STATE[state]}', cls=f'st {state}'),
                Ask('open beside ', n.slug, Kbd('⌥B')) if first else '', cls='need')

def Strip(name, ok, sid, outs):
    "The strip after a side walk: what you learned on the way, and how the checks went."
    solid, shaky = sum(o == 'solid' for o in outs), sum(o in ('fragile', 'gap', 'misconception') for o in outs)
    counts = [f"{len(outs)} {'idea' if len(outs) == 1 else 'ideas'}", ', '.join(x for x in (solid and f'{solid} solid', shaky and f'{shaky} shaky') if x)]
    return Div(P('Back on the paper. You ', 'learned ' if ok else 'looked at ', B(name), ' on the way.'),
               P(' · '.join(x for x in counts if x), ' · ', A('See the side walk', href=Routes.of(Routes.walk, jid=sid)), cls='mute'), cls='rh-strip')

def Needs(at, rows, strip=None):
    "The needs line, the strip when you just came back, and the place for the offer. `rows` is `(need, state)`."
    first = next((n.slug for n, st in rows if st == 'missing'), None)
    line = Div(Span('This needs', cls='lbl'), *[Need(n, st, n.slug == first) for n, st in rows], cls='rh-line') if rows else ''
    return Div(strip or '', line, Div(id='rh-offer', aria_live='polite'), *assets(), cls='rh-needs', data_at=at)

def GapLine(gaps):
    "After a miss that names a gap: the ideas your answer points at, and a way to learn the first one beside the step."
    names = ', '.join(name for _, name in gaps)
    return P('Your answer points at: ', B(names), '. ', Ask('Learn it beside ', gaps[0][0], Kbd('⌥B'), cls='rh-ask rh-gap'), cls='rh-gapline')

WAYS = dict(primer='A quick primer', walk='A short side walk', session='Its own session ↗')

def Way(k, how, slug, title, meta, body, why=''):
    return Button(Div(B(title), Span(str(k), cls='k'), cls='wt'), Span(meta, cls='meta'), Span(body, cls='body'),
                  Span(f"The tutor's pick: {why}.", cls='why') if why else '', type='button', cls='rh-way' + (' pick' if why else ''),
                  data_how=how, data_slug=slug)

def Offer(c, pick, chain, here, limit=False):
    "One sunken card: how to learn idea `c` before you go on. The tutor's pick is marked. At the depth limit, only its own session."
    names = ', '.join(chain)
    walk = f"{names}. One check on each." if len(chain) > 1 else f"The tutor plans up to {val('walks.chain')} ideas. One check on each."
    ways = [('primer', 'beside this page · 2 min', 'The idea in short, and one check.'),
            ('walk', f"beside this page · {len(chain)} ideas" if len(chain) > 1 else f"beside this page · up to {val('walks.chain')} ideas", walk),
            ('session', 'a new tab · as long as you need', f"{c.name} from the start, as its own walk. This page stays open.")]
    if limit: ways = ways[2:]
    why = 'you are two side walks down, so this one opens in a new tab' if limit else pick.why
    cards = [Way(k, how, c.slug, WAYS[how], meta, body, why if how == ('session' if limit else pick.how) else '') for k, (how, meta, body) in enumerate(ways, 1)]
    return Section(Div(Span('Learn it first, then come back', cls='lbl'), Span('Esc closes this', cls='lbl'), cls='rh-head'),
                   H2(f"{c.name}: how do you want to learn it?"), Div(*cards, cls='rh-ways'),
                   Div(Span(f"Your place here stays: {here}, and the open check.", cls='mute'),
                       Button('Not now ', Kbd('Esc'), type='button', cls='quiet small rh-shut'), cls='rh-foot-row'),
                   cls='rh-offer-card', role='dialog', aria_label=f'Learn {c.name}')

def NotFound(t, at):
    "A term that is not on the shelf: a GET writes nothing, so adding it is a choice."
    return Section(P(f"“{t}” is not on your shelf yet."),
                   Div(Button('Add it and learn it', type='button', cls='small', hx_post=Routes.term, hx_vals=json.dumps(dict(t=t, at=at)),
                              hx_target='#rh-offer', hx_swap='innerHTML', data_wait='Adding…'),
                       Button('Not now ', Kbd('Esc'), type='button', cls='quiet small rh-shut'), cls='row'),
                   cls='rh-offer-card', role='dialog', aria_label=f'Learn {t}')

def EndNote(name, ok, back, here, slug, outcome):
    "The end of a side walk: what you learned, and the way back. detour.js sends `rh:done` from `data-rh-done`."
    return Div(P('You ', 'learned ' if ok else 'looked at ', B(name), ' on the way.', cls='lead-sum'),
               A(f'← Back to the paper: {here}', href=back, cls='btn go'), *assets(),
               cls='rh-end', data_rh_done=json.dumps(dict(slug=slug, outcome=outcome)))
