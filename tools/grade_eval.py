"""Opt-in check of the real grader on 11 cases, and of the question writer. It calls a real model; CI and nbdev tests never run it.

Run: uv run python tools/grade_eval.py [--model claude/sonnet] [--runs 1] [--questions 0]
It follows the `grade` and `question` models of the settings, like the app. It prints PASS or FAIL for each case against the
expected `correct`, and for each wrong case it checks that the nudge is short. `--questions N` writes N questions and checks each one."""
import argparse, re
from itertools import cycle, islice
from fastcore.utils import *
from abhyasa.llm import Router, rishi_ask, for_task, ask_json
from abhyasa.tutor import GRADE_SP, TUTOR_SP, grade_prompt, question_prompt, with_code

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

def turns(q, *pairs):
    "The thread before the latest message: the question, then each try of the learner with its nudge."
    return [dict(who='tutor', kind='question', text=q), *(t for you, nudge in pairs for t in (dict(who='you', text=you), dict(who='tutor', kind='nudge', text=nudge)))]

# a real session: the question asked two things, and each nudge pasted a long program
NEURON_CODE = AttrDict(name='Neuron as a weighted sum', depth=2, method='code', kind='recall',
    question=with_code('Read this code. In your own words, state what this function computes. Then say what the variable s holds just before the return line.',
                       'def neuron(w, x, b):\n    s = 0\n    for i in range(len(w)):\n        s += w[i] * x[i]\n    return s + b'),
    answer='It returns the weighted sum of the inputs plus the bias b. Just before the return line, s holds the sum of w[i] * x[i] over all inputs, without b.',
    rubric=['The function returns the sum of each weight times its input, plus b', 'Just before the return line, s holds the sum of the products, without b'])
S1 = 'This is the product function, right? Like that we were just talking about. It calculates z.'
S2 = 'All as if the sum of products of the. Changing variable and the weight.'
S3 = 'it adds the bias to the sum of input weight products'
N1 = ('Not yet. Trace it with numbers:\n```python\nw = [2, 3]\nx = [1, 4]\nb = 5\ns = 0\ns += w[0] * x[0]   # s is 2\n'
      's += w[1] * x[1]   # s is 14\nprint(s)\nprint(s + b)\n```\nWhat does s hold after the loop?')
N2 = ('Yes, s is the sum of the products.\n```python\nw = [2, 3]\nx = [1, 4]\nb = 5\nz = neuron(w, x, b)\nprint(z)\n```\n'
      'How does the function use b to change this sum into z?')

CASES = [   # (label, question, earlier turns, latest answer, confidence, expected correct)
    ('case: right equation, method words missing', NEURON, [], T1, None, True),
    ('case: vector length, not the weighted sum', NEURON, turns(NEURON.question, (T1, NUDGE)), T2, 70, False),
    ('noisy speech to text, right idea', SOFTMAX, [], 'Uh. So each. Output is e to the z i, over the some of all the e to the z j. So when you add them. The top and the bottom, are the same. So one.', None, True),
    ('right result, wrong reasoning', NEURON, [], 'z equals b because the weights are random, so they cancel each other out, and only b is left.', 80, False),
    ('bare "I don\'t know"', SOFTMAX, [], "I don't know.", 10, False),
    ('right answer, dot product instead of the loop', NEURON, [], 'z is w dot x plus b. x is the zero vector, so w dot x is 0 whatever w is. So z = b.', 80, True),
    ('plain right answer', SOFTMAX, [], 'Each output is exp(z_i) divided by the sum of exp(z_j) over all j. All outputs share that one sum as the denominator, so together they give 1.', 90, True),
    ('plain wrong answer', SOFTMAX, [], 'Softmax gives 1 to the biggest score and 0 to the others, so the total is 1.', 80, False),
    ('session: "the product function", nothing on s or b', NEURON_CODE, turns(NEURON_CODE.question), S1, None, False),
    ('session: sum of products, but + b is missing', NEURON_CODE, turns(NEURON_CODE.question, (S1, N1)), S2, None, False),
    ('session: the bias added to the sum of products', NEURON_CODE, turns(NEURON_CODE.question, (S1, N1), (S2, N2)), S3, None, True)]

def feedback_checks(fb:str) -> list:
    "`(label, ok)` for a nudge after a wrong try: at most one question mark, and each code block at most 4 lines."
    blocks = re.findall(r'```[^\n]*\n(.*?)```', fb or '', re.S)
    return [('at most one ?', (fb or '').count('?') <= 1),
            ('code at most 4 lines', all(len(b.strip('\n').splitlines()) <= 4 for b in blocks))]

def one_ask(q:str) -> bool:
    "No second ask in the sentence that ends in '?'. 'Which' and 'who' after a comma can only describe a noun, so they need 'and' or 'or'."
    ask = re.split(r'(?<=[.!:;])\s+', q.strip())[-1]
    return not re.search(r'(?:\b(?:and|or)|,)\s+(?:why|what|how|when|where)\b|\b(?:and|or)\s+(?:which|who)\b', ask, re.I)

def question_checks(r) -> list:
    "`(label, ok)` for a written question: one ?, no second instruction, under 60 words, one ask, code only in `code`."
    q = (r.get('question') or '').strip()
    return [('one ?', q.count('?') == 1),
            ('no "Then"/"Also" part', not re.search(r'(?:^|[.!?:;]\s+)(?:Then|Also)\b', q)),
            ('under 60 words', len(q.split()) < 60),
            ('one ask', one_ask(q)),
            ('code only in `code`', '```' not in q and '\n' not in q and not re.search(r'\bdef \w+\(', q))]

def _verdict(cs): return ', '.join(f"{'PASS' if ok else 'FAIL'} {label}" for label, ok in cs)

def run(ask, runs=1):
    "Grade each case `runs` times; the case passes when every run gives the expected `correct`, and a wrong case gets a short nudge. Return the number of failures."
    bad = nb = 0
    for label, q, ts, ans, conf, want in CASES:
        q = AttrDict(q, turns=ts, tries=[])
        gs = [AttrDict(ask_json(ask, grade_prompt(q, ans, '', conf), GRADE_SP)) for _ in range(runs)]
        ok = all(bool(g.get('correct')) == want for g in gs)
        bad += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {label}: want {want}, got {[g.get('correct') for g in gs]}, grade {[g.get('grade') for g in gs]}\n      {gs[-1].get('feedback', '')}")
        if not want:
            cs = [c for g in gs for c in feedback_checks(g.get('feedback', ''))]
            fok = all(ok for _, ok in cs)
            nb += not fok
            print(f"      {'PASS' if fok else 'FAIL'}  short nudge: {_verdict(cs)}")
    nw = sum(not want for *_, want in CASES)
    print(f'{len(CASES) - bad} of {len(CASES)} cases pass; {nw - nb} of {nw} nudges are short')
    return bad + nb

CONCEPTS = [dict(name='Moving average', slug='moving-average', subject='data', ceiling=6,
                 statement='The mean of the last k values. It moves one step with each new value.'),
            dict(name='Leap year rule', slug='leap-year-rule', subject='calendars', ceiling=6,
                 statement='A year is a leap year when it divides by 4, except a year that divides by 100 but not by 400.')]

def run_questions(ask, n:int) -> int:
    "Write `n` questions through the real `question_prompt`, on 2 made-up concepts at depths 1-4 in the code and words ways; check each. Return the number of failures."
    bad = 0
    for c, d, m in islice(cycle([(c, d, m) for d in (1, 2, 3, 4) for m in ('code', 'words') for c in CONCEPTS]), n):
        r = AttrDict(ask_json(ask, question_prompt(c, d, method=m), TUTOR_SP))
        cs = question_checks(r)
        ok = all(ok for _, ok in cs)
        bad += not ok
        print(f"{'PASS' if ok else 'FAIL'}  question: {c['name']}, depth {d}, {m}: {_verdict(cs)}\n      {r.get('question', '')!r}")
    if n: print(f'{n - bad} of {n} questions pass')
    return bad

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--model', default=None, help='the default model; the `grade` model of the settings still wins')
    p.add_argument('--runs', type=int, default=1)
    p.add_argument('--questions', type=int, default=0, help='also write this many questions and check each one')
    a = p.parse_args()
    ask = Router(rishi_ask(a.model))
    bad = run(for_task(ask, 'grade'), a.runs) + run_questions(for_task(ask, 'question'), a.questions)
    raise SystemExit(1 if bad else 0)
