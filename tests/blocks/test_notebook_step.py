"A notebook step: the tutor writes the notebook spec onto the step, the card shows it, and Leela runs it."
from walk_data import *
from abhyasa.contract import NB_SPEC_CASES, validate_nb_spec

GOOD = NB_SPEC_CASES[0][0]
NB_RULE = 'Write one exercise and one real run'

def nb_step(cl, lr, i=1, spec=GOOD):
    "A started walk whose step `i` is a notebook check with `spec` on it."
    jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, i, check=dict(way='code', kind='notebook', depth=4, why=''), **(dict(nb=validate_nb_spec(spec)) if spec else {}))
    return jid

def test_notebook_card(mk, lr, walk_fake, tmp_path):
    "The notebook card shows the task, the data and the run, and Open in Leela. abhyasa offers no download and no path field: a folder that the notebook needs goes under Your data, or Leela asks for it."
    cl = mk(); jid = nb_step(cl, lr)
    card = cl.get(f'/w/{jid}/1/check').text
    for say in ('Check · notebook · runs in Leela', 'Open in Leela', '(an estimate)', 'none for this one', 'captions.jsonl', 'Predict: How many episodes',
                'Add this folder under Your data on the walk page, or set it in Leela.', 'Leela is not running. Start Leela, then press ⌥S again.', 'Get Leela',
                '1 more test that you cannot see.', 'abhyasa does not run this code'):
        assert say in card, say
    assert 'no people and no place' not in card and 'Download the notebook' not in card and 'name="path"' not in card
    assert lr.journey(jid).steps[1].get('qid') is None                                   # abhyasa opens no question on a notebook step
    assert cl.get(f'/w/{jid}/1/notebook').status_code == 404 and cl.post(f'/w/{jid}/1/data', data=dict(name='IMAGES', path='~/x')).status_code in (404, 405)

def test_an_old_code_check_is_a_notebook(mk, lr, walk_fake):
    "A step that kept a code check from an older abhyasa reads as a notebook check: it opens in Leela, and abhyasa runs nothing."
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why=''))
    assert lr.journey(jid).steps[1]['check']['kind'] == 'notebook'
    assert 'Open in Leela' in cl.get(f'/w/{jid}/1/check').text and cl.post(f'/w/{jid}/1/run', data=dict(source='x = 1')).status_code in (404, 405)

def test_card_links_to_leela_when_it_runs(mk, lr, walk_fake, monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path)); leela_file(tmp_path)
    cl = mk(); jid = nb_step(cl, lr)
    card = cl.get(f'/w/{jid}/1/check').text
    assert f'action="/w/{jid}/1/leela"' in card and 'target="_blank"' in card and 'hx-boost="false"' in card   # a form that notes the time, in a new tab
    assert 'Leela runs at 127.0.0.1:5011.' in card and 'Leela is not running' not in card and '/learn?' not in card
    page = cl.get(f'/w/{jid}/1').text
    assert page.count('/learn?walk=') == 0                                               # the card loads after the page; no second Leela line

def test_open_in_leela_notes_the_time(mk, lr, walk_fake, monkeypatch, tmp_path):
    "Open in Leela sets `leela_at` on the step and goes to the Leela link with the vault key. The card then says when."
    from abhyasa.contract import vault_key
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path)); leela_file(tmp_path)
    cl = mk(); jid = nb_step(cl, lr)
    r = cl.post(f'/w/{jid}/1/leela', follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == f'http://127.0.0.1:5011/learn?walk={jid}&step=1&v={vault_key(lr.vault.path)}'
    assert lr.journey(jid).steps[1]['leela_at'] > 0
    g = cl.get(f'/w/{jid}/1/leela', follow_redirects=False)   # the Mac app sends the new-window form as a GET
    assert g.status_code == 303 and g.headers['location'] == r.headers['location']
    card = cl.get(f'/w/{jid}/1/check').text
    assert 'Opened in Leela at ' in card and 'The result comes back here.' in card and 'Leela runs at' not in card

def test_open_in_leela_stamps_the_idea_of_the_link(mk, lr, walk_fake, monkeypatch, tmp_path):
    "An editor move from another request while Open in Leela runs: the stamp and the place map go to the idea that the link opens, not to the idea that moved in."
    import threading
    import abhyasa.blocks.walk.app as W
    from abhyasa.journey import _jlock
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path)); leela_file(tmp_path)
    cl = mk(); jid = nb_step(cl, lr)
    a, b = [s['slug'] for s in lr.journey(jid).steps[:2]]
    def swap():
        with _jlock(jid):
            j = lr.journey(jid); lr.put_journey({**j, 'steps': [j.steps[1], j.steps[0], *j.steps[2:]]})
    mover, real = threading.Thread(target=swap), W.leela_link
    def link(j, i=None, **kw):
        out = real(j, i, **kw)
        mover.start(); mover.join(.5)   # the move runs now, unless Open in Leela holds the lock of the walk
        return out
    monkeypatch.setattr(W, 'leela_link', link)
    r = cl.post(f'/w/{jid}/1/leela', follow_redirects=False)
    mover.join()
    assert r.status_code == 303 and 'step=1' in r.headers['location']
    j = lr.journey(jid)
    assert j.leela_opened == {'1': b}
    at = {s['slug']: s.get('leela_at') for s in j.steps}
    assert at[b] and not at[a]

def test_open_in_leela_with_no_leela(mk, lr, walk_fake):
    "With no Leela, the press goes back to the step and notes no time. An unknown step is 404."
    cl = mk(); jid = nb_step(cl, lr)
    r = cl.post(f'/w/{jid}/1/leela', follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == f'/w/{jid}/1' and 'leela_at' not in lr.journey(jid).steps[1]
    assert cl.post(f'/w/{jid}/99/leela', follow_redirects=False).status_code == 404

def test_nb_spec_writes_the_step(mk, lr, walk_fake):
    walk_fake.rules[NB_RULE] = GOOD
    cl = mk(); jid = nb_step(cl, lr, spec=None)
    first = cl.get(f'/w/{jid}/1/check').text
    assert 'Writing the notebook…' in first or 'Open in Leela' in first
    assert wait_for(lambda: lr.journey(jid).steps[1].get('nb'), 10) == validate_nb_spec(GOOD)
    assert 'Open in Leela' in cl.get(f'/w/{jid}/1/check').text

def test_bad_spec_twice_leaves_nb_unset(mk, lr, walk_fake):
    walk_fake.rules[NB_RULE] = {**GOOD, 'data': [{**GOOD['data'][0], 'path': '/etc/passwd'}]}
    cl = mk(); jid = nb_step(cl, lr, spec=None)
    cl.get(f'/w/{jid}/1/check')
    why = wait_for(lambda: lr.journey(jid).steps[1].get('nb_why') or None, 10)
    assert why.startswith('data') and not lr.journey(jid).steps[1].get('nb')
    card = cl.get(f'/w/{jid}/1/check').text
    assert 'The tutor could not write the notebook' in card and 'Try again' in card
    walk_fake.rules[NB_RULE] = GOOD
    assert 'Writing the notebook…' in cl.post(f'/w/{jid}/1/check').text or lr.journey(jid).steps[1].get('nb')
    assert wait_for(lambda: lr.journey(jid).steps[1].get('nb'), 10)

def test_walk_made_writes_each_notebook(mk, lr, walk_fake, monkeypatch):
    "A tool walk whose code idea is a notebook check gets its spec in the background, with no page load."
    walk_fake.rules[NB_RULE] = GOOD
    walk_fake.rules['Return JSON: {"concepts"'] = dict(concepts=[{**c, 'ways': ['code', 'maths']} if c['name'] == 'Softmax' else c for c in EXTRACT_REPLY['concepts']])
    monkeypatch.setattr('abhyasa.journey.hands_most', lambda n: n)   # no cap, so the code idea keeps its notebook check
    cl = mk()
    jid = cl.post('/walk/new', data=dict(ref=add_paper(lr), tool='on')).headers['hx-redirect'].split('/')[-1]
    ix = [i for i, s in enumerate(lr.journey(jid).steps) if s['check']['kind'] == 'notebook']
    assert ix and all(lr.journey(jid).steps[i]['check']['why'].endswith('runs in Leela') for i in ix)
    assert wait_for(lambda: all(lr.journey(jid).steps[i].get('nb') for i in ix) or None, 10)

def test_path_why_is_the_old_name_of_data_path_why():
    "Leela imports `abhyasa.contract.path_why`, so the old name stays. The folder rule of the settings has its own name."
    from abhyasa import contract, settings
    assert contract.path_why is contract.data_path_why and not hasattr(settings, 'path_why')
    assert contract.data_path_why('~/a/../b') == 'the path has ..'

def test_data_path_under_a_hidden_home(monkeypatch, tmp_path):
    "A home folder under a folder that starts with a dot (as /Users/x/.sandbox/home): a path in it is good, and a hidden folder in it is still refused. The case lists still pass."
    from abhyasa.contract import data_path_why, NB_SPEC_CASES, RUN_CASES, HANDOFF_CASES, run_ok, read_handoff
    home = tmp_path/'.sandbox'/'home'; (home/'Pictures').mkdir(parents=True)
    monkeypatch.setenv('HOME', str(home))
    assert data_path_why('~/Pictures/comic') == data_path_why(f'{home}/Pictures/comic') == ''
    assert data_path_why('~/.ssh') == data_path_why(f'{home}/.aws/credentials') == 'a part of the path starts with a dot'
    assert data_path_why(f'{tmp_path}/.sandbox/other') == 'the path is not in your home folder'
    for spec, key in NB_SPEC_CASES:
        try: validate_nb_spec(spec); got = None
        except ValueError as e: got = str(e).split(':')[0]
        assert got == key, (spec, key, got)
    assert all(run_ok(a) == ok for a, ok in RUN_CASES)
    from abhyasa.contract import handoff
    assert all(handoff(**kw) == path and read_handoff(path.split('?', 1)[1])['walk'] == kw.get('jid', '') for kw, path in HANDOFF_CASES)

def test_two_apps_link_their_own_vault(lr, walk_fake, monkeypatch, tmp_path):
    "Two apps in one process, on two vaults: the Leela link of each app has the key of its own vault."
    from starlette.testclient import TestClient
    from abhyasa.app import mk_app
    from abhyasa.store import temp_learning
    from abhyasa.contract import vault_key
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path)); leela_file(tmp_path)
    lr2 = temp_learning()
    cls = [TestClient(mk_app(l, walk_fake, transcribe=lambda a, hint='': '', names=['walk'], hosts=('testserver',))) for l in (lr, lr2)]   # the second app is made last
    for cl, l in zip(cls, (lr, lr2)):
        jid = nb_step(cl, l)
        r = cl.post(f'/w/{jid}/1/leela', follow_redirects=False)
        assert r.headers['location'].endswith(f'&v={vault_key(l.vault.path)}'), r.headers['location']
    assert vault_key(lr.vault.path) != vault_key(lr2.vault.path)

def test_plan_says_writing_only_while_a_job_runs(mk, lr, walk_fake):
    "The plan row of a notebook step says Writing the notebook only while its job row runs. Else it says when the notebook is written, or that the tutor could not write it."
    from abhyasa.jobs import job_start, job_end
    cl = mk(); jid = nb_step(cl, lr, spec=None); key = f"walk:{jid}:nb:{lr.journey(jid).steps[1]['slug']}"
    assert wait_for(lambda: None if any(r.state == 'running' for r in lr.jobs().values()) else True)
    lr.walk_step(jid, 1, nb_why=None)   # the fake gives no spec, so an early job could not write it
    plan = cl.get(f'/w/{jid}').text
    assert 'Writing the notebook…' not in plan and 'the notebook is written when you open the idea' in plan
    job_start(lr, key, 'notebook')
    assert 'Writing the notebook…' in cl.get(f'/w/{jid}').text
    job_end(lr, key, 'failed'); lr.walk_step(jid, 1, nb_why='the model did not answer')
    plan = cl.get(f'/w/{jid}').text
    assert 'Writing the notebook…' not in plan and 'the tutor could not write the notebook' in plan
