# The Guided Walk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a paper, a pasted text or a topic into a walk: one idea at a time in reading order, each with its passage, figure, a short tutor note and one check (short answer, predict-first demo, or a code task run in the browser), all logged and reviewed as today.

**Architecture:** The engine change comes first and is useful alone: `extract` keeps placement and modality fields, `method.py` gets the new ways, `allowed=` and `check_for`, and a walk is a journey whose steps carry `read` and `check`. A new engine module `walk.py` runs a step (note, short answer, code task, isolated run). A new hand-written block `blocks/walk` shows the plan and the steps and talks to other blocks only through hooks and links.

**Tech Stack:** Python 3.12+, nbdev 3 on hatchling (engine notebooks in `nbs/`), FastHTML + htmx (blocks), vishalakshi vault, rupaka demos, `abhyasa.llm.Fake` for tests, pytest, Playwright bundled Chromium for the one browser check.

**Spec:** `docs/superpowers/specs/2026-10-28-guided-walk-design.md`

## Global Constraints

- Engine code is edited only in `nbs/*.ipynb`; then run `uv run nbdev-prepare` (hyphen). Never edit a generated `abhyasa/*.py` engine file (`store, model, llm, tutor, sources, voice, ground, rama, nb, demo, journey, profile, method, prompts, check, walk`).
- Web code (`abhyasa/blocks/`, `abhyasa/core/`, `abhyasa/app.py`) is written by hand and tested with `uv run pytest`.
- A block never imports another block. It adds to other pages only through hooks: `today_next`, `concept_more`, `lesson_extra` (and the others in `core/hooks.py`).
- `NAMES` in `abhyasa/blocks/__init__.py` gets `walk` after `demo` and before `today`.
- Prose (UI text, prompts, notebooks, docs, commit messages) is ASD-STE100 Simplified Technical English, US grade 9.
- Notebooks read as documents: an intro, short sections, a one-line lead before each code cell, small tests with a line on what each checks.
- Tests use `temp_learning()` and `abhyasa.llm.Fake`. Never open `~/.vishalakshi/vault.db` or `~/.config/abhyasa`.
- Browser checks: Playwright `p.chromium.launch(headless=True)`, no `executable_path`, one browser at a time, closed in a `finally`.
- New prompt text is registered with `prompts.register`: `extract`, `walk.note`, and `way.demo`, `way.order`, `way.playground`, `way.board`, `way.timeline` (by the loop in `method.py`).
- `TEXT_WAYS = ('code', 'maths', 'analogy', 'example', 'diagram', 'words')`; `WALK_WAYS = TEXT_WAYS + ('demo', 'order')`.
- Check kinds: `short`, `demo`, `order`, `code`. Depths: short 2 (floor < 2) else 3; code 4; demo and order 2, or 3 with a why.
- Learner code: `run_isolated(..., total=10., sandbox=True)`; 2 s per test; `python -I -B`; kill at 12 s; `RLIMIT_CPU` 11 s; `RLIMIT_FSIZE` 10 MB; no network.
- `MAX_TRIES` stays 3. A syntax error uses no try.
- A passage is at most 600 chars and shows only when found word for word. A tutor note is 2 or 3 sentences, at most 60 words.
- Figures only from `lr.vault.assets()`, suffix in `.png .jpg .jpeg .gif .webp`.
- Keys: ⌥S start, ⌥N next idea, ⌥H hint, ⌘↵ send or run, 1-9 options, K keep.
- No new runtime dependency and no new vendored script.
- Commit messages are one plain STE line. No AI credit. No Co-Authored-By line.

## Review Focus

1. **A long paper** (15 pages, over 40 000 chars): the walk must have steps from the last sections too, not stop where `Vault.document` cuts at 40 000 chars. Test: `long_paper_reaches_the_end` in Task 1.
2. **A model that paraphrases the quote or names a figure file that is not there**: the step shows the concept statement marked "In the tutor's words" and no broken image, never a passage that is not in the paper. Tests: `quote_not_in_text_gives_no_passage` in Task 1 and `step_without_passage_or_figure` in Task 5.
3. **Reload, Back or a second tab on a step with an open check**: the same question comes back, no second question is made, no try is logged twice, and a double press of "Next idea" moves one step only. Test: `reload_keeps_one_question_and_next_is_idempotent` in Task 5.
4. **Learner code that hangs at the top level, has a syntax error, opens a socket, or prints a fake pass line and exits**: no hang over 12 s, no try used for the syntax error, the socket fails, and the fake line does not pass. Test: `hostile_code_does_not_pass_or_hang` in Task 7.
5. **A demo that the model cannot make, or that takes long**: the step does not stay on "making a demo"; it falls back to a short answer, and "Next idea" works all the time. Test: `demo_failure_falls_back_to_short_answer` in Task 6.

---

## Shared test data

Task 1 writes this data once, as the plain module `tests/walk_data.py`. Engine notebooks load it with one hidden cell (`#| hide`: `import sys; sys.path.insert(0, '../tests'); from walk_data import *`; nbdev runs a notebook in `nbs/`). Block tests use `from walk_data import *` (pytest puts `tests/` on the path for its `conftest.py`). Task 5 adds the fixture `walk_fake(fake)` to `tests/conftest.py`: it adds the rules below to the same `fake` object that `mk` uses, and returns it.

```python
import json, re, time

PAGES = [(0, '1 Introduction\n\nRecurrent models compute along the positions of the input. '
             'This inherently sequential nature precludes parallelization within training examples.'),
         (3, '3.2.1 Scaled Dot-Product Attention\n\nWe compute the dot products of the query with all keys, divide each by √dk, '
             'and apply a softmax function to obtain the weights on the values.\n\n![Figure 2](images/fig2.png)'),
         (4, 'We suspect that for large values of dk, the dot products grow large in magnitude, pushing the softmax '
             'function into regions where it has extremely small gradients.')]

def add_paper(lr):
    "File the paper on the main shelf with its figure file; return the doc id."
    d = lr.vault.add(PAGES, 'Attention Is All You Need', source='/tmp/attention.pdf', kind='pdf')
    img = lr.vault.assets('attention')/'images'/'fig2.png'
    img.parent.mkdir(parents=True, exist_ok=True); img.write_bytes(b'\x89PNG\r\n\x1a\n')
    return d['doc_id']

EXTRACT_REPLY = dict(concepts=[
    dict(name='Sequential computation', statement='A recurrent model computes one position after another, so it cannot run the positions of one example in parallel.',
         aliases=[], prereqs=[], section='1 Introduction', quote='This inherently sequential nature precludes parallelization within training examples.',
         figure='', ways=['words', 'analogy'], moves=[], when=None, who=[]),
    dict(name='Softmax', statement='Softmax turns a list of scores into weights that are above 0 and add to 1.', aliases=['softmax function'], prereqs=[],
         section='3.2.1 Scaled Dot-Product Attention', quote='apply a softmax function to obtain the weights on the values',
         figure='images/fig2.png', ways=['code', 'maths'], moves=['weights'], when=None, who=[]),
    dict(name='Scaling by the root of dk', statement='Attention divides the dot products by √dk, so large vectors do not push softmax into regions with very small gradients.',
         aliases=[], prereqs=['Softmax'], section='3.2.1 Scaled Dot-Product Attention', quote='the dot products grow large in magnitude',
         figure='', ways=['demo', 'maths'], moves=['dot products', 'weights'], when=None, who=['Vaswani'])])

EXERCISE = dict(task='Write softmax(x, t=1.0). It returns weights that add to 1. It must not fail on large scores.', fname='softmax',
                stub='import math\n\ndef softmax(x, t=1.0):\n    ...',
                tests=['assert round(sum(softmax([1.0, 2.0, 3.0])), 6) == 1.0', 'assert softmax([0.0, 0.0]) == [0.5, 0.5]',
                       dict(test='assert max(softmax([1000.0, 1001.0])) < 1', say='It does not fail on large scores', hidden=True)],
                solution='import math\ndef softmax(x, t=1.0):\n    m = max(x)\n    e = [math.exp((v - m) / t) for v in x]\n    return [v / sum(e) for v in e]')

GOOD = 'import math\ndef softmax(x, t=1.0):\n    m = max(x)\n    e = [math.exp((v - m) / t) for v in x]\n    return [v / sum(e) for v in e]'
NAIVE = 'import math\ndef softmax(x, t=1.0):\n    e = [math.exp(v / t) for v in x]\n    return [v / sum(e) for v in e]'

def wait_for(f, secs=5.):
    "The first value of `f()` that is not None, asked every 0.1 s for `secs`; None at the end."
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if (v := f()) is not None: return v
        time.sleep(.1)

def walk(cl, lr):
    "File the paper, make a walk from it through the app, and return the journey id."
    return cl.post('/walk/new', data=dict(ref=add_paper(lr))).headers['hx-redirect'].split('/')[-1]
```

`walk_fake` is the `fake` fixture of `tests/conftest.py` plus these rules: `'Return JSON: {"concepts"': EXTRACT_REPLY`, `'You write a short note': 'Softmax makes weights from scores. Look at what a large score does.'`, `'You write one small Python exercise': EXERCISE`.

---

### Task 1: Extract keeps the reading order and the modality fields

**Files:**
- Modify: `nbs/04_sources.ipynb` (cells `#c007` `EXTRACT_SP`/`extract_prompt`, `#c011` `extract`/`from_vault`; new cells for `doc_pages`, `locate`, `figure_path`, `placement`)
- Create: `tests/walk_data.py` (the "Shared test data" above)
- Generated: `abhyasa/sources.py`

**Interfaces:**
- Consumes: `Learning.put`, `store._union`, `llm.ask_json`, `prompts.register, prompt`, `Vault.store(where=..., select=...)` (as `Vault.document` uses it), `Vault.assets(name=None)`.
- Produces:
  - `doc_pages(lr:Learning, ref:str, shelf:str='store') -> AttrDict(doc_id:str, title:str, source:str, pages:list[tuple[int|None, str]])` — every chunk, in page order, no char cap. `page` is the 1-based page a reader sees (vishalakshi stores the 0-based `enumerate` index; add 1; check this against a real PDF doc in a temp vault).
  - `locate(pages:list, quote:str) -> tuple[int|None, int, int]|None` — `(page, start, end)` of `quote` with white space and case folded; None when not found or `quote` shorter than 12 chars.
  - `figure_path(lr:Learning, source:str, link:str) -> str|None` — the path relative to `lr.vault.assets()` of `link` resolved under `lr.vault.assets(Path(source).stem)`, only when the file exists, stays inside the assets root, and has an allowed suffix.
  - `placement(c, doc_id:str) -> AttrDict|None` — the newest provenance entry of concept `c` with this `doc_id`.
  - `extract(lr, ask, text:str='', subject:str='', source:dict=None, pages:list=None) -> L` — when `pages` is given, windows are built from the pages and each concept's provenance entry is `{**source, order, section, page, span, passage, figure}`; concept fields `ways`, `moves`, `who` merge by `_union`; `when`, `image` (first figure), `visual=bool(moves)` are set.
  - `from_vault(lr, ask, ref, subject='', shelf='store') -> L` — uses `doc_pages`; source `dict(src='vault', shelf=shelf, doc_id=..., title=...)`.
  - `EXTRACT_SP` registered as `register('extract', 'Concept finder', ..., EXTRACT_SP)`; `extract` uses `prompt('extract')`.

- [ ] **Step 1: Write the failing tests** (test cells at the end of the notebook, each with a one-line lead)

```python
lr = temp_learning(); did = add_paper(lr)
ask = Fake({'Return JSON: {"concepts"': EXTRACT_REPLY})
slugs = from_vault(lr, ask, did)
p = placement(lr.concept('softmax'), did)
assert list(slugs) == ['sequential-computation', 'softmax', 'scaling-by-the-root-of-dk']
assert (p.order, p.section, p.page) == (1, '3.2.1 Scaled Dot-Product Attention', 4)
assert p.passage.startswith('apply a softmax function') and p.figure == 'attention/images/fig2.png'
assert lr.concept('softmax').ways == ['code', 'maths'] and lr.concept('softmax').visual is True
assert lr.concept('softmax').image == 'attention/images/fig2.png' and lr.concept('scaling-by-the-root-of-dk').who == ['Vaswani']
assert 'Concept finder' == PROMPTS['extract'].label

# a second paper that names Softmax keeps its own placement
d2 = lr.vault.add([(0, 'Softmax gives weights.')], 'Notes', source='/tmp/notes.md', kind='file')['doc_id']
from_vault(lr, Fake({'Return JSON: {"concepts"': dict(concepts=[dict(name='Softmax', statement='', quote='Softmax gives weights.', section='', ways=['words'])])}), d2)
assert placement(lr.concept('softmax'), did).page == 4 and placement(lr.concept('softmax'), d2).page == 1
assert lr.concept('softmax').ways == ['code', 'maths', 'words']

# quote_not_in_text_gives_no_passage, and a figure file that is not there gives no figure
bad = dict(concepts=[dict(name='Masking', statement='The decoder hides later positions.', quote='we mask out all values', figure='images/nope.png', section='3.2.3')])
lr2 = temp_learning(); d3 = add_paper(lr2); from_vault(lr2, Fake({'Return JSON: {"concepts"': bad}), d3)
m = placement(lr2.concept('masking'), d3)
assert m.passage == '' and m.span is None and m.figure is None

# long_paper_reaches_the_end: 15 pages of 4 000 chars; the reply names the section that the window holds
long = [(i, f'{i + 1} Section {i + 1}\n\n' + f'Idea {i + 1} is stated here. ' * 140) for i in range(15)]
lr3 = temp_learning(); d4 = lr3.vault.add(long, 'Long paper', source='/tmp/long.pdf', kind='pdf')['doc_id']
def per_window(p, sp):
    ns = sorted({int(n) for n in re.findall(r'Idea (\d+) is stated', p)})
    return json.dumps(dict(concepts=[dict(name=f'Idea {n}', statement=f'Idea {n}.', quote=f'Idea {n} is stated here.', section=f'{n} Section {n}') for n in ns]))
from_vault(lr3, per_window, d4)
assert placement(lr3.concept('idea-15'), d4).page == 15
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run nbdev-test --path nbs/04_sources.ipynb`
Expected: FAIL with `NameError: name 'add_paper' is not defined` (after adding the data cell: `NameError: name 'placement' is not defined`).

- [ ] **Step 3: Implement** the interfaces above in `nbs/04_sources.ipynb`.
  - `extract_prompt` asks for `{"concepts": [{"name", "statement", "aliases", "prereqs", "section", "quote", "figure", "ways", "moves", "when", "who"}]}`, keeps the prefix `Return JSON: {"concepts"`, and lists the way names from `method.METHODS` in the prompt text (import inside the function, so `sources` does not import `method` at the top). `EXTRACT_SP` adds: list concepts in the order of the text; `quote` is one short sentence copied exactly; `figure` is an image link copied from the text or ""; `ways` only from the list.
  - Windows come from pages joined in order (`_windows` on the joined text); `locate` searches all pages, so a window border does not lose a quote.
  - `order` is the index after a stable sort on `(page, start)` for located concepts; an unlocated concept keeps its model place after the concept before it.
  - Placement goes only in the provenance entry. Never write the concept-level `order`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run nbdev-prepare && uv run nbdev-test --path nbs/04_sources.ipynb && uv run pytest -q`
Expected: PASS; the existing suite still passes (`tests/blocks/test_vault.py` and Add use `extract` with text).

- [ ] **Step 5: Commit**

```bash
git add nbs/04_sources.ipynb abhyasa/sources.py abhyasa/_modidx.py tests/walk_data.py
git commit -m "Keep the order, section, passage and figure of each idea when you extract a source"
```

---

### Task 2: The ways: demo, order and the modality ways, `allowed=` and `check_for`

**Files:**
- Modify: `nbs/13_method.ipynb` (cells `#d475cb12`, `#0b702e9a`; new cell for `check_for`)
- Modify: `nbs/10_demo.ipynb` (cell `#c021` `record_prediction`)
- Modify: `nbs/03_tutor.ipynb` (`Tutor.teach`: `left` from `TEXT_WAYS`)
- Modify: `abhyasa/blocks/strengths/ui.py:32` (list only ways with counts or in `WALK_WAYS`)
- Test: `tests/blocks/test_strengths.py`
- Generated: `abhyasa/method.py`, `abhyasa/demo.py`, `abhyasa/tutor.py`

**Interfaces:**
- Consumes: `posterior`, `mean`, `improving`, `credit_method`, `Learning.record`.
- Produces:
  - `METHODS` with 11 keys: the 6 of today plus `demo`, `order`, `playground`, `board`, `timeline`; `LABELS` for each (`Demos`, `Put in order`, `Playgrounds`, `Boards`, `Timelines`).
  - `TEXT_WAYS`, `WALK_WAYS` (values in Global Constraints); `CHECK_KIND = dict(demo='demo', order='order', code='code')`.
  - `choose(st, subject='', weak=False, rng=None, explore='sometimes', prior=(), allowed=None) -> tuple[str, str]`.
  - `check_for(c, st, rng=None, explore='sometimes', prior=(), last:str='') -> AttrDict(way:str, kind:str, depth:int, why:str)`.
  - `Learning.record_prediction(slug, gate, picked, ans, ok, why='', context='', session='', confidence=None, kind='demo', method='demo', **meta) -> AttrDict`.

- [ ] **Step 1: Write the failing tests** (in `nbs/13_method.ipynb`, and one in `nbs/10_demo.ipynb`)

```python
rng = random.Random(0)
assert {'demo', 'order', 'playground', 'board', 'timeline'} <= set(METHODS) and 'way.timeline' in PROMPTS
assert all(choose(EMPTY, rng=rng)[0] in TEXT_WAYS for _ in range(200))          # a session never gets a way it cannot show
assert all(choose(EMPTY, rng=rng, allowed=['demo', 'maths'])[0] in ('demo', 'maths') for _ in range(200))
assert choose(EMPTY, rng=rng, allowed=['board'])[0] in METHODS                   # an allowed list keeps its own ways
assert choose(EMPTY, rng=rng, allowed=['nope'])[0] in TEXT_WAYS                  # no known way: back to the text ways

c = AttrDict(ways=['code', 'maths'], floor=0)
k = check_for(c, EMPTY, rng=random.Random(1))
assert (k.way, k.kind, k.depth) in {('code', 'code', 4), ('maths', 'short', 2)} and k.why
assert check_for(AttrDict(ways=['demo'], floor=0), EMPTY).kind == 'demo'
assert check_for(AttrDict(ways=['timeline'], floor=3), EMPTY).way in TEXT_WAYS   # no timeline view yet
assert check_for(AttrDict(ways=['words'], floor=3), EMPTY).depth == 3
assert all(check_for(AttrDict(ways=['demo', 'code'], floor=0), EMPTY, rng=rng, last='demo').way == 'code' for _ in range(20))
```

```python
# in 10_demo: a prediction credits `demo`, and keeps the walk meta
lr = temp_learning(); lr.put('Reciprocal rank fusion', 'Sum 1/(k + rank).', 'ml')
d = lr.put_demo(gallery()['reciprocal-rank-fusion'], 'reciprocal-rank-fusion')
g = first(b['id'] for b in d.spec['blocks'] if b.get('type') == 'gate')
a = lr.record_prediction(d.slug, g, 1, 1, True, session='s1', walk='w1', step=2)
assert (a.kind, a.method, a.walk, a.step) == ('demo', 'demo', 'w1', 2)
assert 'demo' in lr.stats().methods['ml'] and 'diagram' not in lr.stats().methods['ml']
assert lr.record_prediction(d.slug, g, 0, 1, False, kind='order', method='order').kind == 'order'
```

```python
# tests/blocks/test_strengths.py: test_ways_with_no_view_stay_hidden
def test_ways_with_no_view_stay_hidden(mk):
    page = mk().get('/you/strengths').text
    assert 'Demos' in page and 'Timelines' not in page and 'Boards' not in page
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run nbdev-test --path nbs/13_method.ipynb; uv run nbdev-test --path nbs/10_demo.ipynb; uv run pytest tests/blocks/test_strengths.py -q`
Expected: FAIL with `AssertionError` on the first `METHODS` line, `TypeError: ... unexpected keyword argument 'walk'`, and `Timelines` found.

- [ ] **Step 3: Implement.**
  - `choose`: filter `ps` to `allowed` (default `TEXT_WAYS`; when nothing in it is in `METHODS`, `TEXT_WAYS`); `prior` and `improving` only over the candidates. The rest of the logic does not change.
  - `check_for`: candidates `[w for w in c.get('ways') or () if w in WALK_WAYS] or list(TEXT_WAYS)`; drop `last` when another candidate is left; `way, note = choose(st, c.get('subject', ''), False, rng, explore, prior, allowed=candidates)` (never `weak=True`: a walk check explores); `kind = CHECK_KIND.get(way, 'short')`; depth per Global Constraints; `why = note or f'{LABELS[way].lower()} fits this idea'`.
  - `record_prediction`: credit `method`, pass `kind`, `method` and `**meta` to `record`. Meta keys must not be record's own parameters; raise `ValueError` for `kind`/`method`/`session` inside `meta`.
  - Strengths: show a way when it has counts, or when it is in `WALK_WAYS`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run nbdev-prepare && uv run nbdev-test --path nbs/13_method.ipynb && uv run nbdev-test --path nbs/10_demo.ipynb && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add nbs/13_method.ipynb nbs/10_demo.ipynb nbs/03_tutor.ipynb abhyasa/ abhyasa/blocks/strengths/ui.py tests/blocks/test_strengths.py
git commit -m "Add the demo, order, playground, board and timeline ways, and let choose use only the ways that fit"
```

---

### Task 3: A walk is a journey with `read` and `check` on each step

**Files:**
- Modify: `nbs/11_journey.ipynb` (`PLAN_SP`/`plan_prompt`/`plan` get `ways`; new section "Walks" after `plan`)
- Generated: `abhyasa/journey.py`

**Interfaces:**
- Consumes: Task 1 `from_vault`, `extract(..., pages=)`, `placement`; Task 2 `check_for`; `ground.ground`; `Learning.stats`, `Learning.profile`.
- Produces:
  - `journey_from_source(lr, ask, ref:str, shelf:str='store', subject:str='') -> AttrDict` — journey with `mode='walk'`, `source={shelf, doc_id, title}`, `started=None`, `sitting=None`; one step per concept of this source in placement order; `read` per spec 6.3; `check` from `check_for`; `status='known'` for a concept with floor 4 or more.
  - `journey_from_text(lr, ask, text:str, title:str, subject:str='') -> AttrDict` — the same, `source=None`, `read.text` from the text.
  - `walk_from_topic(lr, ask, goal:str, who:str='', sources=None) -> AttrDict` — `plan`, then `read` from the first grounded passage that names the idea (`ground(name, sources, 1, must=[name, *aliases])`; `dict(src, ref, title, url, text, section='', figure=None)`, or `None` when there is none), `check` from `check_for`, `mode='walk'`.
  - `Learning.walk_step(jid:str, i:int, **kv) -> AttrDict` — merge `kv` into step `i` and save; `KeyError` for a missing journey, `IndexError` for a bad `i`.
  - `walk_state(j) -> AttrDict(steps:list, current:int|None, done:int, total:int, sections:list[tuple[str, list[int]]])` — each step gets `dot` in `done`, `shaky`, `skipped`, `known`, `now`, `todo` (`done` = outcome `solid`; `shaky` = `fragile`, `gap`, `misconception`).
  - `STEP_MIN = dict(short=2, order=2, demo=3, code=6)` and `minutes(step) -> int` (reading at 200 words a minute plus `STEP_MIN`).

- [ ] **Step 1: Write the failing tests**

```python
lr = temp_learning(); did = add_paper(lr)
ask = Fake({'Return JSON: {"concepts"': EXTRACT_REPLY})
j = journey_from_source(lr, ask, did)
assert j.mode == 'walk' and j.source == dict(shelf='store', doc_id=did, title='Attention Is All You Need') and j.started is None
assert [s['slug'] for s in j.steps] == ['sequential-computation', 'softmax', 'scaling-by-the-root-of-dk']
r = j.steps[1]['read']
assert (r['section'], r['page'], r['figure']) == ('3.2.1 Scaled Dot-Product Attention', 4, 'attention/images/fig2.png')
assert j.steps[1]['check']['kind'] in ('code', 'short') and j.steps[2]['check']['way'] in ('demo', 'maths')
assert progress(lr, j).total == 3                                                # progress does not change

ws = walk_state(lr.walk_step(j.id, 0, done=dict(outcome='fragile', aid='a1', at=1.)))
assert [s.dot for s in ws.steps] == ['shaky', 'now', 'todo'] and ws.current == 1
assert ws.sections == [('1 Introduction', [0]), ('3.2.1 Scaled Dot-Product Attention', [1, 2])]
assert minutes(j.steps[1]) >= 2

lr.update('softmax', floor=4)
assert journey_from_source(lr, ask, did).steps[1]['status'] == 'known'          # you know it: the walk keeps it, as known

jt = journey_from_text(lr, ask, PAGES[1][1], 'Attention notes')
sm = next(s for s in jt.steps if s['slug'] == 'softmax')
assert jt.source is None and sm['read']['text'].startswith('apply a softmax function')
assert next(s for s in jt.steps if s['slug'] == 'sequential-computation')['read']['text'] == ''   # its quote is not in this text

PLAN = dict(title='Attention', subject='ml', steps=[dict(name='Softmax', statement='', slug='softmax', why='Weights.', needs=[], ways=['code'])])
class Notes:
    name = 'notes'
    def search(self, q, k=4): return [passage('vault:notes', 'n1', 'My notes', 'Softmax turns scores into weights.')]
jw = walk_from_topic(lr, Fake({'You plan a learning path': PLAN}), 'learn attention', sources=[Notes()])
assert jw.mode == 'walk' and jw.steps[0]['read']['text'].startswith('Softmax turns') and jw.steps[0]['check']
assert walk_from_topic(lr, Fake({'You plan a learning path': PLAN}), 'learn attention', sources=[]).steps[0]['read'] is None
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run nbdev-test --path nbs/11_journey.ipynb`
Expected: FAIL with `NameError: name 'journey_from_source' is not defined`.

- [ ] **Step 3: Implement** the interfaces in `nbs/11_journey.ipynb`. `check_for` gets `lr.stats()`, the profile's `explore` and `prior` (as `Tutor.ask_on` builds them), and a `random.Random()`; one shared helper `_check(lr, c)` for all three makers. `read.text` is the placement passage, or `''` when it was not found.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run nbdev-prepare && uv run nbdev-test --path nbs/11_journey.ipynb && uv run pytest tests/blocks/test_journeys.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add nbs/11_journey.ipynb abhyasa/journey.py abhyasa/_modidx.py
git commit -m "Make a walk from a source, a text or a topic: a journey with a passage and a check on each step"
```

---

### Task 4: The step runtime: the tutor note and the short-answer check

**Files:**
- Modify: `nbs/03_tutor.ipynb` (`question_prompt`, `Tutor.ask_on`, `Tutor.answer`, `Tutor._close`)
- Create: `nbs/15_walk.ipynb` (intro, sections "The note", "A short answer", "The sitting log"), add it to `nbs/sidebar.yml`
- Generated: `abhyasa/tutor.py`, `abhyasa/walk.py`

**Interfaces:**
- Consumes: Task 2 `TEXT_WAYS`, Task 3 `Learning.walk_step`, `walk_state`; `Session._logged`, `Session.save`.
- Produces:
  - `question_prompt(c, depth, avoid=(), ctx='', who='', bridge=(), method='', read='')` — with `read`, adds "The learner just read this. Ask past it; do not ask them to repeat a sentence of it:" and the text.
  - `Tutor.ask_on(c, depth, why='', session='', mode=None, method:str=None, meta:dict=None, read:str='') -> AttrDict` — `method` skips `choose`; `meta` goes into every `record` of the question (tries and close); review rule of spec 6.4.
  - `NOTE_SP` registered as `register('walk.note', 'Walk note', ..., NOTE_SP)`; it starts with `You write a short note`.
  - `tutor_note(lr, ask, j, i:int) -> str` — cached in the step's `note`.
  - `step_meta(j, i:int) -> dict` — `dict(walk=j.id, step=i, section=..., page=...)`.
  - `open_short(tutor, j, i:int, session:str) -> AttrDict` — the public question; stores its id in the step's `qid`.
  - `Session.noted(a:dict, floor0:int)` — add one log row for an attempt made outside `Session.answer` (a demo or order prediction), then `save`.

- [ ] **Step 1: Write the failing tests** (in `nbs/15_walk.ipynb`)

```python
lr = temp_learning(); did = add_paper(lr)
ask = Fake({'Return JSON: {"concepts"': EXTRACT_REPLY, 'You write a short note': 'Softmax makes weights from scores. Look at what a large score does.',
            'You grade one answer': dict(correct=True, grade=9, first_error='', misconception='', feedback='Yes.')},
           dflt=dict(question='Why do the weights add to 1?', answer='Each is divided by the sum.', rubric=['divide by the sum']))
j = journey_from_source(lr, ask, did)
t = Tutor(lr, ask, context=False)

n = tutor_note(lr, ask, j, 1)
assert n.startswith('Softmax makes') and lr.journey(j.id).steps[1]['note'] == n
assert tutor_note(lr, Fake(), lr.journey(j.id), 1) == n                         # kept: no second model call

s = Session(t, journey=j.id)
lr.walk_step(j.id, 1, check=dict(way='words', kind='short', depth=2, why='plain words fit'))
q = open_short(t, lr.journey(j.id), 1, s.id); s.q = q
assert q.method == 'words' and q.depth == 2                                      # the step's check decides, not `choose`
assert 'answer' not in q and 'rubric' not in q and lr.journey(j.id).steps[1]['qid'] == q.id
assert 'The learner just read this' in ask.calls[-1][0] and n in ask.calls[-1][0]
r = s.answer('Each weight is divided by the sum of all.')
a = lr.attempts('softmax', limit=1)[0]
assert r.done and (a.walk, a.step, a.section, a.page) == (j.id, 1, '3.2.1 Scaled Dot-Product Attention', 4)
assert s.log[-1]['concept'] == 'softmax'

# the review rule: the last way of a walk check is left out
lr.update('softmax', due=0)
assert all(t.ask_on(lr.concept('softmax'), 3).method != a.method for _ in range(10))

s.noted(dict(concept='softmax', question='Predict', correct=True, outcome='solid', method='demo', kind='demo'), floor0=2)
assert s.log[-1]['method'] == 'demo' and lr.session(s.id).log[-1]['method'] == 'demo'
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run nbdev-test --path nbs/15_walk.ipynb`
Expected: FAIL with `ImportError: cannot import name 'tutor_note'` (the module does not exist yet).

- [ ] **Step 3: Implement.**
  - `ask_on`: store `meta` as `q.meta`; `answer` and `_close` pass `**q.get('meta', {})` to `record`. `public` drops nothing new (meta is safe).
  - The review rule reads `first(self.learning.attempts(c['slug'], limit=5).filter(lambda a: a.get('final')))`.
  - `tutor_note` prompt input: concept name and statement, `read.text`, and the check kind; never the check question. Reply text is cut to 3 sentences.
  - `Session.noted` builds the same row shape as `_logged` (`qid=''`, `floor0`, `floor` from the concept now).

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run nbdev-prepare && uv run nbdev-test --path nbs/15_walk.ipynb && uv run nbdev-test --path nbs/03_tutor.ipynb && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add nbs/03_tutor.ipynb nbs/15_walk.ipynb nbs/sidebar.yml abhyasa/tutor.py abhyasa/walk.py abhyasa/_modidx.py
git commit -m "Add the walk step: a short tutor note and a short-answer check that logs its walk and step"
```

---

### Task 5: The walk block: the plan, the step page and short-answer checks

**Files:**
- Create: `abhyasa/blocks/walk/{__init__.py, cfg.py, ui.py, app.py, walk.css, walk.js}`
- Modify: `abhyasa/blocks/__init__.py` (`NAMES`)
- Modify: `tests/conftest.py` (fixture `walk_fake`, see "Shared test data")
- Test: `tests/blocks/test_walk.py`

**Interfaces:**
- Consumes: Task 3 `journey_from_source`, `walk_state`, `minutes`, `Learning.walk_step`; Task 4 `tutor_note`, `open_short`, `step_meta`; `Session`, `moved`; `core.Page`, `Md`, `asset_css`, `asset_js`.
- Produces:
  - `Routes` in `cfg.py` with the routes of spec 6.8 (`new='/walk/new'`, `one='/w/{jid}'`, `plan='/w/{jid}/plan'`, `start='/w/{jid}/start'`, `step='/w/{jid}/{i}'`, `check`, `answer`, `hint`, `giveup`, `run`, `predict`, `keep`, `next`, `done`, `img` under `/w/{jid}/{i}/...`) and `Routes.of(route, **kw)`.
  - `CHECKS: dict[str, Callable]` in `ui.py`: `short` here; Tasks 6 and 8 add `demo`, `order`, `code`.
  - `CAPS = ('learning', 'tutor', 'ask', 'pool', 'sessions', 'sources')`.
  - The step page has `id="rail"`, `id="passage"`, `id="figure"` (when there is one), `id="note"`, and `id="check"` with `hx-get` to the check route and `hx-trigger="load"`.

- [ ] **Step 1: Write the failing tests**

```python
from walk_data import *

def test_plan_then_start(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr)
    page = cl.get(f'/w/{jid}').text
    assert 'Attention Is All You Need' in page and page.index('1 Introduction') < page.index('3.2.1 Scaled Dot-Product Attention')
    assert 'Start the walk' in page and 'min' in page
    cl.post(f'/w/{jid}/plan', data=dict(i=1, act='check', way='code'))
    assert lr.journey(jid).steps[1]['check'] == dict(way='code', kind='code', depth=4, why='you chose it')
    assert cl.post(f'/w/{jid}/plan', data=dict(i=1, act='check', way='board')).status_code == 400   # no board view yet
    cl.post(f'/w/{jid}/plan', data=dict(i=0, act='drop'))
    assert [s['slug'] for s in lr.journey(jid).steps][0] == 'softmax'
    r = cl.post(f'/w/{jid}/start', follow_redirects=False)
    assert r.headers['location'] == f'/w/{jid}/0' and lr.journey(jid).started and lr.journey(jid).sitting

def test_step_page_and_short_check(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why='plain words fit'))
    page = cl.get(f'/w/{jid}/1').text
    assert 'apply a softmax function' in page and f'src="/w/{jid}/1/img"' in page and 'Softmax makes weights' in page
    assert lr.journey(jid).steps[1]['read_at']
    card = cl.get(f'/w/{jid}/1/check').text
    assert 'What does a rank tell you?' in card and 'Its position.' not in card and 'rubric' not in card   # no answer in the HTML
    r = cl.post(f'/w/{jid}/1/answer', data=dict(answer='the rank is a position', confidence=70)).text
    assert 'Next idea' in r and lr.attempts('softmax', limit=1)[0].walk == jid
    assert cl.get(f'/w/{jid}/1/img').headers['content-type'] == 'image/png'

def test_next_skips_and_moves_on(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    r = cl.post(f'/w/{jid}/0/next', follow_redirects=False)
    assert lr.journey(jid).steps[0]['done']['outcome'] == 'skipped' and not lr.attempts('sequential-computation')
    assert r.headers['location'] == f'/w/{jid}/0/done'                             # step 1 is in a new section
    assert 'Section done' in cl.get(f'/w/{jid}/0/done').text and f'href="/w/{jid}/1"' in cl.get(f'/w/{jid}/0/done').text
    assert cl.post(f'/w/{jid}/1/next', follow_redirects=False).headers['location'] == f'/w/{jid}/2'   # same section: the next step

def test_reload_keeps_one_question_and_next_is_idempotent(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    a, b = cl.get(f'/w/{jid}/1/check').text, cl.get(f'/w/{jid}/1/check').text
    assert lr.journey(jid).steps[1]['qid'] and a.count('What does a rank') == b.count('What does a rank') == 1
    n = len([c for c in walk_fake.calls if 'Write ONE question' in c[0]])
    assert n == 1                                                                  # the reload made no second question
    cl.post(f'/w/{jid}/1/next'); cl.post(f'/w/{jid}/1/next')
    assert lr.journey(jid).steps[2]['done'] is None                                # a double press moves one step only

def test_step_without_passage_or_figure(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 2, read={**lr.journey(jid).steps[2]['read'], 'text': '', 'figure': None})
    page = cl.get(f'/w/{jid}/2').text
    assert "In the tutor's words" in page and '<img' not in page
    assert cl.get(f'/w/{jid}/2/img').status_code == 404

def test_image_route_stays_in_assets(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr)
    lr.walk_step(jid, 1, read={**lr.journey(jid).steps[1]['read'], 'figure': '../../vault.db'})
    assert cl.get(f'/w/{jid}/1/img').status_code == 404
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/blocks/test_walk.py -q`
Expected: FAIL with 404 on `/walk/new` (and `test_blocks.py` passes until the folder exists without `NAMES`).

- [ ] **Step 3: Implement the block.**
  - `connect` registers every route at its end. `ask` is looked up on each call with `for_task(ctx.ask, 'extract')`, as in the journeys block.
  - The sitting: `j.sitting` names a `Session(tutor, journey=jid)` in `ctx.sessions` (or `Session.load`); the walk sets `s.q` itself and never calls `Session.next`.
  - `plan` POST: `act='drop'` removes step `i`; `act='check'` takes a way in `WALK_WAYS` (else 400) and sets `check` with the kind and depth rules of Task 2 and `why='you chose it'`.
  - `check` GET: when `qid` is still in `tutor.open`, show that question; else make one with `open_short`.
  - `next` POST: when the step has `done`, only redirect (idempotent); else drop an open question from `tutor.open` without a record and set `done.outcome='skipped'`. Redirect (303) to `/w/{jid}/{i+1}`, or to `/w/{jid}/{i}/done` when step `i` ends its section.
  - `done` GET (`Routes.done = '/w/{jid}/{i}/done'`): the section summary ("Section done", `moved` over the log rows of this section), ends the sitting, and links "Go on" to the next step; the next step opens a new sitting.
  - The passage shows with `Md` in a `blockquote` with "From the paper, section …, p. …" (or the title of the grounded source for a topic walk); with no passage, the statement with "In the tutor's words".
  - `img`: resolve `lr.vault.assets()/figure`, refuse when the resolved path is not inside the assets root or the suffix is not allowed; `FileResponse` with its media type.
  - Look: one column, the rail at the left, the check card on the raised surface (as `shots/a2-walk-code.png`). `walk.js` binds ⌥N to the next form and ⌥H to hint.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/blocks/test_walk.py tests/test_blocks.py -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add abhyasa/blocks/walk abhyasa/blocks/__init__.py tests/conftest.py tests/blocks/test_walk.py
git commit -m "Add the walk block: the plan, one idea per page with its passage and figure, and a short-answer check"
```

---

### Task 6: Demo and order checks, made before the step

**Files:**
- Modify: `nbs/10_demo.ipynb` (`put_demo`, `demo_for`, `make_demo`, `queue_demo`)
- Modify: `abhyasa/blocks/walk/{app.py, ui.py, walk.js}`
- Test: `tests/blocks/test_walk.py`
- Generated: `abhyasa/demo.py`

**Interfaces:**
- Consumes: Task 2 `record_prediction(..., kind, method, **meta)`; Task 4 `step_meta`, `Session.noted`; Task 5 `CHECKS`, `Routes`.
- Produces:
  - `Learning.put_demo(spec, concept, by='hand', checked=None, aim:str='') -> AttrDict` (meta `aim`).
  - `Learning.demo_for(concept, aim:str=None) -> AttrDict|None`.
  - `make_demo(learning, ask, slug, first_error='', check=None, log=None, aim:str='') -> AttrDict|None` — `aim='order'` asks for one gate with a ranklist of 3 to 6 steps and passes a ranklist gallery spec in `examples`.
  - `queue_demo(tutor, slug, first_error='', aim='')` — job key `f'{slug}:{aim}'`; `job_state(tutor, slug, aim='')`.
  - `CHECKS['demo']`, `CHECKS['order']`: a card of class `walk-demo` (not `demo-card`, so `demo.js` does not post it) with `data-url` to the walk predict route; `walk.js` posts each `rk-predict` and the "Keep this state" button (K) posts the rupaka state to `keep`.

- [ ] **Step 1: Write the failing tests**

```python
def test_demo_check_is_made_ahead_and_logged(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 2, check=dict(way='demo', kind='demo', depth=2, why='a demo fits'))
    cl.get(f'/w/{jid}/1')                                                          # opening step 1 makes the demo of step 2
    d = wait_for(lambda: lr.demo_for('scaling-by-the-root-of-dk'))
    assert d is not None
    card = cl.get(f'/w/{jid}/2/check').text
    assert 'walk-demo' in card and 'demo-card' not in card and f'/w/{jid}/2/predict' in card
    g = first(b['id'] for b in d.spec['blocks'] if b.get('type') == 'gate')
    assert cl.post(f'/w/{jid}/2/predict', data=dict(slug=d.slug, gate=g, picked='1', ans='1', ok='true', why='bigger dot products')).json()['ok']
    a = lr.attempts('scaling-by-the-root-of-dk', limit=1)[0]
    assert (a.kind, a.method, a.walk, a.step, a.depth) == ('demo', 'demo', jid, 2, 3)
    assert lr.journey(jid).steps[2]['done']['outcome'] in ('solid', 'fragile')
    cl.post(f'/w/{jid}/2/keep', data=dict(state='{"dk": 256, "scale": false}'))
    assert lr.attempts('scaling-by-the-root-of-dk', limit=1)[0].keep == {'dk': 256, 'scale': False}

def test_order_check_logs_order(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='order', kind='order', depth=2, why=''))
    cl.get(f'/w/{jid}/0')
    d = wait_for(lambda: lr.demo_for('softmax', aim='order')); g = first(b['id'] for b in d.spec['blocks'] if b.get('type') == 'gate')
    cl.post(f'/w/{jid}/1/predict', data=dict(slug=d.slug, gate=g, picked='0', ans='1', ok='false'))
    assert lr.attempts('softmax', limit=1)[0].kind == 'order'

def test_demo_failure_falls_back_to_short_answer(mk, walk_fake, lr):
    walk_fake.rules['You design one interactive demo'] = '{}'                     # every author try fails the checks
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 2, check=dict(way='demo', kind='demo', depth=2, why=''))
    cl.get(f'/w/{jid}/1')
    card = wait_for(lambda: (t := cl.get(f'/w/{jid}/2/check').text) if 'pending' not in t else None, secs=10)
    assert 'What does a rank tell you?' in card and lr.journey(jid).steps[2]['check']['kind'] == 'short'
    assert cl.post(f'/w/{jid}/2/next').status_code in (200, 303)
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/blocks/test_walk.py -k "demo or order" -q`
Expected: FAIL: `demo_for` returns None after opening step 1, and `predict` gives 404.

- [ ] **Step 3: Implement.**
  - Step GET for `i` queues the demo of step `i + 1` when its kind is `demo` or `order` and `demo_for(slug, aim)` is None. The tests run with `ctx.pool`; a test pool runs jobs at once or the test waits on the job (use the pool the `mk` fixture gives).
  - Check GET for a demo step: demo ready → card; job running and younger than 90 s → a pending card that polls the check route every 2 s; failed, or older than 90 s → `walk_step(jid, i, check=check_for(..., allowed text ways))` with `kind='short'` and show the short card.
  - `predict`: refuse (404) a `slug` whose demo is not of this step's concept; `record_prediction(slug, gate, ..., session=sitting, kind=step kind, method=step way, **step_meta(j, i))` (it stores `gate` itself), `Session.noted`, then `done` on the first prediction.
  - The pending card has class `pending`; the tests poll on that word.
  - `keep`: `json.loads` the state (at most 20 000 chars; else 400), `mark_attempt(aid, keep=state)` on the newest attempt of this step.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run nbdev-prepare && uv run nbdev-test --path nbs/10_demo.ipynb && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add nbs/10_demo.ipynb abhyasa/demo.py abhyasa/blocks/walk tests/blocks/test_walk.py
git commit -m "Make the demo before the step, log demo and order predictions with the walk, and fall back to a short answer"
```

---

### Task 7: Run learner code in a closed process, and the code task

**Files:**
- Modify: `nbs/06_check.ipynb` (`snippet`, `parse`, `run_isolated`)
- Modify: `nbs/08_nb.ipynb` (split `new_exercise` out of `Exercise.__init__`)
- Modify: `nbs/15_walk.ipynb` (section "A code task")
- Test: `tests/test_check.py`, `tests/test_exercise.py`
- Generated: `abhyasa/check.py`, `abhyasa/nb.py`, `abhyasa/walk.py`

**Interfaces:**
- Consumes: `validate_exercise`, `code_prompt`, `code_sp`, `public`, `Tutor._close`, `MAX_TRIES`; Task 4 `step_meta`, `Session._logged`.
- Produces:
  - `run_isolated(kind, fname, source, tests, *, total=10., setup=(), sandbox=True) -> dict` — `public` dict, or `{'timeout': True}`, or `{'error': 'no check result'}`.
  - `parse(text, nonce:str=None) -> dict` — with `nonce`, only a line with that nonce counts.
  - `new_exercise(ask, c) -> AttrDict(task, fname, stub, tests, solution)` — the model call with one retry; `Exercise.__init__` uses it.
  - `code_task(tutor, c, session:str='', meta:dict=None) -> AttrDict(q, stub:str, fname:str, tests:list[str])` — `q` is the public question (`kind='code'`, `depth=4`, `method='code'`); `tests` holds the text of visible tests only.
  - `run_code(tutor, qid:str, source:str, confidence:int=70) -> AttrDict` — `syntax` (`'line 3: invalid syntax'` or `''`), `checks` (public), `passed`, `total`, `first_error`, `tries_left`, `done`; when `done`, the `_close` result fields too.
  - `Session.code(source:str, confidence:int=70) -> AttrDict` — `run_code` on `self.q`, `_logged` on a close, `save`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_check.py
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
```

```python
# nbs/15_walk.ipynb: a code task, a syntax error, a failing try, a pass
lr = temp_learning(); did = add_paper(lr)
ask = Fake({'Return JSON: {"concepts"': EXTRACT_REPLY, 'You write one small Python exercise': EXERCISE, 'Teach the smallest step': 'Take away the max. Check: what is softmax([5, 5])?'})
j = journey_from_source(lr, ask, did); t = Tutor(lr, ask, context=False); s = Session(t, journey=j.id)
k = code_task(t, lr.concept('softmax'), s.id, step_meta(j, 1)); s.q = k.q
assert k.fname == 'softmax' and 'm = max(x)' not in k.stub and len(k.tests) == 2         # the hidden test text stays on the server
assert 'answer' not in k.q and 'rubric' not in k.q
r = s.code('def softmax(x, t=1.0)\n    return x')
assert r.syntax.startswith('line 1') and r.tries_left == 3 and not r.done                # a typo is not a try
r = s.code(NAIVE)
assert (r.passed, r.total, r.done, r.tries_left) == (2, 3, False, 2) and 'large scores' in r.first_error
assert not any(c['got'] for c in r.checks if c['hidden'])                                 # no expected value of a hidden test
r = s.code(GOOD)
a = lr.attempts('softmax', limit=1)[0]
assert r.done and r.correct and (a.kind, a.depth, a.method, a.walk) == ('code', 4, 'code', j.id)
assert s.log[-1]['concept'] == 'softmax' and lr.stats().methods['*']['code'][0] > 0
```

```python
# tests/test_exercise.py: test_exercise_uses_new_exercise
def test_exercise_uses_new_exercise(lr):
    ex = new_exercise(Fake({'You write one small Python exercise': EXERCISE}), lr.concept('ranking'))
    assert ex.fname == 'softmax' and ex.solution.startswith('import math')
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/test_check.py::test_hostile_code_does_not_pass_or_hang tests/test_exercise.py -q; uv run nbdev-test --path nbs/15_walk.ipynb`
Expected: FAIL: the fake line passes, `new_exercise` and `code_task` are not defined.

- [ ] **Step 3: Implement.**
  - `run_isolated`: make a temp dir; `subprocess.run([sys.executable, '-I', '-B'], cwd=tmp, env={'PATH': os.defpath, 'HOME': tmp}, preexec_fn=limits, timeout=total + 2)` with `limits` setting `RLIMIT_CPU` to `total + 1` and `RLIMIT_FSIZE` to 10 MB (skip `preexec_fn` off POSIX). With `sandbox`, put a prelude before `source`: `sys.addaudithook` that raises `PermissionError` on events starting `socket.`, on `subprocess.Popen`, `os.system`, `os.exec`, `os.posix_spawn`, `os.fork`, and on `open` with a write mode for a path outside `tmp`.
  - A process killed by its limits (a negative return code, as from `SIGXCPU`) gives `{'timeout': True}`, the same as `TimeoutExpired`.
  - `snippet` gets the nonce in `data` and prints `{"nonce": nonce, **public(result)}`; `parse(text, nonce)` skips lines without it.
  - `run_code`: `ast.parse` first (syntax → no try, message `line N: msg`); then `run_isolated`; grade and close as `Exercise.check` does (`g.grade = 10 * passed // total`; first error: hidden → `"{label}: {status}"`, visible → `"This test fails: `{test}` ({error})"`; timeout → "The code ran longer than 10 s"; no result → "The code stopped before the tests ran"). The visible-test text is in `q.rubric`; `q.answer` is the solution and never leaves the server.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run nbdev-prepare && uv run nbdev-test --path nbs/06_check.ipynb && uv run nbdev-test --path nbs/15_walk.ipynb && uv run pytest -q`
Expected: PASS, including the existing `test_run_isolated`.

- [ ] **Step 5: Commit**

```bash
git add nbs/06_check.ipynb nbs/08_nb.ipynb nbs/15_walk.ipynb abhyasa/check.py abhyasa/nb.py abhyasa/walk.py abhyasa/_modidx.py tests/test_check.py tests/test_exercise.py
git commit -m "Run learner code in a closed process with no network, and add the code task of a walk step"
```

---

### Task 8: The code check in the browser

**Files:**
- Modify: `abhyasa/blocks/walk/{app.py, ui.py, walk.css, walk.js}`
- Test: `tests/blocks/test_walk.py`

**Interfaces:**
- Consumes: Task 7 `code_task`, `Session.code`; Task 5 `CHECKS`, `Routes.run`.
- Produces: `CHECKS['code']`: the task text, a `Textarea(name='source', cls='code-editor', spellcheck='false')` filled with the stub, the visible tests, a results list (`pass`/`fail`/`error`/`timeout` and label or test text), the first error, "Run the tests ⌘↵", "Hint ⌥H", "I don't know", and "try N · K of M pass"; `POST /w/{jid}/{i}/run` returns the results part only (htmx swap of `#code-out`).

- [ ] **Step 1: Write the failing test**

```python
def test_code_check_in_the_browser(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why='your best way here: code'))
    card = cl.get(f'/w/{jid}/1/check').text
    assert 'code-editor' in card and 'def softmax(x, t=1.0):' in card and 'm = max(x)' not in card
    assert 'max(softmax([1000.0, 1001.0]))' not in card                            # a hidden test stays hidden
    r = cl.post(f'/w/{jid}/1/run', data=dict(source='def softmax(x\n')).text
    assert 'line 1' in r and 'try 1' in r                                          # a syntax error uses no try
    r = cl.post(f'/w/{jid}/1/run', data=dict(source=NAIVE)).text
    assert '2 of 3 pass' in r and 'It does not fail on large scores' in r and 'm = max(x)' not in r
    r = cl.post(f'/w/{jid}/1/run', data=dict(source=GOOD)).text
    assert 'Next idea' in r and lr.attempts('softmax', limit=1)[0].kind == 'code'
    assert lr.journey(jid).steps[1]['done']['outcome'] == 'fragile'                # a pass after a failing try is not clean
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run pytest tests/blocks/test_walk.py::test_code_check_in_the_browser -q`
Expected: FAIL: no `code-editor` in the card.

- [ ] **Step 3: Implement.** The check route makes the code task once (kept by `qid`, as Task 5) and keeps `stub`, `fname` and visible tests on the step (`code=dict(fname, stub, tests)`), so a reload shows the same task. `walk.js`: ⌘↵ in the editor submits; Tab inserts 4 spaces; Shift-Tab removes up to 4. The editor text keeps its value across a results swap (swap only `#code-out`). On close, the result part shows the lesson (when there is one) and "Next idea ⌥N".

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/blocks/test_walk.py -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add abhyasa/blocks/walk tests/blocks/test_walk.py
git commit -m "Add the code check to the walk: write a function in the page and run its tests"
```

---

### Task 9: Ways in: Add, the vault page, a topic walk, Today and review

**Files:**
- Modify: `abhyasa/blocks/add/app.py` (a second form "As a walk, in reading order": vault document, text or topic, posting to `/walk/new` by URL)
- Modify: `abhyasa/blocks/vault/ui.py:43` ("Learn as a walk" button posting to `/walk/new` with `shelf` and `ref`)
- Modify: `abhyasa/blocks/journeys/ui.py` ("Continue the walk" to `/w/{jid}` for `mode='walk'`)
- Modify: `abhyasa/blocks/history/app.py` (Continue goes to `/w/{jid}` for a sitting of a walk)
- Modify: `abhyasa/blocks/walk/app.py` (`/walk/new` takes `ref`+`shelf`, `text`+`title`, or `topic`; hooks `today_next`, `concept_more`, `lesson_extra`)
- Test: `tests/blocks/test_walk.py`, `tests/blocks/test_others.py`, `tests/blocks/test_vault.py`, `tests/blocks/test_history.py`

**Interfaces:**
- Consumes: Task 3 `journey_from_source`, `journey_from_text`, `walk_from_topic`, `walk_state`; `profile_text`; `with_step`; `placement`.
- Produces: the hooks `today_next` → "Continue the walk: {title} · idea {k} of {n}" linking `/w/{jid}`; `concept_more(c)` → the passage of `c` in each walk with a link to its step; `lesson_extra(r)` → "Read the passage again: p. {page}" linking `/w/{jid}/{i}`, when `r.concept` is a walk step.

- [ ] **Step 1: Write the failing tests**

```python
def test_ways_in(mk, walk_fake, lr):
    cl = mk()
    add = cl.get('/add').text
    assert 'As a walk, in reading order' in add and '/walk/new' in add
    did = add_paper(lr)
    assert 'Learn as a walk' in cl.get(f'/v/store/{did}').text
    jid = cl.post('/walk/new', data=dict(text=PAGES[1][1], title='My notes')).headers['hx-redirect'].split('/')[-1]
    assert lr.journey(jid).mode == 'walk' and lr.journey(jid).source is None
    walk_fake.rules['You plan a learning path'] = dict(title='Attention', subject='ml', steps=[dict(name='Ranking', statement='', slug='', why='Scores to places.', needs=[], ways=['code'])])
    tj = cl.post('/walk/new', data=dict(topic='how attention works')).headers['hx-redirect'].split('/')[-1]
    assert lr.journey(tj).mode == 'walk' and lr.journey(tj).steps[0]['read']['text'].startswith('Ranking orders')   # from the Notes source
    assert cl.post('/walk/new', data=dict()).text.startswith('<p')                 # nothing given: a plain message, no error page

def test_today_journeys_concept_and_review_links(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    assert f'href="/w/{jid}"' in cl.get('/').text and 'idea 1 of 3' in cl.get('/').text
    assert f'href="/w/{jid}"' in cl.get(f'/j/{jid}').text
    assert 'apply a softmax function' in cl.get('/c/softmax').text and f'/w/{jid}/1' in cl.get('/c/softmax').text
    lr.walk_step(jid, 1, check=dict(way='words', kind='short', depth=2, why=''))
    cl.get(f'/w/{jid}/1/check'); cl.post(f'/w/{jid}/1/answer', data=dict(answer='the rank is a position'))
    sid = cl.get('/start?focus=softmax', follow_redirects=False).headers['location'].split('/')[-1]
    cl.get(f'/s/{sid}'); r = cl.post(f'/s/{sid}/answer', data=dict(answer='rank'))
    assert 'Read the passage again: p. 4' in r.text and f'/w/{jid}/1' in r.text
    assert f'/w/{jid}' in cl.get('/learning').text                                 # Continue goes to the walk, not a plain session
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/blocks/test_walk.py -k "ways_in or links" -q`
Expected: FAIL: no "As a walk" on `/add`.

- [ ] **Step 3: Implement.** Each block keeps to its own `CAPS`; the links are route strings, not imports. `/walk/new` errors (no input, a doc that is not there, a model failure) return a short `P(..., cls='req-err')` as `journeys.new` does. A source with no concepts files no journey and says "The tutor found no ideas in this document."

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add abhyasa/blocks tests/blocks
git commit -m "Start a walk from Add, from a vault document or from a topic, and continue it from Today"
```

---

### Task 10: Docs and one look in a real browser

**Files:**
- Modify: `nbs/index.ipynb` (a short section "Learn a paper or a topic as a walk"; check for stale references)
- Modify: `README.md` (made by `nbdev-prepare` from `index.ipynb`), `CHANGELOG.md` (an entry under the next version), `docs/design-layers.md` (the walk page in the list of pages)
- Create: `tools/walk_look.py` (a script, not a test: it starts the app on a temp vault with `Fake`, opens `/w/{jid}/1` in Playwright's bundled Chromium, saves `design/screens/walk-code.png` and `walk-demo.png`)

**Interfaces:**
- Consumes: everything above.
- Produces: docs only, and two screens.

- [ ] **Step 1: Write the failing check.** `tools/walk_look.py` asserts, in the page: `#rail`, `#passage`, `#check .code-editor`, no horizontal scroll at 1280 px (`document.documentElement.scrollWidth <= 1280`), and that ⌥N focuses the next form.

- [ ] **Step 2: Run it to see it fail**

Run: `uv run python tools/walk_look.py`
Expected: PASS when Tasks 5-8 are right. A FAIL names the missing element, the scroll width or the key; fix it in `walk.css`, `ui.py` or `walk.js` before Step 3.

- [ ] **Step 3: Write the docs** in STE grade 9: what a walk is, the three checks, that learner code runs in a closed process with no network, and that reading never waits for a check. Run `uv run nbdev-prepare`, and look for stale references in `index.ipynb`.

- [ ] **Step 4: Run everything**

Run: `uv run nbdev-prepare && uv run pytest -q && uv run python tools/walk_look.py`
Expected: PASS; two new screens in `design/screens/`.

- [ ] **Step 5: Commit**

```bash
git add nbs/index.ipynb README.md CHANGELOG.md docs/design-layers.md tools/walk_look.py design/screens/walk-code.png design/screens/walk-demo.png
git commit -m "Document the guided walk and add screens of a code check and a demo check"
```
