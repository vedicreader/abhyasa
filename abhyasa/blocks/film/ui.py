"The Videos part of a concept page: one card for each demo, with its video or a button that makes it."
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import asset_css
from .cfg import Routes

_P = Path(__file__).parent
WAIT = 'job, every 20s'   # a wait loads again on an event of the job stream, and every 20 seconds

def assets(): return (asset_css(_P/'film.css'),)

def _at(route, slug): return Routes.of(route, slug=slug)

def _mins(s) -> str: m, s = divmod(round(s), 60); return f'{m}:{s:02}'

def FilmCard(f):
    "The video of a film, with its subtitles, its length, and Make it again."
    v = f"?v={int(f.get('at', 0))}"
    return Figure(Video(Source(src=_at(Routes.video, f.slug) + v, type='video/mp4'),
                        Track(kind='captions', src=_at(Routes.subs, f.slug) + v, srclang='en', label='English', default=True),
                        controls=True, preload='metadata', playsinline=True),
                  Figcaption(Span(f.title, cls='n'), Span(_mins(f.secs) + ('' if f.voiced else ', subtitles only'), cls='mute'),
                             Button('Make it again', cls='quiet', **_make(f.slug))),
                  id=f'film-{f.slug}', cls='film-card')

def _make(slug): return dict(hx_post=_at(Routes.make, slug), hx_target=f'#film-{slug}', hx_swap='outerHTML')

def MakeCard(d):
    "A demo with no film: the button that makes one."
    return Div(Span(d.spec.get('title') or d.slug, cls='n'), Button('Make a video', **_make(d.slug)),
               P('The tutor draws the demo as a short video, with a voice. It takes a minute or two.', cls='mute'), id=f'film-{d.slug}', cls='film-card make')

def Pending(slug, title):
    "The film of a demo draws now: its card loads again when the job changes."
    return Div(Span(title, cls='n'), P('Drawing the video. You can leave this page.', cls='mute making'),
               hx_get=_at(Routes.card, slug), hx_trigger=WAIT, hx_swap='outerHTML', id=f'film-{slug}', cls='film-card pending', data_job=f'film:{slug}')

def Failed(slug, title, why):
    return Div(Span(title, cls='n'), P(why or 'The video did not draw.', cls='mute'), Button('Try again', **_make(slug)), id=f'film-{slug}', cls='film-card failed')

def NoTools(slug):
    return Div(P('This Mac cannot draw videos yet. Install the extra: pip install "rupaka[film]", and ffmpeg.', cls='mute'), id=f'film-{slug}', cls='film-card')

def Films(cards): return Section(H3('Videos'), *assets(), Div(*cards, cls='film-cards'), cls='films', data_part='films')
