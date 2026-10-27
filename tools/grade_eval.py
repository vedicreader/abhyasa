"""Opt-in check of the real grader on 8 cases. It calls a real model; CI and nbdev tests never run it.

Run: uv run python tools/grade_eval.py [--model claude/sonnet] [--runs 1]
It follows the `grade` model of the settings, like the app. It prints PASS or FAIL for each case against the expected `correct`."""
import argparse
from fastcore.utils import *
from abhyasa.llm import Router, rishi_ask, for_task, ask_json
from abhyasa.tutor import GRADE_SP, grade_prompt

NEURON = AttrDict(name='Neuron as a weighted sum', depth=3, method='words', kind='explain',
    question=("A neuron scores a chart with inputs x1 = Jupiter strength and x2 = Saturn strength. You set both inputs to 0. "
              "Why does z then equal b, whatever the weights are? Explain using the loop that sums products, in your own words."),
    answer='The loop adds w*x for each input. Each product is 0 when x is 0, so the sum is 0 and only b is left.',
    rubric=['Each product of weight and input is 0 when the input is 0', 'The sum of the products is 0, so z equals b'])
SOFTMAX = AttrDict(name='Softmax', depth=3, method='words', kind='explain',
    question='Why do the outputs of softmax always add up to 1? Explain in your own words.',
    answer='Each output is e^zi divided by the sum of all e^zj. The sum of the outputs is that sum divided by itself, so it is 1.',
    rubric=['Each output is its exponential divided by the sum of all the exponentials', 'The outputs share one denominator, so they add up to 1'])
T1 = ("And. Okay, so it's x one w one plus. Y one w two. Or x two w two, plus b equals. Said. Then, if x one and x two are zero, "
      "then all that's left is the constant b. So z=b")
T2 = ("Sorry, it's in the running some. X one square, w one square plus x two square, w two square. Plus b squared the whole of root, "
      "so it's. root of B Square, is B.")
NUDGE = 'What happens to each product and the running sum as the loop processes the two zero inputs?'

def turns(q, you, nudge):
    "The thread before the latest message: the question, one try of the learner and the nudge."
    return [dict(who='tutor', kind='question', text=q), dict(who='you', text=you), dict(who='tutor', kind='nudge', text=nudge)]

CASES = [   # (label, question, earlier turns, latest answer, confidence, expected correct)
    ('case: right equation, method words missing', NEURON, [], T1, None, True),
    ('case: vector length, not the weighted sum', NEURON, turns(NEURON.question, T1, NUDGE), T2, 70, False),
    ('noisy speech to text, right idea', SOFTMAX, [], 'Uh. So each. Output is e to the z i, over the some of all the e to the z j. So when you add them. The top and the bottom, are the same. So one.', None, True),
    ('right result, wrong reasoning', NEURON, [], 'z equals b because the weights are random, so they cancel each other out, and only b is left.', 80, False),
    ('bare "I don\'t know"', SOFTMAX, [], "I don't know.", 10, False),
    ('right answer, dot product instead of the loop', NEURON, [], 'z is w dot x plus b. x is the zero vector, so w dot x is 0 whatever w is. So z = b.', 80, True),
    ('plain right answer', SOFTMAX, [], 'Each output is exp(z_i) divided by the sum of exp(z_j) over all j. All outputs share that one sum as the denominator, so together they give 1.', 90, True),
    ('plain wrong answer', SOFTMAX, [], 'Softmax gives 1 to the biggest score and 0 to the others, so the total is 1.', 80, False)]

def run(ask, runs=1):
    "Grade each case `runs` times; the case passes when every run gives the expected `correct`. Return the number of failures."
    bad = 0
    for label, q, ts, ans, conf, want in CASES:
        q = AttrDict(q, turns=ts, tries=[])
        gs = [AttrDict(ask_json(ask, grade_prompt(q, ans, '', conf), GRADE_SP)) for _ in range(runs)]
        ok = all(bool(g.get('correct')) == want for g in gs)
        bad += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {label}: want {want}, got {[g.get('correct') for g in gs]}, grade {[g.get('grade') for g in gs]}\n      {gs[-1].get('feedback', '')}")
    print(f'{len(CASES) - bad} of {len(CASES)} cases pass')
    return bad

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--model', default=None, help='the default model; the `grade` model of the settings still wins')
    p.add_argument('--runs', type=int, default=1)
    a = p.parse_args()
    raise SystemExit(1 if run(for_task(Router(rishi_ask(a.model)), 'grade'), a.runs) else 0)
