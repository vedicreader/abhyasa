"What comes back from Leela: its attempts with the walk meta show on the walk step, and the walk end shows what you made."
from walk_data import *
from abhyasa.contract import NB_SPEC_CASES, validate_nb_spec

PNG = b'\x89PNG\r\n\x1a\n' + b'\0' * 32

def nb_step(cl, lr, i=1):
    "A started walk whose step `i` is a notebook check with the good spec of the contract."
    jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, i, check=dict(way='code', kind='notebook', depth=4, why=''), nb=validate_nb_spec(NB_SPEC_CASES[0][0]))
    return jid

def meta(jid, i, app='leela'): return dict(walk=jid, step=i, app=app, section='3.2.1 Scaled Dot-Product Attention', **{'from': f'{jid}/{i}'})

def file_check(lr, jid, i, app='leela'):
    "A passed check as Leela files it (`record_exercise`): kind `code`, depth 4, with the walk meta."
    return lr.record('softmax', 'Write caption', 'def caption(): ...', correct=True, depth=4, kind='code', grade=9, feedback='Good.',
                     notebook='/Users/x/lessons/comic-7.ipynb', card_key='c1:h', **meta(jid, i, app))

def file_run(lr, jid, i, n=2, **kw):
    "A run as Leela files it, with `n` images copied to the vault assets."
    d = lr.vault.assets()/'leela'/jid/str(i); d.mkdir(parents=True, exist_ok=True)
    for k in range(n): (d/f'{k}.png').write_bytes(PNG)
    run = dict(metrics=dict(loss=0.083, steps=1000), images=[f'leela/{jid}/{i}/{k}.png' for k in range(n)], secs=2310, device='mps',
               notebook='/Users/x/lessons/comic-7.ipynb', makes='Vālmīki asks Nārada who has every virtue.', **kw)
    return lr.record('softmax', 'Run', kind='run', **{**run, **meta(jid, i)})

def test_code_attempt_marks_the_step_done(mk, lr, walk_fake):
    cl = mk(); jid = nb_step(cl, lr)
    file_check(lr, jid, 1)
    page = cl.get(f'/w/{jid}/1').text
    d = lr.journey(jid).steps[1]['done']
    assert (d['outcome'], d['by']) == ('solid', 'leela')
    assert 'From Leela' in page and 'Right. 2 of 2 tests pass.' in page and 'lessons/comic-7.ipynb' in page and '/Users/x' not in page
    assert f'action="/w/{jid}/1/next"' in page and 'Next idea' in page and 'Open in Leela' not in page
    assert 'From Leela' in cl.get(f'/w/{jid}/1/check').text   # the check route gives the same card

def test_run_attempt_shows_metrics_and_images(mk, lr, walk_fake):
    cl = mk(); jid = nb_step(cl, lr)
    file_run(lr, jid, 1)
    lr.record('softmax', 'The loss after 500 steps', '0.15', correct=False, depth=1, kind='predict', actual='0.091', **meta(jid, 1))
    page = cl.get(f'/w/{jid}/1').text
    for say in ('1,000 steps in 38 min 30 s on Apple GPU (mps). Last loss 0.083.', 'You said 0.15. It was 0.091.', 'Images are copies in your vault.',
                f'src="/w/{jid}/1/result/0.png"', f'src="/w/{jid}/1/result/1.png"'):
        assert say in page, say
    assert not lr.journey(jid).steps[1].get('done') and 'Open in Leela' in page   # a run with no passed check does not end the step
    r = cl.get(f'/w/{jid}/1/result/0.png')
    assert r.status_code == 200 and r.headers['content-type'] == 'image/png' and r.content == PNG and r.headers['x-content-type-options'] == 'nosniff'

def test_unsafe_results_are_refused(mk, lr, walk_fake, tmp_path):
    cl = mk(); jid = nb_step(cl, lr)
    file_run(lr, jid, 1)
    (lr.vault.assets()/'x.png').write_bytes(PNG)
    for bad in (f'/w/{jid}/0/result/..%2F..%2Fx.png', f'/w/{jid}/1/result/9.png', f'/w/{jid}/1/result/00.png', f'/w/{jid}/1/result/a.png',
                f'/w/{jid}/99/result/0.png', '/w/nope/1/result/0.png'):
        assert cl.get(bad).status_code == 404, bad
    d = lr.vault.assets()/'leela'/jid/'1'
    (d/'2.png').write_bytes(b'<svg onload=alert(1)>')                      # not a PNG
    (d/'3.png').write_bytes(PNG + b'\0' * (2 << 20))                       # too big
    (d/'4.png').symlink_to(tmp_path/'out.png'); (tmp_path/'out.png').write_bytes(PNG)   # a link out of the assets
    for n in (2, 3, 4): assert cl.get(f'/w/{jid}/1/result/{n}.png').status_code == 404, n

def test_untrusted_attempts_change_nothing(mk, lr, walk_fake):
    "An attempt from another app changes nothing; a run that `run_ok` refuses shows no card; a text from Leela is escaped."
    cl = mk(); jid = nb_step(cl, lr)
    file_check(lr, jid, 1, app='other')
    lr.record('softmax', 'Run', kind='run', metrics={f'm{k}': k for k in range(13)}, **meta(jid, 1))
    page = cl.get(f'/w/{jid}/1').text
    assert not lr.journey(jid).steps[1].get('done') and 'From Leela' not in page
    lr.record('softmax', 'Guess', '<script>alert(1)</script>', kind='predict', actual='<b>x</b>', **meta(jid, 1))
    page = cl.get(f'/w/{jid}/1').text
    assert 'From Leela' in page and '<script>alert(1)' not in page and '&lt;script&gt;' in page and '<b>x</b>' not in page

def test_walk_end_shows_what_you_made(mk, lr, walk_fake):
    cl = mk(); jid = nb_step(cl, lr)
    file_check(lr, jid, 1); file_run(lr, jid, 1, n=3)
    cl.post(f'/w/{jid}/0/next')
    r = cl.get(f'/w/{jid}', follow_redirects=False)
    assert r.headers.get('location', r.headers.get('hx-redirect')) == f'/w/{jid}/2'   # Leela's check moved the walk on, past idea 2
    cl.post(f'/w/{jid}/2/next')
    page = cl.get(f'/w/{jid}/2/done').text
    assert 'What you made' in page and f'src="/w/{jid}/1/result/2.png"' in page and 'Idea 2' in page
    assert 'Leela never changes the walk.' in page and 'abhyasa wrote this from Leela' in page
    assert 'Vālmīki asks Nārada' in page and 'Attention Is All You Need' in page   # the caption, and the source line of the passage
