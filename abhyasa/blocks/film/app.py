"""Videos of demos: a film is a demo as a narrated explainer video (`abhyasa.film`). The concept page shows the film of each demo,
or a button that makes it. The video, its subtitles and the wait of its job are here."""
from pathlib import Path
from fasthtml.common import *
from starlette.responses import FileResponse
from rupaka.film import can_film
from abhyasa.core import hook
from abhyasa.film import queue_film, film_state, vtt
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'tutor')
MOST = 3   # the newest demos of a concept that get a card

def connect(app, ctx):
    lr, tutor = ctx.learning, ctx.tutor

    def card(slug:str):
        "The card of the film of demo `slug`: the video, the wait, the failure, or the Make button."
        d = lr.demo(slug)
        if d is None: return Response('No such demo.', status_code=404)
        title, st = d.spec.get('title') or slug, film_state(tutor, slug)
        if st == 'running': return ui.Pending(slug, title)
        if (f := lr.film(slug)): return ui.FilmCard(f)
        if st == 'failed': return ui.Failed(slug, title, (lr.job(f'film:{slug}') or {}).get('why', ''))
        return ui.MakeCard(d) if can_film() else ui.NoTools(slug)

    def make(slug:str):
        "Start the job that draws the film of demo `slug`; its wait."
        if lr.demo(slug) is None: return Response('No such demo.', status_code=404)
        if not can_film(): return ui.NoTools(slug)
        queue_film(tutor, slug)
        return card(slug)

    def video(slug:str):
        f = lr.film(slug)
        return FileResponse(f.path, media_type='video/mp4') if f else Response('No such video.', status_code=404)

    def subs(slug:str):
        f = lr.film(slug)
        p = Path(f.path).with_suffix('.srt') if f else None
        return Response(vtt(p.read_text()), media_type='text/vtt') if p and p.exists() else Response('No subtitles.', status_code=404)

    @hook('concept_more')
    def films(c):
        "Videos: one card for each of the newest demos of concept `c`. With no film and no tools to draw one, the part does not show."
        ds = lr.demos(c.slug)[:MOST]
        cards = [card(d.slug) for d in ds if lr.film(d.slug) or film_state(tutor, d.slug) != 'none' or can_film()]
        return ui.Films(cards) if cards else None

    app.get(Routes.video)(video)
    app.get(Routes.subs)(subs)
    app.get(Routes.card)(card)
    app.post(Routes.make)(make)
