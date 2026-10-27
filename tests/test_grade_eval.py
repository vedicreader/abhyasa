"The checks that tools/grade_eval.py scores without a model judge: a short nudge and a question that asks one thing."
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location('grade_eval', Path(__file__).parents[1]/'tools'/'grade_eval.py')
ge = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(ge)

def oks(cs): return [ok for _, ok in cs]

def test_feedback_one_question_short_code():
    "A nudge with one question and 4 lines of code passes; two questions or a 5-line block fails."
    assert all(oks(ge.feedback_checks('You have the sum. What does the return line add?')))
    assert all(oks(ge.feedback_checks('Close.\n```python\na = 1\nb = 2\nc = a + b\nprint(c)\n```\nWhat is c?')))
    assert not all(oks(ge.feedback_checks('What is s? What is b?')))
    assert not all(oks(ge.feedback_checks('Look.\n```python\na = 1\nb = 2\nc = 3\nd = 4\ne = 5\n```\nWhat is e?')))

def test_question_checks():
    "A question with one ask passes each check. A second instruction, a long text or code in `question` fails one check."
    assert all(oks(ge.question_checks(dict(question='What does s hold just before the return line?', code='s = 0\nreturn s'))))
    assert not all(oks(ge.question_checks(dict(question='State what f computes. Then say what s holds before return.', code=''))))
    assert not all(oks(ge.question_checks(dict(question='Why? Also, how?', code=''))))
    assert not all(oks(ge.question_checks(dict(question=' '.join(['word'] * 60) + '?', code=''))))
    assert not all(oks(ge.question_checks(dict(question='What does this give?\n```python\nf(2)\n```', code=''))))
    assert all(oks(ge.question_checks(dict(question='If x is 0, then what is z?', code=''))))

def test_one_ask():
    "A second question word joined by 'and', 'or' or a comma fails the one-ask check; one ask passes."
    ask = lambda q: dict(ge.question_checks(dict(question=q, code='')))['one ask']
    for q in ("After the loop, what does `out` hold, and why does it have fewer values than `sales`?",
              "What does it return for 2100 and for 2400, and why do the results differ?",
              "On which days does the spike of 40 raise the average, and why does it affect that many days?"): assert not ask(q), q
    for q in ('Why does it print 7, not 8?', 'What does s hold just before the return line?',
              'You add one very large value to a list. Why does the median move less than the mean?'): assert ask(q), q

def test_session_cases():
    "The real session gives three cases: turn 1 alone, turns 1 and 2, and turns 1 to 3; only the last is correct."
    got = [(want, len(ts)) for label, q, ts, ans, conf, want in ge.CASES if q is ge.NEURON_CODE]
    assert got == [(False, 1), (False, 3), (True, 5)]
