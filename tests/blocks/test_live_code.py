"The code of a step: the validator, the placeholder and its fallback, the setting, and the graded check that moves the gauge."
import base64, json
from walk_data import *
from abhyasa.path import check_code, grade_code
from abhyasa.core.livecode import LiveCell
from abhyasa.learner import use_settings

GOOD = dict(src='# Make x 4, then run\nx = 3\nprint(x * 2)', watch=['x'], expect=dict(var='x', value='4'))

def with_code(cl, lr, code=GOOD):
    jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_slug(jid, lr.journey(jid).steps[0]['slug'], code=check_code(code))
    return jid

def test_the_validator_keeps_only_small_safe_python():
    assert check_code(GOOD)['expect'] == dict(var='x', value='4')
    for bad in ('import os', 'from subprocess import run', 'import numpy.linalg, socket', 'x = (', 'open("f")', 'eval("1")', '().__class__', 'x = 1\n' * 41, '', '   '):
        assert check_code(dict(src=bad)) is None, bad
    assert check_code(dict(src='import math, numpy.linalg\nx = math.pi'))['src'].startswith('import math')
    assert check_code(dict(src='x = 1', watch=['x', 'a b', '__x', 'y'] + list('abcdefgh')))['watch'] == ['x', 'y', 'a', 'b', 'c', 'd']

def test_grading_needs_no_model():
    assert grade_code(dict(var='x', value='4'), '', dict(x='4.0')) and not grade_code(dict(var='x', value='4'), '', dict(x='5'))
    assert grade_code(dict(out='16'), 'it is 16\n') and not grade_code(None, 'x')

def test_the_placeholder_and_its_fallback():
    code = check_code(GOOD)
    hosted = str(LiveCell(code, 'w-0', 'w', 0, '/w/w/0/code', hosted=True))
    assert 'class="lee-livecell"' in hosted and 'data-lang="python"' in hosted and 'data-watch="x"' in hosted and 'data-id="w-0"' in hosted and 'data-check-url="/w/w/0/code"' in hosted
    assert base64.b64decode(hosted.split('data-src-b64="')[1].split('"')[0]).decode() == code['src'] and '<pre' in hosted and 'x = 3' in hosted
    alone = str(LiveCell(code, 'w-0', 'w', 0, '/w/w/0/code', hosted=False))
    assert 'lee-livecell' not in alone and 'data-src-b64' not in alone and 'x = 3' in alone and '<pre' in alone

def test_a_step_with_code_shows_it_and_a_step_without_shows_nothing(mk, lr, walk_fake):
    cl = mk(); jid = with_code(cl, lr)
    assert 'x = 3' in cl.get(f'/w/{jid}/0').text and 'live-code' in cl.get(f'/w/{jid}/0').text
    assert 'live-code' not in cl.get(f'/w/{jid}/1').text

def test_the_setting_is_off_so_no_step_gets_code(mk, lr, walk_fake):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    cl.get(f'/w/{jid}/0/note')
    assert not lr.journey(jid).steps[0].get('code') and not lr.journey(jid).steps[0].get('code_none')

def test_the_check_files_one_attempt_for_each_id_and_moves_the_gauge(mk, lr, walk_fake):
    cl = mk(); jid = with_code(cl, lr); slug = lr.journey(jid).steps[0]['slug']
    n = len(lr.attempts(slug, limit=None))
    r = cl.post(f'/w/{jid}/0/code', data=dict(aid='a1', out='8\n', watch=json.dumps(dict(x='4')))).json()
    assert r['ok'] and r['correct'] and slug in r['gauge'] and len(lr.attempts(slug, limit=None)) == n + 1
    assert cl.post(f'/w/{jid}/0/code', data=dict(aid='a1', out='8\n', watch=json.dumps(dict(x='4')))).json()['correct'] and len(lr.attempts(slug, limit=None)) == n + 1
    r = cl.post(f'/w/{jid}/0/code', data=dict(aid='a2', out='6\n', watch=json.dumps(dict(x='3')))).json()
    assert r['ok'] and not r['correct'] and len(lr.attempts(slug, limit=None)) == n + 2
    assert cl.post(f'/w/{jid}/1/code', data=dict(aid='a3')).status_code == 404   # no code on that step

def test_the_check_refuses_a_cross_site_post(mk, lr, walk_fake):
    cl = mk(); jid = with_code(cl, lr)
    assert cl.post(f'/w/{jid}/0/code', data=dict(aid='x'), headers={'Origin': 'http://evil.example'}).status_code == 403

def test_the_ladder_shows_four_rungs_only_with_a_demo_and_code(mk, lr, walk_fake):
    from rupaka.spec import gallery
    cl = mk(); jid = with_code(cl, lr); slug = lr.journey(jid).steps[0]['slug']
    assert 'The idea in four ways' not in cl.get(f'/c/{slug}').text                      # code, but no demo
    spec = next(iter(gallery().values())) if isinstance(gallery(), dict) else gallery()[0]
    lr.put_demo(spec, slug)
    page = cl.get(f'/c/{slug}').text
    assert 'The idea in four ways' in page and 'In words' in page and 'As a picture' in page and 'As code' in page and 'x = 3' in page
    assert 'As numbers' not in page and 'live-numbers' not in page                       # standalone: nothing runs, so no numbers
    other = lr.journey(jid).steps[1]['slug']
    assert 'The idea in four ways' not in cl.get(f'/c/{other}').text
