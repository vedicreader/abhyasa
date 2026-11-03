"One file as a source: from the Start box and Pick files. Who the walk is for and No code. Make this walk again with other sources and your words."
import re, subprocess, pytest
from pathlib import Path
from fastcore.nbio import new_nb, mk_cell, write_nb
import abhyasa.blocks.add.app as add_app
from starlette.testclient import TestClient
from abhyasa.sources import vault_roots, FILE_TYPE
from test_sources_folder import wait_for_walk
from test_stop_again import ended

PLAN = 'You plan a learning path'
STEPS = dict(title='Agents', subject='ml', steps=[dict(name='Tool calls', statement='An agent calls a tool and reads its answer.', slug='', why='It is the base.',
                                                     needs=[], ways=['code'], hands='notebook', doc='01_agents')])

@pytest.fixture
def home(tmp_path, monkeypatch):
    "A temp home with the folder `karma`: two notebooks and a note. Only `01_agents.ipynb` is the source in these tests."
    monkeypatch.setattr(Path, 'home', lambda: tmp_path); monkeypatch.setenv('HOME', str(tmp_path))
    d = tmp_path/'karma'; d.mkdir()
    write_nb(new_nb([mk_cell('# Agentic engineering\n\nAn agent calls a tool, reads the answer, and decides what to do next.', 'markdown')]), d/'01_agents.ipynb')
    write_nb(new_nb([mk_cell('# Kernels\n\nA GPU kernel runs one small program on many cores.', 'markdown')]), d/'02_kernels.ipynb')
    (d/'notes.md').write_text('# Notes\n\nOther notes.')
    monkeypatch.setattr(add_app, 'can_pick', lambda: True)
    return tmp_path

def planner(fake, plan=STEPS):
    "The planner gives `plan`, and each prompt that it gets is kept."
    got = []
    fake.rules[PLAN] = lambda p, sp: (got.append(p), plan)[1]
    return got

def test_one_file_from_start_files_only_that_file_for_who_it_is_for(mk, lr, walk_fake, home):
    "A file chip files that file and not its folder. The planner sees only it, and who the walk is for. With No code, no check is a notebook."
    got, nb = planner(walk_fake), home/'karma'/'01_agents.ipynb'
    cl = mk()
    h = cl.get('/learn/read', params=dict(q='Teach agentic engineering', extra=[str(nb)])).text
    assert f'name="sources" value="file:{nb}"' in h and 'only this file is added when you press Start' in h
    url = wait_for_walk(cl, cl.post('/walk/new', data=dict(q='Teach agentic engineering', sources=[f'file:{nb}'], chips='1',
                                                           audience='people who do not write code', no_code='on')))
    j = lr.journey(url.split('/')[-1])
    assert j.chips == [f'file:{nb}'] and (j.audience, j.no_code) == ('people who do not write code', True)
    assert vault_roots(lr) == {str(nb.resolve()): 1}   # not 02_kernels, not notes.md
    assert '01_agents' in got[0] and '02_kernels' not in got[0] and 'people who do not write code' in got[0] and 'No code:' in got[0]
    assert [s['check']['kind'] for s in j.steps] == ['short']   # the plan asked for a notebook; No code makes it a short check

def test_without_no_code_the_plan_keeps_its_notebook(mk, lr, walk_fake, home):
    "The same plan with no No code keeps the notebook that builds the goal: No code is what changes it."
    planner(walk_fake); nb = home/'karma'/'01_agents.ipynb'
    cl = mk()
    url = wait_for_walk(cl, cl.post('/walk/new', data=dict(q='Teach agentic engineering', sources=[f'file:{nb}'], chips='1')))
    assert [s['check']['kind'] for s in lr.journey(url.split('/')[-1]).steps] == ['notebook']

def test_a_file_of_another_type_is_refused(mk, home):
    (p := home/'karma'/'slides.key').write_text('x')
    h = mk().get('/learn/read', params=dict(q='Teach agentic engineering', extra=[str(p)])).text
    assert FILE_TYPE.split(':')[0] in h and f'name="sources" value="file:{p}"' not in h

def test_pick_files_opens_the_file_chooser(mk, home, monkeypatch):
    "Pick files is beside Pick folders. It opens `choose file`, with more than one allowed, and gives one path for each file."
    calls, nb = [], home/'karma'/'01_agents.ipynb'
    monkeypatch.setattr(add_app, '_osa', lambda args, **kw: (calls.append(args), subprocess.CompletedProcess(args, 0, stdout=f'{nb}\n'))[1])
    cl = TestClient(mk().app, client=('127.0.0.1', 50000))
    assert 'id="start-pick-files"' in cl.get('/').text and 'Who is it for' in cl.get('/').text
    assert cl.post('/learn/pick', params=dict(files='1')).json() == dict(paths=[str(nb)])
    assert 'choose file with prompt' in calls[0][2] and 'with multiple selections allowed' in calls[0][2]

def test_pick_in_make_this_walk_again_gives_ticked_rows(mk, home, monkeypatch):
    "In the form of Make this walk again, Pick files gives one ticked `add` row for each file, which you can untick. Cancel gives no row."
    nb = home/'karma'/'01_agents.ipynb'
    out = [f'{nb}\n']
    monkeypatch.setattr(add_app, '_osa', lambda args, **kw: subprocess.CompletedProcess(args, 0, stdout=out[0]))
    cl = TestClient(mk().app, client=('127.0.0.1', 50000))
    h = cl.post('/learn/pick', data=dict(rows='1', files='1')).text
    assert f'name="add" value="{nb}" checked' in h and '01_agents.ipynb' in h and 'a file' in h
    out[0] = ''
    assert 'name="add"' not in cl.post('/learn/pick', data=dict(rows='1')).text

def test_make_this_walk_again_uses_the_sources_and_words_of_its_form(mk, lr, walk_fake, home):
    """A walk from the whole folder, made again with the folder unticked and the one notebook added: the new plan sees only that notebook,
    who it is for and your words, and the walk keeps the new sources. A source that abhyasa cannot use shows the form again, and no job starts."""
    got, nb = planner(walk_fake), home/'karma'/'01_agents.ipynb'
    cl = mk()
    url = wait_for_walk(cl, cl.post('/walk/new', data=dict(q='Teach agentic engineering', sources=[f'folder:{home/"karma"}'], chips='1')))
    jid = url.split('/')[-1]
    assert '02_kernels' in got[0]
    page = cl.get(url).text
    assert 'name="asks"' in page and f'value="folder:{home/"karma"}"' in page and 'name="audience"' in page
    assert 'data-act="pick-folders"' in page and 'data-act="pick-files"' in page   # the choosers are in the form, beside the typed field
    bad = cl.post(f'/w/{jid}/replan', data=dict(form='1', sources=[f'folder:{home/"karma"}'], add='not a source here')).text
    assert 'abhyasa cannot use not a source here as a source.' in bad and lr.job(f'walk:{jid}:replan') is None
    r = cl.post(f'/w/{jid}/replan', data=dict(form='1', add=['', str(nb)], audience='people who do not write code', asks='Use only the agentic engineering notebook.'))   # the typed field is empty; the notebook is a picked row
    assert r.headers['hx-redirect'] == f'/w/{jid}#change'
    assert ended(lr, f'walk:{jid}:replan').state == 'done'
    p = got[-1]
    assert '01_agents' in p and '02_kernels' not in p and 'Use only the agentic engineering notebook.' in p and 'people who do not write code' in p
    j = lr.journey(jid)
    assert j.chips == [f'file:{nb}'] and j.audience == 'people who do not write code' and j.chip_counts == {f'file:{nb}': 1}
