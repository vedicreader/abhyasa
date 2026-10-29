"""Opt-in trial of the guided walk on real material: a paper, a topic, and two docs sites. It uses the real model and the network; CI never runs it in full.

Run: uv run --all-extras python tools/walk_trial.py [--only NAME] [--model claude/sonnet] [--out design/screens/trial] [--no-shots]
For each subject it makes a walk, writes the notes and questions of its steps and checks them, grades two answers, runs a code task (the paper only),
checks the Leela links (the two docs walks), and takes screens. It writes `report.md` and the screens in `--out` and prints the table.
It uses a new temporary vault and never starts or calls Leela. `--dry` uses a fake model and fake pages, with no network and no browser."""
import argparse, errno, os, re, socket, sys, tempfile, threading, time
from contextlib import contextmanager
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).parents[1]
if '--dry' in sys.argv: os.environ['LITESEARCH_USEARCH'] = '0'   # numpy search: in a new venv, usearch downloads a binary on first use
os.environ['VISHALAKSHI_VAULT'] = os.environ['ABHYASA_VAULT'] = str(Path(tempfile.mkdtemp())/'vault.db')   # never the real vault
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'tests')]   # `grade_eval`, and the page and exercise data of the tests (for `--dry`)

from fastcore.utils import *
from abhyasa.store import temp_learning
from abhyasa.llm import Router, Fake, route_ask, for_task
from abhyasa.tutor import Tutor
from abhyasa.ground import VaultSource
from abhyasa.sources import file_link, LinkError
from abhyasa.journey import journey_from_sources, walk_from_topic, walk_state, handoff, vault_key
from abhyasa.settings import val
from abhyasa.walk import tutor_note, open_short, code_task, run_code, step_meta
from abhyasa.core.leela import leela_link
from grade_eval import question_checks

CASES = [dict(name='attention', link='1706.03762', pages=1),
         dict(name='gradient-descent', topic='how gradient descent works'),
         dict(name='pydantic-ai', link='https://ai.pydantic.dev', pages=8, tool=True),
         dict(name='claude-code', link='https://docs.claude.com/en/docs/claude-code/overview', pages=8, tool=True)]
PORT = 5019   # the port of the fake Leela address file
def marks() -> str:
    "The guides of the trial, with the walk length from the settings now."
    return f'steps 5 to {val("walks.steps")}; passage on 70% of steps (a paper or docs walk); every question passes; grade right both ways; naive code fails and good code passes; no code check and right links on a tool walk; at most 30 s a step'

class Timed(Router):
    "A `Router` that keeps the seconds of each model call in `calls`."
    def __init__(self, r, calls=None):
        super().__init__(r.dflt, r.models, r.tokens)
        self.calls = [] if calls is None else calls
    def _t(self, f):
        def ask(prompt, sp=''):
            t = time.monotonic()
            try: return f(prompt, sp)
            finally: self.calls.append(time.monotonic() - t)
        return ask
    def __call__(self, prompt, sp=''): return self._t(self.dflt)(prompt, sp)
    def for_(self, task, name=None, job=None): return self._t(super().for_(task, name, job))

@contextmanager
def env(**kw):
    "Set the environment variables `kw` for the block, then put the old values back."
    old = {k: os.environ.get(k) for k in kw}
    os.environ.update(kw)
    try: yield
    finally:
        for k, v in old.items(): os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

def timed(f, *a, **kw):
    "`(result, seconds)` of `f(*a, **kw)`."
    t = time.monotonic(); r = f(*a, **kw)
    return r, time.monotonic() - t

CHOICE = dict(question='Which one tells you the position of a page?', options=[dict(text='Its rank.', misconception=''), dict(text='Its score.', misconception='a score is a position')],
              correct=0, rubric=[])   # a choice question with no model answer

def fake_ask(choice=False):
    "The `Fake` model of the dry run: the replies of the `walk_fake` fixture, a plan, and a grader that fails only 'I am not sure.' With `choice`, a question is a choice question with no model answer."
    from rupaka.spec import gallery
    from walk_data import EXTRACT_REPLY, EXERCISE
    def grader(p, sp):
        ok = 'not sure' not in p.split("Learner's answer:")[1].split("Learner's think-aloud:")[0].lower()
        return dict(correct=ok, grade=8 if ok else 2, first_error='' if ok else 'No idea given.', misconception='', feedback='Say what the step does.')
    plan = dict(title='Gradient descent', subject='ml', steps=[dict(name=n, statement=f'{n} is a step of the method.', slug='', why='It comes first.', needs=[], ways=['words'])
                                                                for n in ('Loss', 'Gradient', 'Learning rate')])
    return Fake({'You grade one answer': grader, 'Give hint level': 'Think about positions.', 'Teach the smallest step': 'Positions are shared. Check: what if k = 0?',
                 'Return JSON: {"concepts"': EXTRACT_REPLY, 'You write a short note': 'Softmax makes weights from scores. Look at what a large score does.',
                 'You write one small Python exercise': EXERCISE, 'You plan a learning path': plan, 'You design one interactive demo': gallery()['reciprocal-rank-fusion']},
                dflt=CHOICE if choice else dict(question='What does a rank tell you?', answer='Its position.', rubric=['position']))

def fake_read(lr):
    "A `read` for `file_link` that files `PAGES` and fetches nothing."
    from walk_data import PAGES
    def read(how, target, **kw):
        src = target if how in ('arxiv', 'pdf') else target.rstrip('/') + '/page'
        d = lr.vault.add([(n, f'{t}\n\n(Pages of {target}.)' if n == 0 else t) for n, t in PAGES], f'Pages of {target}', source=src, kind='web')
        img = lr.vault.assets(d['doc_id'])/'images'/'fig2.png'
        img.parent.mkdir(parents=True, exist_ok=True); img.write_bytes(b'\x89PNG\r\n\x1a\n')
        return dict(doc_id=d['doc_id'])
    return read

def build(lr, ask, case, read=None) -> AttrDict:
    "Make the walk of `case`: a link through `file_link` and `journey_from_sources`, a topic through `walk_from_topic` on the vault."
    t = time.monotonic()
    if 'topic' in case: j = walk_from_topic(lr, ask, case['topic'], sources=[VaultSource(lr)])
    else: j = journey_from_sources(lr, ask, file_link(lr, case['link'], case.get('pages', 8), read=read), tool=bool(case.get('tool')))
    if not j.steps: raise LinkError('The tutor found no ideas on these pages.')
    return AttrDict(j=j, secs=time.monotonic() - t)

def measure(lr, ask, j) -> AttrDict:
    "For each step: the tutor note, and for a short check the question, with `question_checks`. `secs_step` is the mean seconds of a step."
    tutor, kinds, secs, found, figs, asks, ok, bad = Tutor(lr, ask), {}, [], 0, 0, 0, 0, []
    for i, s in enumerate(j.steps):
        t = time.monotonic()
        k = s['check']['kind']; kinds[k] = kinds.get(k, 0) + 1
        found += bool((s.get('read') or {}).get('text')); figs += bool((s.get('read') or {}).get('figure'))
        tutor_note(lr, ask, j, i)
        if k == 'short':
            q = open_short(tutor, lr.journey(j.id), i, 'trial')
            cs = question_checks(q); asks += 1
            if all(o for _, o in cs): ok += 1
            else: bad.append(AttrDict(step=i, name=q.name, question=q.question, failed=[l for l, o in cs if not o]))
        secs.append(time.monotonic() - t)
    return AttrDict(steps=len(j.steps), found=found, figures=figs, kinds=kinds, asks_ok=ok, asks=asks, secs_step=mean(secs), bad_asks=bad)

def as_choice(lr, j) -> AttrDict:
    "Walk `j` with its first short check at depth 1, so that its question is a choice question (`--choice`)."
    k = first(i for i, s in enumerate(j.steps) if s['check']['kind'] == 'short')
    return j if k is None else lr.walk_step(j.id, k, check={**j.steps[k]['check'], 'depth': 1})

def grade_trip(lr, ask, j) -> AttrDict:
    "On the first short step: the model answer of its question must grade correct, and a new question answered 'I am not sure.' must not."
    tutor = Tutor(lr, ask)
    k = first(i for i, s in enumerate(j.steps) if s['check']['kind'] == 'short')
    if k is None: raise ValueError('no short check in this walk')
    c = lr.concept(j.steps[k]['slug'])
    q = open_short(tutor, lr.journey(j.id), k, 'trial')
    o = tutor.open[q.id]
    ans, basis = (o.answer, 'model answer') if o.answer else (o.get('options') and o.options[o.correct]['text'], 'correct option')   # a choice question may have no model answer
    if not ans: raise ValueError('the question has no model answer and no correct option: the grade trip is skipped')
    good = bool(tutor.answer(q.id, ans, confidence=80).correct)
    q2 = tutor.ask_on(c, 2, session='trial', method=j.steps[k]['check']['way'])
    return AttrDict(good=good, weak=not tutor.answer(q2.id, 'I am not sure.', confidence=20).correct, basis=basis)

def code_trip(lr, ask, j) -> AttrDict:
    "On the first code step (else step 0): the stub as the naive try, then the stored solution as the good try; each as `passed of total`."
    t = time.monotonic()
    tutor = Tutor(lr, ask)
    i = first(i for i, s in enumerate(j.steps) if s['check']['kind'] == 'code') or 0
    task = code_task(tutor, lr.concept(j.steps[i]['slug']), session='trial', meta=step_meta(j, i))
    good = tutor.open[task.q.id].answer
    def r(src):
        if not (x := run_code(tutor, task.q.id, src)): raise ValueError('run_code gave no result')
        return f'{x.passed} of {x.total}'
    return AttrDict(naive=r(task.stub), good=r(good), secs=time.monotonic() - t)

def handoff_trip(lr, ask, j, cfg_home) -> AttrDict:
    "On a tool walk, with a fake Leela address file in `cfg_home`: no `code` check, and on each step with `leela` the right link on the page or its card (a notebook step), and no `code-editor` on the page or the card."
    from starlette.testclient import TestClient
    from abhyasa.app import mk_app
    from walk_data import leela_file
    with env(ABHYASA_LEELA_FILE=str(leela_file(cfg_home, port=PORT))):
        j = lr.journey(j.id)
        cl = TestClient(mk_app(lr, ask, transcribe=lambda a, hint='': '', sources=[VaultSource(lr)], hosts=('testserver', '127.0.0.1', 'localhost')))
        cl.post(f'/w/{j.id}/start')
        n = links = pages = skipped = 0
        for i, s in enumerate(j.steps):
            if not s.get('leela'): continue
            n += 1
            want = f'http://127.0.0.1:{PORT}' + handoff(j.id, i, v=vault_key(lr.vault.path))
            links += leela_link(j, i) == want
            page = cl.get(f'/w/{j.id}/{i}').text
            demo = s['check']['kind'] in ('demo', 'order')   # a demo card starts a demo job: not fetched
            card = '' if demo else cl.get(f'/w/{j.id}/{i}/check').text
            skipped += demo
            other = [m for m in re.findall(r'href="(http://127\.0\.0\.1:\d+/learn[^"]*)"', card) if m != want.replace('&', '&amp;')]   # a short card has no link; a link on a card must be right
            go = f'action="/w/{j.id}/{i}/leela"' in card if s['check']['kind'] == 'notebook' else want.replace('&', '&amp;') in page + card   # a notebook card posts, then goes to the link
            pages += go and 'code-editor' not in page + card and not other
    return AttrDict(code_checks=sum(s['check']['kind'] == 'code' for s in j.steps), leela_steps=n, links_ok=links, pages_ok=pages, cards_skipped=skipped)

def free_port() -> int:
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); return s.getsockname()[1]

def shoot(lr, ask, jid, idxs, out, name=None) -> list:
    "Screens of steps `idxs` of walk `jid`: the app under uvicorn on a free port, Playwright's bundled Chromium, both closed in a `finally`."
    import uvicorn
    from playwright.sync_api import sync_playwright
    from abhyasa.app import mk_app
    out, port, got = Path(out), free_port(), []
    out.mkdir(parents=True, exist_ok=True)
    srv = uvicorn.Server(uvicorn.Config(mk_app(lr, ask, transcribe=lambda a, hint='': ''), host='127.0.0.1', port=port, log_level='warning'))
    th = threading.Thread(target=srv.run, daemon=True); th.start()
    try:
        end = time.monotonic() + 30
        while not srv.started and time.monotonic() < end: time.sleep(.1)
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page(viewport=dict(width=1280, height=900))
                base = f'http://127.0.0.1:{port}'
                pg.request.post(f'{base}/w/{jid}/start')
                for i in idxs:
                    pg.goto(f'{base}/w/{jid}/{i}')
                    pg.wait_for_function("() => !document.querySelector('#check .pending')", timeout=120_000)
                    got.append(out/f'{name or jid}-{i}.png')
                    pg.screenshot(path=str(got[-1]), full_page=True)
            finally: b.close()
    finally:
        srv.should_exit = True; th.join(10)
    return got

COLS = ['walk', 'steps', 'with passage', 'figures', 'checks short/demo/order/code', 'one ask', 'grade round trip', 'code naive/good', 'Leela steps and links right', 's/step', 's/call', 'build s']

def _pct(n, d): return f'{n} ({100 * n // d}%)' if d else '0'

def cells(r) -> list:
    "The table cells of a row `r`."
    if r.get('error'): return [r.name, 'error', *['-'] * (len(COLS) - 2)]
    m, g, c, h = r.get('m'), r.get('g'), r.get('c'), r.get('h')
    k = m.kinds
    return [r.name, m.steps, _pct(m.found, m.steps), m.figures, '/'.join(str(k.get(x, 0)) for x in ('short', 'demo', 'order', 'code')),
            f'{m.asks_ok} of {m.asks}', '-' if not g else ('right both ways' if g.good and g.weak else f'wrong (good {g.good}, weak {g.weak})'),
            '-' if not c else f'{c.naive} / {c.good}', '-' if not h else f'{h.leela_steps}, {h.links_ok} links, {h.pages_ok} pages',
            f'{m.secs_step:.1f}', f'{r.s_call:.1f}', f'{r.build.secs:.0f}']

def flags(r) -> list:
    "What is outside the guides, for a row `r`."
    if r.get('error'): return [f'The case failed: {r.error}']
    m, g, c, h, out = r.m, r.get('g'), r.get('c'), r.get('h'), []
    most = val('walks.steps')
    if not 5 <= m.steps <= most: out.append(f'{m.steps} steps (5 to {most})')
    if r.case.get('link') and m.found * 100 < 70 * m.steps: out.append(f'passage on {m.found} of {m.steps} steps (70%)')
    if m.asks_ok < m.asks: out.append(f'{m.asks - m.asks_ok} of {m.asks} questions fail a check')
    if r.get('g_error') or (g and not (g.good and g.weak)): out.append(f'the grade round trip is not right: {g or r.g_error}')
    if c and not (int(c.naive.split()[0]) < int(c.naive.split()[2]) and c.good.split()[0] == c.good.split()[2]): out.append(f'code: naive {c.naive}, good {c.good}')
    if r.get('c_error'): out.append(f'code trip failed: {r.c_error}')
    if r.get('shots_error'): out.append(f'screens failed: {r.shots_error}')
    if h and (h.code_checks or h.links_ok < h.leela_steps or h.pages_ok < h.leela_steps): out.append(f'Leela: {h.code_checks} code checks, {h.links_ok} of {h.leela_steps} links, {h.pages_ok} pages')
    if r.get('h_error'): out.append(f'Leela trip failed: {r.h_error}')
    if m.secs_step > 30: out.append(f'{m.secs_step:.0f} s a step (30)')
    return out

def report(rows, out) -> str:
    "The Markdown of the trial: a table, then the details of each walk. Writes `out/report.md` and prints the table."
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    table = '\n'.join(['| ' + ' | '.join(COLS) + ' |', '|' + ' --- |' * len(COLS), *('| ' + ' | '.join(map(str, cells(r))) + ' |' for r in rows)])
    md = [f'# Walk trial\n\nGuides: {marks()}.\n', table]
    for r in rows:
        md.append(f'\n## {r.name}\n')
        md.append('\n'.join(f'- Outside the guides: {f}' for f in flags(r)) or '- Inside every guide.')
        if r.get('error'): continue
        m = r.m
        md.append(f"- Steps: {m.steps}, and {len(r.build.j.get('more') or ())} more ideas that are not steps; build {r.build.secs:.0f} s; {r.n_calls} model calls, {r.s_call:.1f} s each on average.")
        for b in m.bad_asks: md.append(f'- Step {b.step} ({b.name}) fails {", ".join(b.failed)}: {b.question!r}')
        if r.get('g'): md.append(f'- Grade: the {r.g.basis} graded correct: {r.g.good}; "I am not sure." graded not correct: {r.g.weak}.')
        if r.get('c'): md.append(f'- Code: naive {r.c.naive}, good {r.c.good}, {r.c.secs:.0f} s.')
        if r.get('h'): md.append(f'- Leela: {r.h.leela_steps} steps with a link, {r.h.links_ok} links right, {r.h.pages_ok} pages right, {r.h.code_checks} code checks. {r.h.cards_skipped} demo or order cards were not fetched (a demo card starts a demo job).')
        for e in ('g', 'c', 'h', 'shots'):
            if r.get(f'{e}_error'): md.append(f'- Error ({e}): {r[f"{e}_error"]}')
        md += [f'- Screen: `{p.name}`' for p in r.get('shots') or ()]
    s = '\n'.join(md) + '\n'
    (out/'report.md').write_text(s)
    print(table)
    return s

def run_case(lr, ask, case, a, read, cfg_home) -> AttrDict:
    "Run one case alone; an error goes into the row."
    r, n0 = AttrDict(name=case['name'], case=case), len(ask.calls)
    def step(key, f, *args):
        "Run one part of the case; an error in a part after the build goes into `<key>_error`."
        try: r[key] = f(*args)
        except Exception as e: r[f'{key}_error'] = f'{type(e).__name__}: {e}'
    try:
        r.build = build(lr, ask, case, read)
        j = r.build.j = as_choice(lr, r.build.j) if a.choice else r.build.j
        r.m = measure(lr, ask, j)
    except Exception as e:
        r.error = f'{type(e).__name__}: {e}'
        return r
    step('g', grade_trip, lr, ask, j)
    if case['name'] == 'attention': step('c', code_trip, lr, ask, j)
    if case.get('tool'): step('h', handoff_trip, lr, ask, j, cfg_home)
    if not a.no_shots:
        n = len(j.steps)
        step('shots', lambda: shoot(lr, ask, j.id, sorted({0, n // 2, n - 1}), a.out, case['name']))
    r.n_calls = len(ask.calls) - n0
    r.s_call = mean(ask.calls[n0:]) if r.n_calls else 0.
    return r

def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--model', default=None, help='the default model; the per-task models of your settings still apply')
    p.add_argument('--only', default=None, help='run only the case with this name')
    p.add_argument('--out', default=str(ROOT/'design/screens/trial'))
    p.add_argument('--dry', action='store_true', help='a fake model and fake pages: no network and no browser')
    p.add_argument('--no-shots', action='store_true')
    p.add_argument('--choice', action='store_true', help='with --dry: the first short check of each walk is a choice question with no model answer')
    p.add_argument('--probe', action='store_true', help='with --dry: try one connection off this computer (it is refused), to show that the dry run fails on it')
    a = p.parse_args(argv)
    if a.dry: a.no_shots = True
    tmp = Path(tempfile.mkdtemp())
    if a.dry:
        _no_network()
        base, read = Router(fake_ask(a.choice), models=lambda: {}, tokens=lambda: {}), None
        if a.probe:
            try: socket.create_connection(('192.0.2.1', 9), timeout=1)   # a test address: the guard refuses it before any packet leaves
            except OSError: pass
    else:
        from abhyasa.voice import settings
        s = settings()   # one read of the models and reply caps that you chose; nothing else of the folder is used or changed
        m, t = s['models'], s['tokens']
        base, read = Router(route_ask(a.model), models=lambda: m, tokens=lambda: t), None
    os.environ['ABHYASA_CONFIG'] = str(tmp/'config')   # the app writes its session key here
    import rupaka.check
    rupaka.check.can_check = lambda: False   # a demo is made but not run in a browser: one browser only, for the screens
    lr, ask = temp_learning(), Timed(base)
    if a.dry: read = fake_read(lr)
    cases = [c for c in CASES if a.only in (None, c['name'])]
    if not cases: raise SystemExit(f'no case named {a.only!r}')
    cases.sort(key=lambda c: 'topic' in c)   # a topic walk goes last, when the other cases are filed
    rows = []
    with env(ABHYASA_LEELA_FILE=str(tmp/'leela'/'serving.json')):   # only the address file of Leela moves; HOME and XDG_CONFIG_HOME stay as they are, so the model sees your login
        for c in cases:
            rows.append(run_case(lr, ask, c, a, read, tmp))
    report(rows, a.out)
    if BLOCKED: raise SystemExit(f'dry run: {len(BLOCKED)} connection(s) to a host off this computer were refused: {sorted(set(BLOCKED))}')

BLOCKED = []   # the hosts that a dry run tried to reach

def _no_network():
    "In a dry run, refuse a connection to any host but this computer, and keep each refused host in `BLOCKED`."
    real, real_ex = socket.socket.connect, socket.socket.connect_ex
    def off(self, addr): return self.family != socket.AF_UNIX and str(addr[0]) not in ('127.0.0.1', '::1', 'localhost')
    def connect(self, addr, *a):
        if off(self, addr): BLOCKED.append(str(addr[0])); raise OSError(f'dry run: no network ({addr[0]})')
        return real(self, addr, *a)
    def connect_ex(self, addr, *a):
        if off(self, addr): BLOCKED.append(str(addr[0])); return errno.EACCES
        return real_ex(self, addr, *a)
    socket.socket.connect, socket.socket.connect_ex = connect, connect_ex

if __name__ == '__main__': main()
