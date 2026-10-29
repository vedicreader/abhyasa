"A notebook step: the tutor writes the notebook spec onto the step, the card shows it, and Leela runs it."
from walk_data import *
from abhyasa.contract import NB_SPEC_CASES, validate_nb_spec
from abhyasa.check import load_tests
import json

GOOD = NB_SPEC_CASES[0][0]
NB_RULE = 'Write one exercise and one real run'

def nb_step(cl, lr, i=1, spec=GOOD):
    "A started walk whose step `i` is a notebook check with `spec` on it."
    jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, i, check=dict(way='code', kind='notebook', depth=4, why=''), **(dict(nb=validate_nb_spec(spec)) if spec else {}))
    return jid

def test_notebook_card_and_download(mk, lr, walk_fake, tmp_path):
    cl = mk(); jid = nb_step(cl, lr)
    card = cl.get(f'/w/{jid}/1/check').text
    for say in ('Check · notebook · runs in Leela', 'Open in Leela', '(an estimate)', 'none for this one', 'captions.jsonl', 'Predict: How many episodes',
                'Pick the folder of your images', 'Download the notebook', 'Leela is not running. Start Leela, then press ⌥S again.', 'Get Leela',
                '1 more test that you cannot see.', 'abhyasa does not run this code'):
        assert say in card, say
    assert 'no people and no place' not in card                                         # a hidden test shows nothing of itself
    assert lr.journey(jid).steps[1].get('qid') is None                                   # abhyasa opens no question on a notebook step
    r = cl.get(f'/w/{jid}/1/notebook')
    assert r.status_code == 200 and r.headers['content-disposition'] == f'attachment; filename="{jid}-1.ipynb"'
    setup, tests = load_tests(json.loads(r.text))
    assert 'EPISODES = Path(' in setup[0] and [t['say'] for t in tests] == ['episode 1', 'no people and no place']
    assert cl.get(f'/w/{jid}/0/notebook').status_code == 404                             # a step with no spec has no notebook

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
    card = cl.get(f'/w/{jid}/1/check').text
    assert 'Opened in Leela at ' in card and 'The result comes back here.' in card and 'Leela runs at' not in card

def test_open_in_leela_with_no_leela(mk, lr, walk_fake):
    "With no Leela, the press goes back to the step and notes no time. An unknown step is 404."
    cl = mk(); jid = nb_step(cl, lr)
    r = cl.post(f'/w/{jid}/1/leela', follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == f'/w/{jid}/1' and 'leela_at' not in lr.journey(jid).steps[1]
    assert cl.post(f'/w/{jid}/99/leela', follow_redirects=False).status_code == 404

def test_data_path_outside_home_refused(mk, lr, walk_fake):
    cl = mk(); jid = nb_step(cl, lr)
    before = lr.journey(jid).steps[1]['nb']
    for bad, why in (('/etc', 'the path is not in your home folder'), ('~/../../etc', 'the path has ..'), ('', 'give a path of one line'),
                     ('~/.ssh', 'a part of the path starts with a dot'), ('~/x\nimport os', 'give a path of one line')):
        r = cl.post(f'/w/{jid}/1/data', data=dict(name='IMAGES', path=bad))
        assert r.status_code == 400 and f'abhyasa did not keep this path: {why}.' in r.text, (bad, r.text)
    assert cl.post(f'/w/{jid}/1/data', data=dict(name='NOPE', path='~/x')).status_code == 400
    assert lr.journey(jid).steps[1]['nb'] == before and 'requires' not in before   # an empty `requires` is left out
    r = cl.post(f'/w/{jid}/1/data', data=dict(name='IMAGES', path='~/Pictures/ramayana'))
    assert r.status_code == 200 and '~/Pictures/ramayana' in r.text
    assert [d['path'] for d in lr.journey(jid).steps[1]['nb']['data']][1] == '~/Pictures/ramayana'

def test_refused_import_says_notebook(mk, lr, walk_fake):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why=''))
    cl.get(f'/w/{jid}/1/check')
    out = cl.post(f'/w/{jid}/1/run', data=dict(source='import torch\ndef softmax(x, t=1.0): return x')).text
    assert '<code>import torch</code> does not work here. This step needs a notebook: change the check to Notebook, or open it in Leela.' in out

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
    monkeypatch.setattr('abhyasa.journey.hands_most', lambda n: n)   # no cap, so the code idea keeps its notebook check
    cl = mk()
    jid = cl.post('/walk/new', data=dict(ref=add_paper(lr), tool='on')).headers['hx-redirect'].split('/')[-1]
    ix = [i for i, s in enumerate(lr.journey(jid).steps) if s['check']['kind'] == 'notebook']
    assert ix and all(lr.journey(jid).steps[i]['check']['why'].endswith('runs in Leela') for i in ix)
    assert wait_for(lambda: all(lr.journey(jid).steps[i].get('nb') for i in ix) or None, 10)

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
