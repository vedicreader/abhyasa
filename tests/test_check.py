"""Checks for the light learner-code runner."""
import builtins
import json
import os
import subprocess
import sys
import threading
import time

import pytest

import abhyasa.check as check
from fastcore.nbio import mk_cell, new_nb, write_nb
from abhyasa.check import SAFE_BUILTINS, Report, public, run_asserts, safe_test, time_limit, validate_exercise


def test_light_import():
    code = """
import sys
import abhyasa.check
heavy = ('abhyasa.store', 'abhyasa.tutor', 'abhyasa.llm', 'rishi', 'vishalakshi', 'fasthtml')
assert not any(name == p or name.startswith(p + '.') for name in sys.modules for p in heavy)
"""
    subprocess.run([sys.executable, '-I', '-c', code], check=True, capture_output=True, text=True, timeout=10)


def test_nb_reexports():
    import abhyasa.check
    import abhyasa.nb
    assert abhyasa.nb.safe_test is abhyasa.check.safe_test


def test_safe_tests_and_dict_validation():
    assert safe_test('assert f(2) == 4', 'f')
    assert not safe_test("assert __import__('os')", 'f')
    tests = ['assert f(2) == 4', dict(test='assert f(3) == 6', say='three', hidden=True)]
    exercise = dict(task='Double a number.', fname='f', stub='def f(x): ...', tests=tests)
    assert validate_exercise(exercise).tests == tests
    with pytest.raises(ValueError, match='plain assert'):
        validate_exercise(dict(exercise, tests=[dict(test='import os', say='', hidden=True)]))
    for bad in ({}, {'test': 3}, {'test': 'assert f(1)', 'say': 3}, {'test': 'assert f(1)', 'hidden': 'yes'}):
        with pytest.raises(ValueError): validate_exercise(dict(exercise, tests=[bad]))


def test_report_and_statuses():
    report = run_asserts(lambda x: 2 * x, 'f', ['assert f(2) == 4', dict(test='assert f(3) == 7', say='Three')])
    assert isinstance(report, Report)
    assert report.found and not report.timeout and not report.passed
    assert [c.status for c in report.checks] == ['pass', 'fail']
    assert [c.got for c in report.checks] == ['4', '6']
    assert report.checks[1].label == 'Three'
    assert report.checks[1].error.startswith('AssertionError:')
    assert all(c.ms >= 0 for c in report.checks)
    assert run_asserts(lambda: 1, 'f', ['assert f() == 1']).passed
    missing = run_asserts(None, 'f', ['assert f() == 1'])
    assert not missing.found and not missing.passed


def test_error_and_hidden_public():
    def broken(): raise ValueError('private-expected-83912')
    shown = run_asserts(broken, 'f', ['assert f() == 0'])
    assert shown.checks[0].status == 'error'
    assert shown.checks[0].error == 'ValueError: private-expected-83912'
    text = "assert f() == 'private-expected-83912'"
    hidden = run_asserts(lambda: 'actual', 'f', [dict(test=text, say='Secret case', hidden=True)])
    assert hidden.checks[0].status == 'fail'
    assert hidden.checks[0].error == 'AssertionError'
    page = public(hidden)
    payload = json.dumps(page)
    assert text not in payload and 'private-expected-83912' not in payload
    assert set(page) == {'v', 'found', 'timeout', 'checks'} and page['v'] == 1
    assert set(page['checks'][0]) == {'i', 'label', 'status', 'got', 'error', 'hidden', 'ms'}
    private_error = run_asserts(broken, 'f', [dict(test='assert f() == 0', hidden=True)])
    assert private_error.checks[0].error == 'ValueError'
    assert 'private-expected-83912' not in json.dumps(public(private_error))


def test_output_is_captured(capsys):
    def noisy():
        print('do not publish')
        print('do not publish', file=sys.stderr)
        return 1
    report = run_asserts(noisy, 'f', ['assert f() == 1'])
    assert report.passed
    out = capsys.readouterr()
    assert out.out == out.err == ''
    assert 'do not publish' not in json.dumps(public(report))


def test_single_call_and_clipping():
    calls = []
    def once():
        calls.append(1)
        return 'x' * 400
    report = run_asserts(once, 'f', ["assert f() == 'other'"])
    assert calls == [1]
    assert len(report.checks[0].got) <= 200
    def broken(): raise ValueError('x' * 400)
    assert len(run_asserts(broken, 'f', ['assert f() == 1']).checks[0].error) <= 200


def test_total_budget():
    calls = []
    def slow():
        calls.append(1)
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline: time.sleep(.005)
        return 1
    started = time.monotonic()
    report = run_asserts(slow, 'f', ['assert f() == 1'] * 12, secs=.08, total=.22)
    elapsed = time.monotonic() - started
    assert .15 <= elapsed < .8
    assert report.timeout and not report.passed
    assert all(c.status == 'timeout' for c in report.checks)
    assert len(calls) <= 3


def test_worker_timeout():
    result = []
    def bounded_loop():
        deadline, iterations = time.monotonic() + 1., 0
        while time.monotonic() < deadline:
            iterations += 1
    def work():
        started = time.monotonic()
        try:
            with time_limit(.2): bounded_loop()
        except TimeoutError: result.append(time.monotonic() - started)
    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(1.5)
    assert not worker.is_alive()
    assert len(result) == 1 and .1 <= result[0] < .8


def test_main_timeout_and_cleanup():
    with pytest.raises(TimeoutError):
        with time_limit(.02): time.sleep(1)   # not a busy `while` loop: on Python 3.13, the alarm error can skip the `with` there
    with time_limit(.5): pass   # room for a slow machine; the sleep shows that the timer is gone
    time.sleep(.6)


def test_worker_timer_cancelled():
    result = []
    def work():
        with time_limit(.5): pass
        time.sleep(.6)
        result.append('finished')
    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(2)
    assert not worker.is_alive() and result == ['finished']


def test_keyboard_interrupt_stops_run():
    calls = []
    def interrupted():
        calls.append(1)
        raise KeyboardInterrupt
    report = run_asserts(interrupted, 'f', ['assert f() == 1'] * 3)
    assert calls == [1]
    assert report.timeout and not report.passed
    assert [c.status for c in report.checks] == ['timeout'] * 3


def test_load_tests(tmp_path):
    nb = new_nb([
        mk_cell('#| setup\nfixture = 3'),
        mk_cell('#| test: Triples\nassert f(fixture) == 6', metadata={'abhyasa': {'test': True, 'say': 'ignored'}}),
        mk_cell("assert f(4) == 8", metadata={'abhyasa': {'test': True, 'say': 'Secret', 'hidden': True}}),
        mk_cell('#| test\n#| hidden\nassert f(5) == 10'),
        mk_cell('#| test: Not code', cell_type='markdown'),
        mk_cell('ordinary = 1'),
    ])
    setup, tests = check.load_tests(nb)
    assert setup == ['#| setup\nfixture = 3']
    assert [t['say'] for t in tests] == ['Triples', 'Secret', 'Test 3']
    assert [t['hidden'] for t in tests] == [False, True, True]
    assert all(set(t) == {'source', 'say', 'hidden'} for t in tests)
    path = tmp_path / 'checks.ipynb'
    write_nb(nb, path)
    assert check.load_tests(path) == (setup, tests)


def test_run_cells_isolation_and_capture(capsys):
    tests = [
        dict(source='local = fixture + 1\nprint(local)\nassert f(local) == 8', say='Fixture'),
        dict(source="assert 'local' not in globals()\nassert fixture == 3", say='Fresh names'),
        dict(source='assert f(3) == 7', say='Wrong result'),
        dict(source="assert f(4) == 918273, 'secret-918273'", say='Private', hidden=True),
        dict(source="raise ValueError('secret-918273')", hidden=True),
    ]
    ns = {'f': lambda n: n * 2, '__builtins__': {}}
    report = check.run_cells(tests, ns, setup=['fixture = 3\nprint("setup output")'])
    assert report.found and not report.timeout
    assert [c.status for c in report.checks] == ['pass', 'pass', 'fail', 'fail', 'error']
    assert report.checks[2].got == '6'
    assert report.checks[3].error == 'AssertionError'
    assert report.checks[4].error == 'ValueError'
    assert '918273' not in json.dumps(public(report))
    assert set(ns) == {'f', '__builtins__'}
    assert capsys.readouterr().out == ''


def test_run_cells_capture_failing_statement_once():
    calls = []
    def once(n):
        calls.append(n)
        return n * 2
    tests = [dict(source='assert f(1) == 2\nassert f(3) == 7\nassert f(5) == 10')]
    report = check.run_cells(tests, {'f': once})
    assert report.checks[0].got == '6'
    assert calls == [1, 3]
    report = check.run_cells([dict(source='assert f(1) == 2\nassert False')], {'f': once})
    assert report.checks[0].got is None
    def fails(n):
        if n == 3: raise AssertionError('inside the function')
        return n * 2
    report = check.run_cells([dict(source='assert f(1) == 2\nassert f(3) == 7')], {'f': fails})
    assert report.checks[0].status == 'fail' and report.checks[0].got is None
    for source, got in ((r'assert f(3) == 7; assert f(5) == 10', '6'),
                        (r'assert f(1) == 2; assert f(3) == 7', '6'),
                        (r'assert f(1) == 2; assert False', None),
                        ('assert f(\n3) == 7; assert f(5) == 10', '6')):
        report = check.run_cells([dict(source=source)], {'f': once})
        assert report.checks[0].got == got


def test_run_cells_setup_failure():
    tests = [dict(source='assert True'), dict(source='assert True', hidden=True)]
    report = check.run_cells(tests, {}, setup=["raise ValueError('private-918273')"])
    assert [c.status for c in report.checks] == ['error', 'error']
    assert report.checks[0].error == 'SetupError: ValueError'
    assert report.checks[1].error == 'SetupError'
    assert '918273' not in json.dumps(public(report))
    for setup in ((), [r'raise SystemExit("private-918273")']):
        report = check.run_cells([dict(source=r'raise SystemExit("private-918273")', hidden=True)], {}, setup=setup)
        assert report.checks[0].status == 'error'
        assert report.checks[0].error == ('SetupError' if setup else 'SystemExit')
        assert '918273' not in json.dumps(public(report))


def test_run_cells_budget_and_interrupt():
    tests = [dict(source='while True: pass')] * 10
    started = time.monotonic()
    report = check.run_cells(tests, {}, secs=.06, total=.16)
    assert .1 <= time.monotonic() - started < .8
    assert report.timeout and all(c.status == 'timeout' for c in report.checks)
    report = check.run_cells([dict(source='raise KeyboardInterrupt'), dict(source='assert True')], {})
    assert report.timeout and [c.status for c in report.checks] == ['timeout', 'timeout']
    started = time.monotonic()
    report = check.run_cells([dict(source='assert True')], {}, setup=['while True: pass'], total=.06)
    assert time.monotonic() - started < .8
    assert report.timeout


@pytest.mark.parametrize('kind', ['assert', 'cell'])
def test_snippet_matches_runner_and_preserves_names(kind, capsys):
    def noisy(n):
        print('learner output')
        print('learner stderr', file=sys.stderr)
        return n * 2
    asserts = ['assert f(2) == 4', dict(test='assert f(3) == 7', say='Wrong'),
               dict(test='assert f(4) == 918273', say='Private', hidden=True)]
    tests = asserts if kind == 'assert' else [dict(source=t if isinstance(t, str) else t['test'],
                                                     say='' if isinstance(t, str) else t['say'],
                                                     hidden=False if isinstance(t, str) else t.get('hidden', False)) for t in asserts]
    ns = {'f': noisy, '_abhyasa_check': 'keep', '__name__': 'kernel', '__builtins__': builtins.__dict__}
    before = ns.copy()
    expected = public(run_asserts(noisy, 'f', tests) if kind == 'assert' else check.run_cells(tests, ns))
    source = check.snippet(kind, 'f', tests)
    exec(source, ns)
    assert ns == before
    captured = capsys.readouterr()
    assert captured.err == '' and len(captured.out.splitlines()) == 1
    actual = check.parse(captured.out)
    for result in (expected, actual):
        for c in result['checks']: c.pop('ms')
    assert actual == expected


def test_parse():
    for text in ('', 'not JSON', '[]', 'null', '{"other": 1}'):
        assert check.parse(text) == {'error': 'no check result'}
    result = {'v': 1, 'found': True, 'timeout': False, 'checks': []}
    assert check.parse('noise\n' + json.dumps(result) + '\nmore noise\n') == result
    assert check.parse(json.dumps(result) + '\n' + json.dumps(dict(result, found=False)))['found'] is False


def test_run_isolated():
    tests = ['assert f(3) == 6']
    result = check.run_isolated('assert', 'f', 'def f(n):\n print("noise")\n return n * 2', tests)
    assert result['found'] and result['checks'][0]['status'] == 'pass'
    result = check.run_isolated('assert', 'f', 'def f(n): return n', tests)
    assert result['checks'][0]['status'] == 'fail' and result['checks'][0]['got'] == '3'
    tests = [dict(source='assert f(fixture) == 6', say='Fixture')]
    result = check.run_isolated('cell', 'f', 'def f(n): return n * 2', tests, setup=['fixture = 3'])
    assert result['checks'][0]['status'] == 'pass'
    started = time.monotonic()
    assert check.run_isolated('assert', 'f', 'while True: pass', [], total=.1) == {'timeout': True}
    assert time.monotonic() - started < 3.1


def test_hostile_code_does_not_pass_or_hang():
    tests = ['assert f(2) == 4']
    t = time.monotonic()
    assert check.run_isolated('assert', 'f', 'while True: pass\ndef f(n): return n * 2', tests, total=1.) == {'timeout': True}
    assert time.monotonic() - t < 4
    fake = 'import json, os\nprint(json.dumps({"v": 1, "found": True, "timeout": False, "checks": [{"status": "pass"}]}))\nos._exit(0)'
    assert check.run_isolated('assert', 'f', fake, tests).get('checks') in (None, [])
    net = 'import socket\ndef f(n):\n    socket.create_connection(("example.org", 80), 1)\n    return n * 2'
    r = check.run_isolated('assert', 'f', net, tests)
    assert r['checks'][0]['status'] == 'error'
    w = check.run_isolated('assert', 'f', 'open("/tmp/abhyasa-should-not-exist", "w")\ndef f(n): return n * 2', tests)
    assert not os.path.exists('/tmp/abhyasa-should-not-exist')
    assert (w.get('checks') or [{}])[0].get('status') != 'pass'


def test_future_import_stays_first():
    r = check.run_isolated('assert', 'f', 'from __future__ import annotations\ndef f(n: int) -> int: return n * 2', ['assert f(2) == 4'])
    assert r['checks'][0]['status'] == 'pass'


def test_code_on_the_line_of_a_future_import_is_refused():
    "Code after a `;` on the future line must not run before the guard. The runner refuses it."
    for head in ('from __future__ import annotations', '"doc"'):
        src = f'{head}; import socket; S = socket.socket()\ndef f(n): return "made-socket-before-guard"'
        r = check.run_isolated('assert', 'f', src, ['assert f(2) == 4'])
        assert 'checks' not in r and 'own line' in r['error'], r
    head, body = check._split_future('"doc"\nfrom __future__ import (\n    annotations)\nfrom __future__ import division\nx = 1\n')
    assert (head, body) == ('"doc"\nfrom __future__ import (\n    annotations)\nfrom __future__ import division', 'x = 1\n')


def test_a_signal_that_is_not_a_limit_is_no_result():
    stop = 'import os, signal\nos.kill(os.getpid(), signal.SIGTERM)\ndef f(n): return n * 2'
    assert check.run_isolated('assert', 'f', stop, ['assert f(2) == 4']) == {'error': 'no check result'}


@pytest.mark.skipif(not hasattr(os, 'killpg'), reason='process groups are POSIX only')
def test_a_child_process_that_keeps_the_output_open_does_not_hang(tmp_path):
    "The audit hook refuses new processes, so this runs without it. The time limit stops the whole process group."
    pidfile = tmp_path/'pid'
    src = f'import subprocess\np = subprocess.Popen(["sleep", "30"])\nopen({str(pidfile)!r}, "w").write(str(p.pid))\ndef f(n): return n * 2'
    t = time.monotonic()
    assert check.run_isolated('assert', 'f', src, ['assert f(2) == 4'], total=1., sandbox=False) == {'timeout': True}
    assert time.monotonic() - t < 5
    pid, end = int(pidfile.read_text()), time.monotonic() + 3
    while time.monotonic() < end:
        try: os.kill(pid, 0)
        except ProcessLookupError: break
        time.sleep(.05)
    else: pytest.fail(f'the child process {pid} still runs')


def test_public_hides_a_passing_hidden_tests_expected_value():
    def double(n): return n * 2
    page = json.dumps(public(run_asserts(double, 'double', [dict(test='assert double(-123) == -246', say='Negative', hidden=True)])))
    assert '-246' not in page and '-123' not in page


def test_system_exit_in_the_learners_function_is_an_error_not_an_escape():
    def quits(n): raise SystemExit(3)
    report = run_asserts(quits, 'quits', ['assert quits(1) == 1', dict(test='assert quits(2) == 2', hidden=True)])
    assert [c.status for c in report.checks] == ['error', 'error']
    assert report.checks[1].error == 'SystemExit'


@pytest.fixture
def target():
    "A spare process that hostile code tries to stop. It is not the test process, so a red test cannot stop pytest."
    t = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
    yield t
    t.kill(); t.wait()


@pytest.mark.parametrize('exe', ['real', 'missing'])
def test_hostile_code_cannot_signal_other_processes(target, exe, monkeypatch):
    "The audit hook refuses os.kill, os.killpg and signal.pthread_kill. With a missing sandbox-exec, the hook alone must do it."
    if exe == 'missing': monkeypatch.setattr(check, 'SANDBOX_EXEC', '/missing/sandbox-exec')
    for call in (f'os.kill({target.pid}, 9)', f'os.killpg({target.pid}, 9)', 'os.kill(os.getppid(), 0)',
                 'signal.pthread_kill(threading.main_thread().ident, 0)'):
        src = f'import os, signal, threading\ndef f(n):\n    {call}\n    return n * 2'
        r = check.run_isolated('assert', 'f', src, ['assert f(2) == 4'])
        assert r['checks'][0]['status'] == 'error' and 'PermissionError' in r['checks'][0]['error'], (call, r)
    time.sleep(.2)
    assert target.poll() is None


@pytest.mark.skipif(not os.path.exists(check.SANDBOX_EXEC), reason='macOS sandbox-exec only')
def test_the_profile_alone_refuses_a_signal_to_another_process(target):
    code = f'import os, signal\nsignal.signal(15, lambda *a: print("self"))\nos.kill(os.getpid(), 15)\nos.kill({target.pid}, 9)'
    p = subprocess.run([check.SANDBOX_EXEC, '-p', check.SANDBOX_PROFILE, '-D', 'TMP=/nonexistent', sys.executable, '-I', '-B', '-c', code],
                       capture_output=True, text=True, timeout=20)
    time.sleep(.2)
    assert 'self' in p.stdout and 'PermissionError' in p.stderr and target.poll() is None
