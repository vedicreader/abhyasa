"Your sources: the vault shelves the tutor grounds in, the vedicreader library, and the indexers you start yourself."
import time
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import Page, RouteOverrides, n_of
from abhyasa.ground import VedicSource, index_ramabana, index_notebooks, RAMA_CFG
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'sources')

INDEXERS = dict(
    ramabana=('ramabana sessions', 'One document for each session from ~/.config/ramabana, on the shelf "ramabana".'),
    notebooks=('leela agent sessions', 'Each notebook in a _leela_agent_sessions folder under ~/code, on the shelf "notebooks".'))

def connect(app, ctx):
    lr = ctx.learning

    def page():
        shelves = [s for s in lr.vault.shelves() if not str(s['store']).startswith(('tmp', 'dialogprobe'))]
        vs = VedicSource()
        return Page('Sources', H1('Sources'),
            P('The tutor uses these sources for its questions. It links each concept to the places that name it. It reads the sources and does not change them.', cls='mute'),
            H2('Vault shelves'),
            Ul(*[Li(Span(s['store']), Span(f"  {n_of(s['docs'], 'document')}", cls='mute')) for s in shelves], cls='plain'),
            H2('vedicreader library'),
            P(f"{len(vs.dbs())} verse databases in {vs.dir}." if vs.dbs() else 'Not found. Set VEDICREADER_ROOT to the vedicreader repo.', cls='mute'),
            Details(Summary('More'),
                    P('vedicreader: Sanskrit lessons and terms, and the jyotiṣa grahas, rāśis and nakṣatras, from the repo files.', cls='mute'),
                    Button('Import vedicreader', hx_post='/add/vedicreader', hx_target='#vr', data_wait='Importing…', data_skel='#vr'), Div(id='vr'), cls='more'),
            H2('Add your sessions'),
            P('Each button adds a shelf to your vault, so every tool can search it. They change no other shelf. A second run skips what did not change.', cls='mute'),
            *[Div(Button(f'Index {t}', hx_post=Routes.index.format(what=k), hx_target=f'#ix-{k}', data_wait='Indexing…', data_skel=f'#ix-{k}'),
                  Span(d, cls='mute'), Div(id=f'ix-{k}', cls='ix'), cls='row') for k, (t, d) in INDEXERS.items()],
            on='Library', sub='Sources')

    def index(what:str):
        t = time.time()
        if what == 'ramabana': n = index_ramabana(lr.vault, RAMA_CFG)
        elif what == 'notebooks': n = index_notebooks(lr.vault, [str(Path.home()/'code')], only_agent=True)
        else: return P('Unknown source.', cls='mute')
        return P(', '.join(f'{v} {k}' for k, v in n.items()) + f' in {time.time() - t:.0f} s.', cls='mute')

    RouteOverrides.subtabs.setdefault('Library', []).append(('Sources', Routes.base, 1))
    app.get(Routes.base)(page)
    app.post(Routes.index)(index)
