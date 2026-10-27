"""Checks for the light learner-code runner."""
import json
import subprocess
import sys
import threading
import time

import pytest

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
        with time_limit(.02):
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline: pass
    with time_limit(.02): pass
    time.sleep(.04)


def test_worker_timer_cancelled():
    result = []
    def work():
        with time_limit(.02): pass
        time.sleep(.05)
        result.append('finished')
    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(1)
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
