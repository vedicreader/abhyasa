"The Videos part of a concept page: a film shows with its subtitles, a demo with no film has a Make button, and the job draws it."
from pathlib import Path
from rupaka.spec import gallery
import abhyasa.blocks.film.app as fa
import abhyasa.film as F

SRT = '1\n00:00:00,000 --> 00:00:02,500\nA line.\n'

def fake_draw(p, out, wav=None, res=''):
    Path(out).write_bytes(b'\0\0\0\x18ftypmp42' + b'\0' * 64); Path(out).with_suffix('.srt').write_text(SRT); return out

def put_demo(lr): return lr.put_demo(gallery()['reciprocal-rank-fusion'], 'reciprocal-rank-fusion')

def test_no_tools_no_part(mk, lr, monkeypatch):
    monkeypatch.setattr(fa, 'can_film', lambda: False)
    put_demo(lr)
    assert 'data-part="films"' not in mk().get('/c/reciprocal-rank-fusion').text

def test_film_shows_with_subtitles(mk, lr, monkeypatch):
    monkeypatch.setattr(fa, 'can_film', lambda: False)
    d = put_demo(lr)
    F.make_film(lr, d.slug, voiced=False, draw=fake_draw)
    cl = mk()
    page = cl.get('/c/reciprocal-rank-fusion').text
    assert f'/film/{d.slug}/video' in page and f'/film/{d.slug}/subs' in page and 'subtitles only' in page
    r = cl.get(f'/film/{d.slug}/video')
    assert r.status_code == 200 and r.headers['content-type'] == 'video/mp4'
    assert cl.get(f'/film/{d.slug}/subs').text.startswith('WEBVTT')
    assert cl.get('/film/nope/video').status_code == 404

def test_make_runs_the_job(mk, lr, monkeypatch):
    monkeypatch.setattr(fa, 'can_film', lambda: True)
    real = F.make_film
    monkeypatch.setattr(F, 'make_film', lambda lr, slug, **kw: real(lr, slug, voiced=False, draw=fake_draw))
    d = put_demo(lr)
    cl = mk()
    assert 'Make a video' in cl.get('/c/reciprocal-rank-fusion').text
    cl.post(f'/film/{d.slug}/make')
    F._POOL.submit(lambda: None).result(timeout=30)   # the pool runs one job at a time: this waits for the film
    assert '<video' in cl.get(f'/film/{d.slug}/card').text
    assert cl.post('/film/nope/make').status_code == 404
