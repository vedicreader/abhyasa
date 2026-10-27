"""Exercise feedback uses the shared check report."""
import time

import pytest
from fastcore.basics import AttrDict

from abhyasa.llm import Fake
from abhyasa.nb import Exercise
from abhyasa.store import temp_learning
from abhyasa.tutor import Tutor


@pytest.fixture
def exercise():
    learning = temp_learning()
    learning.put('Double', 'Multiply a number by two.', 'math')
    spec = dict(task='Double a number.', fname='double', stub='def double(x): ...',
                tests=['assert double(2) == 4'], solution='def double(x): return x * 2')
    return Exercise(Tutor(learning, Fake(dflt=spec)), 'double')


def test_exercise_total_timeout(exercise):
    def endless(x):
        while True: pass
    exercise.tests = ['assert double(2) == 4'] * 12
    started = time.monotonic()
    failures = exercise.run(endless)
    elapsed = time.monotonic() - started
    assert elapsed < 12, f'shared 10 second budget took {elapsed:.2f}s'
    assert len(failures) == 12 and all('TimeoutError' in error for _, error in failures)
    assert exercise.report.timeout
    assert all(c.status == 'timeout' for c in exercise.report.checks)


def test_exercise_hidden_feedback(exercise):
    secret = 'private-expected-83912'
    text = f"assert double(123) == '{secret}'"
    exercise.tests = [dict(test=text, say='Secret case', hidden=True)]
    message = exercise.check(lambda x: secret + '-wrong')
    assert text not in message and secret not in message
    assert 'Secret case' in message and 'fail' in message
    assert secret not in str(exercise.q.tries)


def test_exercise_actual_and_capture(exercise, capsys):
    def wrong(x):
        print('learner output')
        return 83913
    failures = exercise.run(wrong)
    assert len(failures) == 1 and failures[0][0] == 'assert double(2) == 4'
    assert '83913' in failures[0][1]
    assert exercise.report.checks[0].got == '83913'
    assert capsys.readouterr().out == ''
    message = exercise.check(wrong)
    assert '0 of 1 tests pass' in message and '83913' in message


def test_exercise_report_grade(exercise):
    exercise.tests = ['assert double(2) == 4', 'assert double(3) == 6']
    exercise.q.tries = [dict(confidence=70), dict(confidence=70)]
    def close(q, correct, confidence, grade, teach):
        assert not correct and teach
        assert grade.grade == 5 and 'got 4' in grade.first_error
        return AttrDict(outcome='miss', feedback=grade.first_error, lesson='', floor=0)
    exercise.t._close = close
    assert 'got 4' in exercise.check(lambda x: 4)
