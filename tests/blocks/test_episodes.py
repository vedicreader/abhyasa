"The Ramayana episodes of vedicreader as a source: the source line of an episode, its link to a running vedicreader, and the app's source list."
import json, os
from pathlib import Path
from fasthtml.common import to_xml
from fastcore.basics import AttrDict
from starlette.testclient import TestClient
import abhyasa.ground as G
from abhyasa.ground import VedicStory
from abhyasa.core import SourceLine, Cites, source_of
from abhyasa.core.cfg import cfg
from abhyasa.app import mk_app
from abhyasa.journey import _topic_read

VR = Path(__file__).parents[1]/'data/vr'
EP = dict(src='vedicstory', ref='VR 1.1.1-5', title='Vālmīki questions Nārada', section='Bāla, sarga 1, verses 1-5', episode='valmiki_questions_narada',
          url=str(VR/'static/story/ramayana/episodes.json'), text='Vālmīki asks Nārada who in the world has every virtue.')

def vr_file(tmp_path, monkeypatch, url='http://127.0.0.1:5010/', pid=None):
    "The address file of a running vedicreader; the pid of this test makes it look alive."
    f = tmp_path/'vr.json'; f.write_text(json.dumps(dict(url=url, pid=pid or os.getpid())))
    monkeypatch.setenv('ABHYASA_VR_FILE', str(f)); return f

def test_episode_line_with_no_vedicreader(monkeypatch, tmp_path):
    "With no vedicreader running, the line is your source, the episode name and its place in the poem, and no link."
    monkeypatch.setenv('ABHYASA_VR_FILE', str(tmp_path/'none.json')); monkeypatch.setitem(cfg, 'vedicreader', '')
    h = to_xml(SourceLine(source_of(EP)))
    assert '>your source<' in h and 'Vālmīki questions Nārada' in h and 'Bāla, sarga 1, verses 1-5' in h
    assert '<a ' not in h and 'episodes.json' not in h   # the file path is not a link

def test_episode_line_links_to_a_running_vedicreader(monkeypatch, tmp_path):
    "With vedicreader running on this computer, the name and `Open in vedicreader` open the episode page in a new tab."
    vr_file(tmp_path, monkeypatch)
    h = to_xml(SourceLine(source_of(EP)))
    assert h.count('href="http://127.0.0.1:5010/story/ramayana/e/valmiki_questions_narada"') == 2 and 'Open in vedicreader' in h and 'target="_blank"' in h
    assert 'Open in vedicreader' in to_xml(Cites([EP]))
    assert '<a ' not in to_xml(SourceLine(source_of(EP), room=True))   # the room has no link

def test_episode_link_is_local_and_safe(monkeypatch, tmp_path):
    "No link for an address that is not on this computer, for a stopped vedicreader, or for an id that is not an episode id."
    monkeypatch.setitem(cfg, 'vedicreader', '')
    vr_file(tmp_path, monkeypatch, url='http://evil.example:5010/'); assert '<a ' not in to_xml(SourceLine(source_of(EP)))
    vr_file(tmp_path, monkeypatch, pid=2**22 + 12345); assert '<a ' not in to_xml(SourceLine(source_of(EP)))
    vr_file(tmp_path, monkeypatch)
    for bad in ('../x', 'a/b', 'x" onclick="alert(1)', 'A' * 81): assert '<a ' not in to_xml(SourceLine(source_of({**EP, 'episode': bad})))
    assert '<a ' not in to_xml(SourceLine(source_of({**EP, 'src': 'notes'})))   # only an episode gets the link

def test_walk_step_keeps_the_episode_place(monkeypatch):
    "A walk step on an episode keeps its Vālmīki cite, its place in the poem and its id, so its source line can show them."
    r = _topic_read(AttrDict(name='Nārada', slug='narada'), [VedicStory(VR)])
    assert (r['src'], r['ref'], r['section'], r['episode']) == ('vedicstory', 'VR 1.1.1-5', 'Bāla, sarga 1, verses 1-5', 'valmiki_questions_narada')
    assert r['text'].startswith('Vālmīki asks Nārada') and 'Acts: Vālmīki, Nārada.' in r['text']

def test_app_reads_the_episodes_on_its_pool(monkeypatch, lr, fake):
    "The app adds the episodes to its sources, reads them on its pool, and the Sources page says how many it has."
    monkeypatch.setattr(G, 'VR_ROOT', VR)
    app = mk_app(lr, fake, transcribe=lambda a, hint='': '', sources=None, hosts=('testserver',))
    st = [s for s in app.state.svc['sources'] if s.name == 'vedicstory']
    assert len(st) == 1 and st[0].pool is app.state.svc['pool']
    st[0]._job.result(timeout=10)
    assert st[0].search('Nārada')[0].ref == 'VR 1.1.1-5'
    assert '3 Ramayana episodes in' in TestClient(app).get('/sources').text

def test_app_without_the_episodes(monkeypatch, lr, fake, tmp_path):
    "With no episode files, the app has no episode source, and the Sources page says so in one line."
    monkeypatch.setattr(G, 'VR_ROOT', tmp_path)
    app = mk_app(lr, fake, transcribe=lambda a, hint='': '', sources=None, hosts=('testserver',))
    assert not [s for s in app.state.svc['sources'] if s.name == 'vedicstory']
    t = TestClient(app).get('/sources').text
    assert 'Ramayana episodes' in t and 'Not found. Set VEDICREADER_ROOT' in t
