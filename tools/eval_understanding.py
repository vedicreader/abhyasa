"""Opt-in eval of the chain idea -> question -> grade -> feedback on a fixed set of 20 steps. It calls real models; CI never runs it.

Run on a COPY of a vault, never on `~/.vishalakshi/vault.db`:
  uv run python tools/eval_understanding.py --vault /tmp/understand-vault/vault.db --out understanding/eval-before
The first run on a vault builds the book walk from `--book` (a Project Gutenberg text file). For each step it writes the walk
check with the app's tutor (`Tutor.ask_on`, models from `route_ask` and the settings), makes 3 test answers with a probe model that
does not see the rubric (own words with the core idea, a recital of the page, a known wrong idea), grades each with the app's grader
(`Tutor._grade`), and asks a judge model (not the writer model) to score each stage on the criteria of the audit.
Cost of one run: 20 steps x (1 question + 1 probe + 3 grades + 1 judge) + 5 plan judges = 125 calls, plus each plain-English
rewrite and each lazy fill of `core`; the run counts and prints every call. Building the book walk once costs about 10 more calls."""
import argparse, json, os, re, sys, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

NO = [Path(p).resolve() for p in ('~/.vishalakshi', '/tmp/abhyasa-combo', '/tmp/abhyasa-eval', '/tmp/abhyasa-walk', '/tmp/audit-vault')]
BOOK_ID, BOOK_TITLE = 'scott-efficiency', 'Increasing Human Efficiency in Business (Walter Dill Scott, 1911)'
WALKS = {'1706-03762-5134': 'Attention Is All You Need', 'how-a-neural-network-works-19cb': 'How a Neural Network Works',
         'encoder-decoder-architecture-and-cross-a-a9c2': 'Encoder-decoder and cross-attention', 'nbs-15-ddpm-4c03': 'DDPM'}
STEPS = [   # (group, walk id or '', concept slug); the book steps are the first 4 steps of the book walk
    ('attention', '1706-03762-5134', 'sequential-bottleneck-of-recurrent-models'),
    ('attention', '1706-03762-5134', 'multi-head-attention-projection-and-concatenation'),
    ('attention', '1706-03762-5134', 'transformer-translation-results'),
    ('nn', 'how-a-neural-network-works-19cb', 'functions-and-the-neuron'),
    ('nn', 'how-a-neural-network-works-19cb', 'backpropagation'),
    ('nn', 'how-a-neural-network-works-19cb', 'rotary-position-embeddings-and-multimodal-embeddings'),
    ('nn', 'encoder-decoder-architecture-and-cross-a-a9c2', 'token-embeddings'),
    ('nn', 'encoder-decoder-architecture-and-cross-a-a9c2', 'queries-keys-and-values'),
    ('ddpm', 'nbs-15-ddpm-4c03', 'ddpm-simplifying-assumptions'),
    ('ddpm', 'nbs-15-ddpm-4c03', 'unconditional-image-generation'),
    ('ddpm', 'nbs-15-ddpm-4c03', 'forward-noising-of-an-image'),
    ('sanskrit', '', 'sa-sandhi-vowels'),
    ('sanskrit', '', 'sa-karakas'),
    ('sanskrit', '', 'sa-middle-voice'),
    ('jyotisha', '', 'jy-nakshatra-punarvasu'),
    ('jyotisha', '', 'jy-graha-saturn'),
    *[('book', BOOK_ID, i) for i in range(4)]]
PROBE_MODEL, JUDGE_MODEL = 'claude/sonnet', 'claude/claude-opus-5-5'
CALLS = Counter()

def guard_vault(p) -> Path:
    "The vault path `p`, resolved; exit when it is the real vault or a folder that other work owns."
    r = Path(p).expanduser().resolve()
    if any(r == n or n in r.parents for n in NO): sys.exit(f'Refused: {r} is not a copy that this eval can write to.')
    return r

def counted(base):
    "A `RouteAsk` subclass whose every call adds one to `CALLS[job]`."
    class Counted(base):
        def via(self, task, name='', max_tokens=None, prepare=None):
            f = super().via(task, name, max_tokens, prepare)
            def ask(p, sp=''): CALLS[task] += 1; return f(p, sp)
            ask.stream, ask.model = f.stream, f.model
            return ask
    return Counted

def book_text(path) -> str:
    "Chapters I to III of the Gutenberg text at `path`: the text between the second 'CHAPTER I' line and 'CHAPTER IV'. Data only."
    t = Path(path).read_text(encoding='utf-8', errors='replace')
    t = t.split('*** START', 1)[-1].split('*** END', 1)[0]
    starts = [m.start() for m in re.finditer(r'^CHAPTER I\s*$', t, re.M)]
    end = re.search(r'^CHAPTER IV\s*$', t, re.M)
    return t[starts[-1]:end.start() if end else None].strip()

PROBE_SP = "You write test answers for an eval of a tutor. You are not the learner. Follow the brief exactly. Return JSON only."
def probe_prompt(c, page, question) -> str:
    return (f"Idea: {c.name}\nThe page the learner read:\n<page>\n{page[:3000]}\n</page>\n\nThe tutor's question:\n{question}\n\n"
            "Write three answers to this question, each 1 to 3 sentences, as a learner would type them:\n"
            "- `own`: a learner who understands the idea. Give the core reason in plain everyday words. Use as few of the page's terms as you can. Do not add extra points.\n"
            "- `recital`: a learner who only remembers the page. Repeat the page's terms and phrases that touch the question, but give no reason and no causal link.\n"
            "- `wrong`: a learner with one common, real misconception about this idea. Say it with confidence, as if it is right.\n"
            "- `wrong_idea`: the misconception of `wrong`, in under 12 words.\n"
            'Return JSON: {"own": str, "recital": str, "wrong": str, "wrong_idea": str}')

CRITERIA = """Criteria (from the audit). Answer each with true or false.
Step: S1 the step is one idea that a novice must grasp, not two. S2 the idea is stated as an understanding (what it does and why, or what problem it solves), not a fact of the paper, a history line, a number or a remark. S3 details (sizes, constants, names) are not the idea. S4 the step names 1 to 3 common wrong ideas (false when none is given). trivia: true when the idea of the step is only a number, a score, a year, an ablation or a remark of the author.
Explanation (only when a note is given, else null): E1 the note makes the idea make sense (a case, a reason, or where an analogy stops). E2 it never points at the wording of the passage or at the check.
Check: C1 it asks the learner to explain, predict, compare, or apply the idea to a new case (not recall a fact, not 'why' about a rule of a text that cannot be reasoned out). C2 it targets the understanding of the step, not a detail of its statement. C3 it uses the real terms of the subject; an analogy or the learner's world never adds a thing to decode (an analogy is fine only as 'where does this analogy break?'). C4 its kind and its depth label agree with what it asks.
Grade: G1 the 'own' answer passed if it holds the core idea in any words (true when the grade is right about it). G2 no grade fails an answer for a point that the question did not ask. G3 no slip (a typo, a sum, a loose word) is labeled as a misconception. G4 the 'recital' answer did not pass.
Feedback: F1 each feedback names the gap in understanding, or, when right, ties the idea to a next idea. F2 no feedback only restates the answer key.
c_match: true when the grade of the 'wrong' answer failed it and its misconception names the same wrong idea as the probe's wrong idea (or one of the step's known wrong ideas)."""
JUDGE_SP = "You are a strict judge of a tutor's teaching chain. You judge understanding, not wording. Return JSON only."

def judge_prompt(r) -> str:
    s = r['step']
    gs = '\n'.join(f"- {k} answer: {json.dumps(r['probes'].get(k, ''))}\n  grade: {json.dumps({x: r['grades'][k].get(x) for x in ('correct', 'grade', 'first_error', 'misconception', 'slip', 'feedback') if x in r['grades'][k]}, ensure_ascii=False)}"
                   for k in ('own', 'recital', 'wrong') if k in r['grades'])
    return (f"Step: {s['name']} (subject {s['subject']})\nStatement: {s['statement']}\nCore (the understanding, when given): {s.get('core') or '(none)'}\n"
            f"Known wrong ideas: {json.dumps(s.get('wrong') or [], ensure_ascii=False)}\n"
            f"Note under the passage: {json.dumps(r.get('note') or None, ensure_ascii=False)}\n\n"
            f"Check: depth {r['q']['depth']} ({r['q']['depth_name']}), kind {r['q']['kind']}" + (f", facet {r['q']['facet']}" if r['q'].get('facet') else '') + f", way {r['q'].get('method')}\nQuestion: {r['q']['question']}\n"
            f"Model answer (hidden): {r['q'].get('answer')}\nRubric: {json.dumps(r['q'].get('rubric'), ensure_ascii=False)}\n\n"
            f"Test answers and their grades. The probe's wrong idea: {json.dumps(r['probes'].get('wrong_idea', ''))}\n{gs}\n\n{CRITERIA}\n\n"
            'Return JSON: {"S1": bool, "S2": bool, "S3": bool, "S4": bool, "trivia": bool, "E1": bool|null, "E2": bool|null, '
            '"C1": bool, "C2": bool, "C3": bool, "C4": bool, "G1": bool, "G2": bool, "G3": bool, "G4": bool, "F1": bool, "F2": bool, "c_match": bool, "why": str}')

PLAN_SP = JUDGE_SP
def plan_prompt(j, cs) -> str:
    ls = '\n'.join(f"{k}. {c.name}: {(c.get('core') or c.get('statement') or '')[:300]}" for k, c in enumerate(cs, 1))
    claim = (j.get('map') or {}).get('claim', '')
    return (f"Walk: {j.get('title')}\nGoal: {j.get('goal')}\n" + (f"Claim of the source: {claim}\n" if claim else '') + f"Steps:\n{ls}\n\n"
            "P1 the walk has 3 to 7 big ideas, and together they explain the main claim of the source or the goal. "
            "P2 no step is only a number, a year, a score, an ablation or a remark of the author. P3 each step is on the goal.\n"
            'Return JSON: {"P1": bool, "P2": bool, "P3": bool, "trivia_steps": [str], "why": str}')

def build_book(lr, ask, path):
    "Make the book walk with the app's own `journey_from_text`, once; the walk id is fixed so a rerun finds it."
    from abhyasa.path import journey_from_text
    import abhyasa.path as P
    j0 = P._new_id
    P._new_id = lambda title: BOOK_ID
    try: return journey_from_text(lr, ask, book_text(path), BOOK_TITLE, subject='business')
    finally: P._new_id = j0

def remap(lr, ask):
    "Map each ML walk of `WALKS` again from its steps and its `more` ideas, with the app's `walk_map`, and save the new steps, `more` and `map`."
    from abhyasa.path import walk_map
    for jid in WALKS:
        if (j := lr.journey(jid)) is None or j.get('map'): continue
        have = {s['slug'] for s in j.steps}
        steps = [*j.steps, *(dict(slug=s, status='todo', why='') for s in j.get('more') or () if s not in have and lr.concept(s))]
        ss, more, mp = walk_map(lr, ask, steps)
        if mp: lr.put_journey({**j, 'steps': ss, 'more': more, 'map': mp})
        print(f"remapped {jid}: {[s['slug'] for s in ss]}", flush=True)

def page_of(lr, j, s, c) -> str:
    "The text that the learner read for step `s`: its passage, else a passage of the concept, else its statement."
    t = ((s or {}).get('read') or {}).get('text') or ''
    if not t: t = next((p.get('passage') for p in c.get('provenance') or () if isinstance(p, dict) and p.get('passage')), '')
    return t or c.get('statement', '')

def main():
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('--vault', help='a COPY of a vault: vault.db')
    a.add_argument('--table', nargs='+', help='no run: print the markdown table of these result JSON files, side by side')
    a.add_argument('--book', default='/tmp/scott-book/pg1319.txt', help='the Gutenberg text of the book walk')
    a.add_argument('--out', help='path stem: writes <out>.json')
    a.add_argument('--only', type=int, default=0, help='run the first N steps only (a smoke run)')
    a.add_argument('--threads', type=int, default=3)
    a.add_argument('--steps', action='store_true', help='with --table: also list each step of the last file')
    a.add_argument('--remap', action='store_true', help='map the 4 ML walks again with `walk_map` first (4 calls), as after an edit')
    o = a.parse_args()
    if o.table: return print(table(o.table) + ('\n\n' + steps_md(o.table[-1]) if o.steps else ''))
    vault = guard_vault(o.vault)
    os.environ.setdefault('ABHYASA_CONFIG', '/tmp/understand-config')
    from fastcore.utils import AttrDict
    from abhyasa.learner import Learning, DEPTHS
    from abhyasa.models import Router, RouteAsk, ask_json
    from abhyasa.tutor import Tutor
    from abhyasa.path import short_check, step_meta
    ask = Router(counted(RouteAsk)())
    lr = Learning(str(vault))
    t0 = time.time()
    if lr.journey(BOOK_ID) is None:
        build_book(lr, ask, o.book)
        print(f'built the book walk: {dict(CALLS)}', flush=True)
    if o.remap: remap(lr, ask)
    setup = dict(CALLS); CALLS.clear()
    tutor = Tutor(lr, ask)
    rows = []
    for g, jid, key in STEPS[:o.only or None]:   # the questions: one at a time, as they read and write the vault
        j = lr.journey(jid) if jid else None
        s = j.steps[key] if isinstance(key, int) else next((x for x in (j.steps if j else ()) if x['slug'] == key), None)
        c = lr.concept(s['slug'] if s else key)
        ck = short_check(lr, c)
        meta = step_meta(j, j.steps.index(s)) if s else None
        q = tutor.ask_on(c, ck.depth, ck.get('why', ''), method=ck.way, meta=meta, read=(s or {}).get('note') or '')
        oq = tutor.open[q.id]
        c = lr.concept(c.slug)   # again: the tutor can fill `core` and `wrong` on the way
        rows.append(dict(group=g, walk=jid, in_walk=bool(s) if jid else None, step=dict(slug=c.slug, name=c.name, subject=c.get('subject', ''), statement=c.get('statement', ''),
                                                       core=c.get('core', ''), wrong=c.get('wrong') or []),
                         note=(s or {}).get('note') or '', page=page_of(lr, j, s, c)[:3000],
                         q=dict(id=q.id, question=oq.question, answer=oq.get('answer'), rubric=oq.get('rubric'), depth=oq.depth,
                                depth_name=DEPTHS[oq.depth], kind=oq.kind, method=oq.get('method'), facet=oq.get('facet', ''), core=oq.get('core', ''))))
        print(f"q {len(rows)}: {c.name}: {oq.question[:120]!r}", flush=True)
    probe = ask.dflt.via('eval.probe', PROBE_MODEL)
    def do_probe(r):
        r['probes'] = ask_json(probe, probe_prompt(AttrDict(r['step']), r['page'], r['q']['question']), PROBE_SP, need=('own', 'recital', 'wrong'))
    with ThreadPoolExecutor(o.threads) as ex: list(ex.map(do_probe, rows))
    def do_grade(r, k):
        oq = AttrDict(tutor.open[r['q']['id']]); oq.turns, oq.tries = [dict(who='tutor', kind='question', text=oq.question)], []
        conf = 85 if k == 'wrong' else 70
        try: r.setdefault('grades', {})[k] = dict(tutor._grade(oq, r['probes'][k], '', conf))
        except Exception as e: r.setdefault('grades', {})[k] = dict(error=repr(e))
    with ThreadPoolExecutor(o.threads) as ex: list(ex.map(lambda rk: do_grade(*rk), [(r, k) for r in rows for k in ('own', 'recital', 'wrong')]))
    judge = ask.dflt.via('eval.judge', JUDGE_MODEL)
    def do_judge(r):
        try: r['judge'] = ask_json(judge, judge_prompt(r), JUDGE_SP, need=('why',))
        except Exception as e: r['judge'] = dict(error=repr(e))
    with ThreadPoolExecutor(o.threads) as ex: list(ex.map(do_judge, rows))
    plans = {}
    def do_plan(jid):
        j = lr.journey(jid); cs = [lr.concept(s['slug']) or AttrDict(name=s['slug']) for s in j.steps]
        try: plans[jid] = dict(title=j.title, steps=[c.name for c in cs], **ask_json(judge, plan_prompt(j, cs), PLAN_SP, need=('why',)))
        except Exception as e: plans[jid] = dict(title=j.title, error=repr(e))
    jids = [*dict.fromkeys(jid for _, jid, _ in STEPS[:o.only or None] if jid)]
    with ThreadPoolExecutor(o.threads) as ex: list(ex.map(do_plan, jids))
    for r in rows: tutor.open.pop(r['q']['id'], None)
    out = dict(at=time.strftime('%Y-%m-%d %H:%M'), vault=str(vault), seconds=round(time.time() - t0), setup_calls=setup, calls=dict(CALLS),
               n_calls=sum(CALLS.values()), models=dict(probe=PROBE_MODEL, judge=JUDGE_MODEL, tasks=ask.models() if callable(ask.models) else {}),
               summary=summary(rows, plans), plans=plans, rows=rows)
    Path(f'{o.out}.json').write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str))
    print(json.dumps(dict(calls=out['calls'], n_calls=out['n_calls'], summary=out['summary']), indent=1))

def _ok(r, k): return bool((r.get('judge') or {}).get(k))

def summary(rows, plans) -> dict:
    "The counts on the audit's targets."
    g = lambda r, k: (r.get('grades') or {}).get(k) or {}
    n = len(rows)
    return dict(steps=n,
        own_pass=sum(bool(g(r, 'own').get('correct')) for r in rows),
        recital_pass=sum(bool(g(r, 'recital').get('correct')) for r in rows),
        wrong_fail=sum(not g(r, 'wrong').get('correct') for r in rows),
        wrong_match=sum(_ok(r, 'c_match') for r in rows),
        trivia_steps=sum(_ok(r, 'trivia') for r in rows),
        questions_c1_c4=sum(all(_ok(r, k) for k in ('C1', 'C2', 'C3', 'C4')) for r in rows),
        feedback_f1_f2=sum(all(_ok(r, k) for k in ('F1', 'F2')) for r in rows),
        **{k: sum(_ok(r, k) for r in rows) for k in ('S1', 'S2', 'S3', 'S4', 'C1', 'C2', 'C3', 'C4', 'G1', 'G2', 'G3', 'G4', 'F1', 'F2')},
        notes=sum(r.get('judge', {}).get('E1') is not None for r in rows),
        E1=sum(_ok(r, 'E1') for r in rows), E2=sum(_ok(r, 'E2') for r in rows),
        plans=len(plans), **{k: sum(bool(p.get(k)) for p in plans.values()) for k in ('P1', 'P2', 'P3')})

TARGETS = [('own_pass', '(a) own words with the core idea pass', '>= 18'), ('recital_pass', '(b) a recital of the page passes', '<= 2'),
           ('wrong_match', '(c) a known wrong idea gets a matching misconception', '>= 15'), ('trivia_steps', 'steps whose idea is a number, a score or a remark', '0'),
           ('questions_c1_c4', 'questions that pass C1-C4', '>= 18'), ('feedback_f1_f2', 'feedback that passes F1-F2', '>= 18')]
MORE = ['S1', 'S2', 'S3', 'S4', 'C1', 'C2', 'C3', 'C4', 'G1', 'G2', 'G3', 'G4', 'F1', 'F2', 'E1', 'E2', 'P1', 'P2', 'P3']

def table(paths) -> str:
    "The markdown table of the audit's targets, then each criterion, for each result file in `paths`."
    rs = [json.loads(Path(p).read_text()) for p in paths]
    head = '| Target | Goal | ' + ' | '.join(Path(p).stem for p in paths) + ' |\n|---|---|' + '---|' * len(paths)
    rows = [f"| {label} | {goal} of {rs[0]['summary']['steps']} | " + ' | '.join(str(r['summary'].get(k, '')) for r in rs) + ' |' for k, label, goal in TARGETS]
    of = lambda r, k: r['summary']['plans'] if k.startswith('P') else r['summary']['notes'] if k.startswith('E') else r['summary']['steps']
    rows += [f"| {k} | yes | " + ' | '.join(f"{r['summary'].get(k, '')} of {of(r, k)}" for r in rs) + ' |' for k in MORE]
    rows.append('| model calls in the run | ~100 | ' + ' | '.join(str(r['n_calls']) for r in rs) + ' |')
    return '\n'.join([head, *rows])

def steps_md(path) -> str:
    "One markdown item for each step of the result file `path`: the question, the three grades and the criteria that the judge failed."
    out = []
    for r in json.loads(Path(path).read_text())['rows']:
        g, j = r.get('grades') or {}, r.get('judge') or {}
        v = lambda k: f"{'pass' if g.get(k, {}).get('correct') else 'fail'} ({g.get(k, {}).get('grade')})"
        bad = [k for k in MORE if j.get(k) is False]
        out.append(f"- **{r['step']['name']}** ({r['group']}, depth {r['q']['depth']}, {r['q'].get('facet') or r['q']['kind']}"
                   + ('' if r.get('in_walk') in (None, True) else ', now a detail of the walk') + f"): {json.dumps(r['q']['question'][:240], ensure_ascii=False)}\n"
                   f"  own {v('own')}, recital {v('recital')}, wrong {v('wrong')} with misconception {json.dumps(g.get('wrong', {}).get('misconception', ''), ensure_ascii=False)}. "
                   f"Judge fails: {', '.join(bad) or 'none'}.")
    return '\n'.join(out)

if __name__ == '__main__': main()
