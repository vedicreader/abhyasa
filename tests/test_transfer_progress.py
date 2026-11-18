import pytest
from abhyasa.learner import temp_learning, Learning
import abhyasa.show as show

RULE = 'To reach transfer: answer two new cases on your own, or one new case in your own words or numbers.'
FIRST = 'Counted as apply. One more new case, on your own, to reach transfer.'
NONE = 'Saved. It does not count toward transfer.'


def shelf():
    lr = temp_learning()
    lr.put('Angles', 'Complementary launch angles have the same range.', 'physics', slug='angles')
    return lr


def answer(lr, case='angle:20', **kw):
    return lr.record_transfer('angles', 'Which angle?', '70', '70', kw.pop('correct', True), case_id=case, multiple_choice=kw.pop('multiple_choice', True), **kw)


def progress(lr):
    return show.transfer_progress(lr.attempts('angles', limit=None))


def test_distinct_cases_and_reload():
    lr = shelf()
    answer(lr)
    assert lr.concept('angles').floor == 4
    assert progress(lr).message == FIRST
    answer(lr)
    assert lr.concept('angles').floor == 4
    assert progress(lr).message == FIRST
    lr = Learning(lr.v)
    answer(lr, 'angle:30')
    assert lr.concept('angles').floor == 5
    assert progress(lr).message == 'Transfer reached.'
    assert progress(lr).depth == 5


def test_free_answer():
    lr = shelf()
    answer(lr, multiple_choice=False)
    assert lr.concept('angles').floor == 5
    assert progress(lr).message == 'Transfer reached.'


@pytest.mark.parametrize('kw', [dict(aided=True), dict(correct=False)])
def test_no_credit_but_saved(kw):
    lr = shelf()
    answer(lr, **kw)
    assert lr.concept('angles').floor == 0
    assert len(lr.attempts('angles', limit=None)) == 1
    assert progress(lr).depth == 0
    assert progress(lr).message == NONE
    assert progress(lr).needed == RULE


def test_pure_progress_and_removed_evidence():
    assert show.transfer_progress([]).rule == RULE
    assert show.transfer_progress([]).needed == RULE
    lr = shelf()
    answer(lr)
    first = list(lr.attempts('angles', limit=None))
    answer(lr, 'angle:30')
    assert progress(lr).needed == ''
    assert show.transfer_progress(first).depth == 4
    assert show.transfer_progress(first).needed == 'One more new case, on your own, to reach transfer.'


def test_missing_case_uses_question_not_attempt_id():
    lr = shelf()
    for evidence_id in ['a', 'b']:
        lr.record_transfer('angles', 'Angle 20?', '70', '70', True, multiple_choice=True, evidence_id=evidence_id)
    assert lr.concept('angles').floor == 4
    assert progress(lr).depth == 4
