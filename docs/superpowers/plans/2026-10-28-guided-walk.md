# The Guided Walk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a paper, a pasted text, a topic or a link (a paper, a docs site, a GitHub repo) into a walk: one idea at a time in reading order, each with its passage, figure, a short tutor note and one check (short answer, predict-first demo, or a code task run in the browser), all logged and reviewed as today. When a step needs an idea the learner does not have, the learner learns it beside the step in a side pane (a rabbit hole) and comes back to the same place. A walk on a library or a command-line tool (a tool walk) has short-answer and order checks here, and its code steps link to Leela, where code with the library runs. A trial on real material measures the result.

**Architecture:** The engine change comes first and is useful alone: `extract` keeps placement and modality fields, `method.py` gets the new ways, `allowed=` and `check_for`, and a walk is a journey whose steps carry `read` and `check`. A new engine module `walk.py` runs a step (note, short answer, code task, isolated run). A new hand-written block `blocks/walk` shows the plan and the steps and talks to other blocks only through hooks and links. Rabbit holes add engine functions in `journey.py` (`needs`, `pick_way_down`, `detour`, `back_from`), a split-pane host in `core/` (a page of the app in an `iframe`, its place kept in `?rh=`), and a block `blocks/detour` that adds to the step page only through hooks. A link is filed in the vault with vishalakshi's readers and made into one walk across the filed pages (`journey_from_sources`). abhyasa keeps a small code footprint: it runs only short stdlib exercises. For code with a library or a tool, a step links to Leela (`/learn?walk=…&step=…`), found through the address file that a running Leela writes; Leela reads the walk from the shared learning store.

**Tech Stack:** Python 3.12+, nbdev 3 on hatchling (engine notebooks in `nbs/`), FastHTML + htmx (blocks), vishalakshi vault, rupaka demos, `abhyasa.llm.Fake` for tests, pytest, Playwright bundled Chromium for the one browser check.

**Spec:** `docs/superpowers/specs/2026-10-28-guided-walk-design.md`

## Global Constraints

- Engine code is edited only in `nbs/*.ipynb`; then run `uv run nbdev-prepare` (hyphen). Never edit a generated `abhyasa/*.py` engine file (`store, model, llm, tutor, sources, voice, ground, rama, nb, demo, journey, profile, method, prompts, check, walk`).
- Web code (`abhyasa/blocks/`, `abhyasa/core/`, `abhyasa/app.py`) is written by hand and tested with `uv run pytest`.
- A block never imports another block. It adds to other pages only through hooks: `today_next`, `concept_more`, `lesson_extra` (and the others in `core/hooks.py`).
- `NAMES` in `abhyasa/blocks/__init__.py` gets `walk` after `demo` and before `today`, and `detour` after `walk` (Task 12).
- Prose (UI text, prompts, notebooks, docs, commit messages) is ASD-STE100 Simplified Technical English, US grade 9.
- Notebooks read as documents: an intro, short sections, a one-line lead before each code cell, small tests with a line on what each checks.
- Tests use `temp_learning()` and `abhyasa.llm.Fake`. Never open `~/.vishalakshi/vault.db` or `~/.config/abhyasa`.
- Browser checks: Playwright `p.chromium.launch(headless=True)`, no `executable_path`, one browser at a time, closed in a `finally`.
- New prompt text is registered with `prompts.register`: `extract`, `walk.note`, and `way.demo`, `way.order`, `way.playground`, `way.board`, `way.timeline` (by the loop in `method.py`).
- `TEXT_WAYS = ('code', 'maths', 'analogy', 'example', 'diagram', 'words')`; `WALK_WAYS = TEXT_WAYS + ('demo', 'order')`.
- Check kinds: `short`, `demo`, `order`, `code`. Depths: short 2 (floor < 2) else 3; code 4; demo and order 2, or 3 with a why.
- Learner code: `run_isolated(..., total=10., sandbox=True)`; 2 s per test; `python -I -B`; kill at 12 s; `RLIMIT_CPU` 11 s; `RLIMIT_FSIZE` 10 MB; no network. On macOS, also `/usr/bin/sandbox-exec` (when it exists) with a profile that denies the network and file writes outside the temp dir. Docs say "a closed process with no network"; never "a security sandbox".
- abhyasa installs no libraries for learners and runs only stdlib exercises: learner code runs with the app's own Python, and an exercise uses only the standard library. Code with a library, tool environments, code lookup and the agent tutor are Leela's (owner's decision, 28 Oct). abhyasa only links to Leela (Task 14).
- Leela: abhyasa never calls Leela. It reads Leela's address file (`$XDG_CONFIG_HOME/leela/serving.json`) and makes a link to a loopback `http` URL only. With no live Leela, it shows a muted line and the install link, never a broken link. Tests never read the owner's real address file (the `no_leela` fixture, Task 14).
- Fetching: the app uses the network only when the learner asks, outside the closed process: a link (Task 13: only the URL given and pages in its folder, at most `pages`, never more than `LINK_MAX = 20`). Tests never fetch: they pass a fake `read` to `file_link`, or patch the `Vault` reader methods with `monkeypatch`.
- `MAX_TRIES` stays 3. A syntax error uses no try.
- A passage is at most 600 chars and shows only when found word for word. A tutor note is 2 or 3 sentences, at most 60 words.
- Figures only from `lr.vault.assets()`, suffix in `.png .jpg .jpeg .gif .webp`.
- Keys (controller ruling): ⌥S start and "Next idea" (the app's "Press the main button" key), ⌥W hint, ⌘↵ send or run, 1-9 options, K keep. Side pane: ⌥B open beside, ⌥Z back to the paper, Esc close the pane. ⌥F ("Show the keyboard shortcuts"), ⌥D (dictate), ⌥G (strengths) and ⌥E (show me a demo) are taken: never bind them. Read `abhyasa/core/keys.py` before you choose a key; the task that binds a new key adds it to `KEYS` (`tests/test_keys.py` checks the table against the js). Where Tasks 5, 8 and the mockups say ⌥N, ⌥H or ⌥F for the walk, use ⌥S and ⌥W.
- No new runtime dependency and no new vendored script.
- Commit messages are one plain STE line. No AI credit. No Co-Authored-By line.

## Review Focus

1. **A long paper** (15 pages, over 40 000 chars): the walk must have steps from the last sections too, not stop where `Vault.document` cuts at 40 000 chars. Test: `long_paper_reaches_the_end` in Task 1.
2. **A model that paraphrases the quote or names a figure file that is not there**: the step shows the concept statement marked "In the tutor's words" and no broken image, never a passage that is not in the paper. Tests: `quote_not_in_text_gives_no_passage` in Task 1 and `step_without_passage_or_figure` in Task 5.
3. **Reload, Back or a second tab on a step with an open check**: the same question comes back, no second question is made, no try is logged twice, and a double press of "Next idea" moves one step only. Test: `reload_keeps_one_question_and_next_is_idempotent` in Task 5.
4. **Learner code that hangs at the top level, has a syntax error, opens a socket, or prints a fake pass line and exits**: no hang over 12 s, no try used for the syntax error, the socket fails, and the fake line does not pass. Test: `hostile_code_does_not_pass_or_hang` in Task 7.
5. **A demo that the model cannot make, or that takes long**: the step does not stay on "making a demo"; it falls back to a short answer, and "Next idea" works all the time. Test: `demo_failure_falls_back_to_short_answer` in Task 6.
6. **A pane URL that points off the app** (`?rh=https://…`, `//host`, `/\host`, `javascript:…`, or a pane message from another origin): no pane, no `iframe`, and `rh` does not change. Tests: `test_pane_url_is_local_only` in Task 11, `test_needs_line_and_side_walk_beside` in Task 12, and the off-app checks in `tools/walk_look.py` (Task 16).
7. **A crawl that pulls unrelated pages** (a docs site that links to its blog, its API pages, another product or another host): the crawl is told the folder of the URL and the page cap, and the walk has steps only from pages in that folder, at most the cap. Test: `crawl_stays_under_the_link` in Task 13.
8. **A stale or strange Leela address file** (the Leela that wrote it has stopped, or its URL is not on this computer): no link to `/learn`; the line says "Open this in Leela for code and tools" with the install link. Test: `test_leela_link_is_local_and_live` in Task 14.

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

### Task 10: Rabbit holes in the engine: needs, the way down, side walks

Spec 6.10. Design: `abhyasa-designs/rabbit-hole/design.md` ("What opens", "What is logged", "Reusable pieces").

**Files:**
- Modify: `nbs/11_journey.ipynb` (new section "Rabbit holes" after "Walks")
- Modify: `nbs/15_walk.ipynb` (`#i13` `step_meta`; this extends Task 4)
- Generated: `abhyasa/journey.py`, `abhyasa/walk.py`

**Interfaces:**
- Consumes: Task 3 `journey_from_source`, `walk_from_topic`, `short_check`, `Learning.walk_step`, `_new_id`; Task 4 `step_meta`; `name_gaps`, `_index`, `Learning.put_journey`, `Learning.add_gap`.
- Produces:
  - `MAX_DEPTH = 2`; `CHAIN = 4`; `READY = 3` (the floor at which a need is met).
  - `needs(lr:Learning, slug:str, by:dict=None) -> L` — the prereqs, then the gaps, of `slug`, each `AttrDict(slug, name, floor, why='prereq'|'gap', ok:bool)`; `ok` is floor `READY` or more.
  - `pick_way_down(lr:Learning, slug:str, by:dict=None) -> AttrDict(how='primer'|'walk'|'session', why:str, chain:list[str])` — `chain` is the unready prereqs of `slug`, deepest first, then `slug`.
  - `detour(lr:Learning, ask, slug:str, parent:dict, how:str='walk', sources=None) -> AttrDict` — a saved walk journey (`mode='walk'`, `started` set) with `parent` and `depth`. For `primer` and `walk`, `depth` is the parent's depth plus 1, and `ValueError('too deep: …')` past `MAX_DEPTH`. For `session`, `depth=0`. A `primer` is one step on `slug` with `short_check`.
  - `trail(lr:Learning, jid:str) -> L` — `AttrDict(walk, title, step)` from the root walk to `jid`.
  - `back_from(lr:Learning, jid:str) -> AttrDict|None` — add `{walk, slug, outcome, at}` to the parent step's `detours` once; return the parent journey (None when `jid` has no parent).
  - `look_up(lr:Learning, ask, term:str, at:str='', sources=None) -> AttrDict(slug, name, statement)` — by name or alias, else `name_gaps` on the concept of step `at` (`'<jid>/<i>'`).
  - `step_meta(j, i)` adds `from='/'.join(map(str, j.parent.values()))` when `j` has a `parent`.

- [ ] **Step 1: Write the failing tests** (in the new section, after the shared-data cell; each with a one-line lead)

```python
lr = temp_learning(); did = add_paper(lr)
j = journey_from_source(lr, Fake({'Return JSON: {"concepts"': EXTRACT_REPLY}), did)
lr.put('Derivatives and gradients', 'The slope of a function at a point, one for each input.', 'ml', slug='gradients')
lr.update('scaling-by-the-root-of-dk', prereqs=['softmax', 'gradients']); lr.update('softmax', floor=3)
test_eq([(n.slug, n.ok) for n in needs(lr, 'scaling-by-the-root-of-dk')], [('softmax', True), ('gradients', False)])
test_eq(pick_way_down(lr, 'gradients').how, 'primer')          # no prereqs of its own: a primer is enough
lr.put('Slope of a line', '', 'ml', slug='slope'); lr.update('gradients', prereqs=['slope'])
w = pick_way_down(lr, 'gradients')
test_eq((w.how, w.chain), ('walk', ['slope', 'gradients']))     # a short chain: a side walk, deepest first
```

```python
d = detour(lr, Fake({}), 'gradients', dict(walk=j.id, step=2))
test_eq((d.mode, d.parent, d.depth, [s['slug'] for s in d.steps]), ('walk', dict(walk=j.id, step=2), 1, ['slope', 'gradients']))
test_eq(step_meta(d, 0)['from'], f'{j.id}/2')                  # each attempt links to the step that opened it
assert 'from' not in step_meta(j, 0)                            # a walk with no parent has no `from`
test_eq([t.walk for t in trail(lr, d.id)], [j.id, d.id])
d2 = detour(lr, Fake({}), 'slope', dict(walk=d.id, step=0), how='primer')
test_eq((d2.depth, len(d2.steps), d2.steps[0]['check']['depth']), (2, 1, 2))
test_fail(lambda: detour(lr, Fake({}), 'softmax', dict(walk=d2.id, step=0), how='primer'), contains='deep')
test_eq(detour(lr, Fake({}), 'softmax', dict(walk=d2.id, step=0), how='session').depth, 0)   # past the limit: its own session
```

```python
lr.walk_step(d.id, 1, done=dict(outcome='solid', aid='a1', at=1.))
p = back_from(lr, d.id); back_from(lr, d.id)
test_eq(p.id, j.id)
test_eq([(x['walk'], x['slug'], x['outcome']) for x in lr.journey(j.id).steps[2]['detours']], [(d.id, 'gradients', 'solid')])   # once
test_eq(look_up(lr, Fake({}), 'gradients').slug, 'gradients')
test_eq(look_up(lr, Fake({}), 'Derivatives and gradients').slug, 'gradients')                  # by name too
g = look_up(lr, Fake({'The idea: vanishing gradients': dict(name='Vanishing gradients', statement='Gradients near 0 stop the weights.')}),
            'vanishing gradients', at=f'{j.id}/2')
assert g.name == 'Vanishing gradients' and g.slug in lr.concept('scaling-by-the-root-of-dk').gaps   # a new term is filed as a gap of the step
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run nbdev-test --path nbs/11_journey.ipynb`
Expected: FAIL with `NameError: name 'needs' is not defined`.

- [ ] **Step 3: Implement** in `nbs/11_journey.ipynb`.
  - `pick_way_down`: `primer` when the concept has floor 1 or 2, or no prereqs of its own; `walk` when the chain has `CHAIN` ideas or fewer; else `session`. `why` is one plain line ("it builds on two ideas you have not met yet").
  - `detour` for `walk`: one step for each slug of the chain. With no chain on the shelf, `walk_from_topic` with the goal "<name>: the basics, enough to read <parent idea>", cut to `CHAIN` steps. Each step gets `read` and `check` as Task 3 makes them.
  - The depth of a parent is `lr.journey(parent['walk']).get('depth', 0)`. A parent with no `walk` key (Leela's `{notebook, cell}`) has depth 0.
  - `back_from`: the outcome is the `done.outcome` of the step on the target slug (the last step), or `'skipped'`.
  - In `nbs/15_walk.ipynb`, `step_meta` adds `from` only when the walk has a `parent`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run nbdev-prepare && uv run nbdev-test --path nbs/11_journey.ipynb && uv run nbdev-test --path nbs/15_walk.ipynb && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add nbs/11_journey.ipynb nbs/15_walk.ipynb abhyasa/journey.py abhyasa/walk.py abhyasa/_modidx.py
git commit -m "Find the ideas a step needs, and make a short side walk that links back to the step"
```

---

### Task 11: The split pane in core

Spec 6.10 ("The pane and its URL state", "A reusable host"). Follow `vedicreader/static/js/pane.js` for the grip and the width.

**Files:**
- Create: `abhyasa/core/pane.py`, `abhyasa/core/pane.js`, `abhyasa/core/pane.css`
- Modify: `abhyasa/core/ui.py` (`Page(..., pane=False)`, link the pane assets), `abhyasa/core/core.js` (Esc), `abhyasa/core/__init__.py`
- Modify: `abhyasa/core/keys.py` (two rows in `KEYS`)
- Test: `tests/test_pane.py`

**Interfaces:**
- `is_local(url) -> bool` — a path in this app: a string that starts with one `/`, with no `//` or `\` at the start, no scheme and no control character.
- `pane_url(url:str) -> str|None` — `url` with `pane=1` added to its query, only when `is_local(url)`; else None.
- `pane_link(label, href:str, title:str='', cls:str='pane-link', **kw) -> FT` — `A(label, href=href, target='_blank', data_pane=pane_url(href), data_title=title)`.
- `PaneHost(url:str|None, title:str='', trail=()) -> FT|str` — `aside#rh-pane`: the bar (the trail, "Own session ↗" linking `url` in a new tab, ×), the grip (`role="separator"`, `aria-orientation="vertical"`, `tabindex="0"`), and an `iframe` with `src=pane_url(url)`. `''` when `url` is not local.
- `Page(title, *c, on='', wide=False, extra=(), crumbs=(), pane=False)` — with `pane=True`, or when the request has `pane=1` (a request-scoped flag set in core, so no route changes): no nav, no crumbs, `html.in-pane`.
- `KEYS` gets `('Side pane', '⌥Z', 'Back to the paper: close the side pane')` and `('Side pane', 'esc', 'Close the side pane')`.
- JS: `abhyasaPane.open(url, title)`, `abhyasaPane.close()`. Messages from the pane: `rh:at {url, title, trail}`, `rh:open {url}`, `rh:done {slug, outcome}`, `rh:close`.

- [ ] **Step 1: Write the failing tests**

```python
from fasthtml.common import to_xml
from abhyasa.core.pane import is_local, pane_url, pane_link, PaneHost
from abhyasa.core.keys import KEYS

def test_pane_url_is_local_only():
    assert pane_url('/w/g-1a2b/0') == '/w/g-1a2b/0?pane=1' and pane_url('/w/g?x=1') == '/w/g?x=1&pane=1'
    for bad in ('https://evil.example/x', '//evil.example', '/\\evil.example', 'javascript:alert(1)', 'w/g', '', None):
        assert not is_local(bad) and pane_url(bad) is None, bad

def test_pane_link_is_a_real_link():
    h = to_xml(pane_link('Derivatives', '/w/g-1a2b/0', 'Side walk'))
    assert 'href="/w/g-1a2b/0"' in h and 'data-pane="/w/g-1a2b/0?pane=1"' in h and 'target="_blank"' in h

def test_host_draws_the_pane_or_nothing():
    h = to_xml(PaneHost('/w/g-1a2b/0', 'Derivatives'))
    assert 'id="rh-pane"' in h and 'src="/w/g-1a2b/0?pane=1"' in h and 'role="separator"' in h
    assert PaneHost(None) == '' and PaneHost('https://evil.example/') == '' and PaneHost('/\\evil.example') == ''

def test_page_in_a_pane_has_no_nav(mk):
    cl = mk()
    assert '<nav' in cl.get('/').text
    t = cl.get('/?pane=1').text
    assert '<nav' not in t and 'in-pane' in t

def test_pane_keys_are_in_the_table():
    assert ('Side pane', '⌥Z', 'Back to the paper: close the side pane') in KEYS
    assert ('Side pane', 'esc', 'Close the side pane') in KEYS
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/test_pane.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'abhyasa.core.pane'`.

- [ ] **Step 3: Implement.**
  - `pane.js`: at 1100 px or more, `open` sets the `iframe` src and `history.pushState` with `?rh=`; under 1100 px, it goes to the page itself in the same tab. The grip: drag, arrow keys (24 px, Shift 96 px), double-click resets, bounds 380 px to the smaller of 70% of the window and the window less 520 px, width in `localStorage` (`rh-w`). The pane is `position: fixed` and the body gets only `padding-right`, so the page is not drawn again.
  - Messages: take one only when `e.origin === location.origin` and `e.source === frame.contentWindow`. On `rh:at`, `replaceState` with the new `rh` only when the url passes the same local test as `is_local`. `rh:open` loads the url in the same pane. `rh:close` closes.
  - Keys: ⌥Z closes one level and puts the focus on `#check` of the main page; bind it in the form that `tests/test_keys.py` reads (`e.code !== 'KeyZ'`). Esc closes the pane before `core.js` goes up a crumb, when the focus is not in a text box. In a page with `html.in-pane`, `core.js` sends `rh:close` to the parent on Esc instead of going up a crumb, and the page sends `rh:at` on load.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/test_pane.py tests/test_keys.py -q && uv run pytest -q`
Expected: PASS (the keys test finds `KeyZ` in `core/pane.js`).

- [ ] **Step 5: Commit**

```bash
git add abhyasa/core tests/test_pane.py
git commit -m "Add the side pane: a page beside the page, with its place in the URL"
```

---

### Task 12: The detour block: the offer, the side walk beside the step, and the way back

Spec 6.10. Mockups `rabbit-hole/shots/r1-offer.png`, `r2-pane.png`, `r3-return.png` (read ⌥B, ⌥Z and ⌥S where the shots show ⌥D, ⌥G and ⌥F).

**Files:**
- Create: `abhyasa/blocks/detour/{__init__.py, cfg.py, ui.py, app.py, detour.css, detour.js}`
- Modify: `abhyasa/blocks/__init__.py` (`NAMES`: `detour` after `walk`), `abhyasa/core/hooks.py` (name `step_needs`, `check_after`, `walk_end`, `term_lookup` in the docstring), `abhyasa/core/keys.py` (one row)
- Modify: `abhyasa/blocks/walk/{app.py, ui.py, walk.js}` (this extends Task 5: run the four hooks; draw `PaneHost` from `rh`; the side walk foot "← Back to the paper: idea k of n ⌥Z"; the draft in `sessionStorage` by `qid`; open a sitting when a side walk step has none)
- Modify: `abhyasa/blocks/journeys/ui.py` (a side walk shows under its parent, in "Side walks", not as its own line)
- Test: `tests/blocks/test_detour.py`

**Interfaces:**
- Consumes: Task 10 `needs`, `pick_way_down`, `detour`, `trail`, `back_from`, `look_up`, `MAX_DEPTH`; Task 11 `PaneHost`, `pane_link`; Task 5 `Routes` strings (by value, not by import).
- Produces:
  - `CAPS = ('learning', 'ask', 'sources')`; `Routes`: `open='/rh/open'`, `term='/rh/term'`, `back='/rh/back/{sid}'`.
  - `POST /rh/open` (`slug`, `at='<jid>/<i>'`, `how`) → JSON `{url, title, how}`, with `url='/w/{sid}/0'`. Past `MAX_DEPTH`, it makes `how='session'`.
  - `GET /rh/term?t=…&at=…` → the offer card for a selected term (three choices, the pick marked).
  - `POST /rh/back/{sid}` → `back_from`, then 303 to the parent step.
  - Hooks: `step_needs(j, i, c)` (the needs line, and the strip "Back on the paper …" while the newest detour of the step is less than 10 minutes old), `check_after(j, i, q)` (the line "Your answer points at: …" from `q.gaps`), `walk_end(j)` (the done page of a side walk sends `rh:done`), `term_lookup(term, at)`; and `today_next` ("Unfinished side walk: …"), `lesson_extra` ("You first met this on the way to: …").
  - `KEYS` gets `('Walk', '⌥B', 'Open beside: learn a missing idea in the side pane')`.

- [ ] **Step 1: Write the failing tests**

```python
from walk_data import *

def needs_gradients(lr):
    lr.put('Derivatives and gradients', 'The slope of a function at a point, one for each input.', 'ml', slug='gradients')
    lr.update('scaling-by-the-root-of-dk', prereqs=['softmax', 'gradients'])

def test_needs_line_and_side_walk_beside(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    page = cl.get(f'/w/{jid}/2').text
    assert 'This needs' in page and 'you have not learned it' in page and '⌥B' in page
    r = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()
    sid = r['url'].split('/')[2]
    assert lr.journey(sid).parent == dict(walk=jid, step=2) and r['title'].startswith('Derivatives')
    pane = cl.get(r['url'] + '?pane=1').text
    assert '<nav' not in pane and 'Back to the paper: idea 3 of 3' in pane and '⌥Z' in pane
    assert f'src="/w/{sid}/0?pane=1"' in cl.get(f'/w/{jid}/2?rh=/w/{sid}/0').text        # a reload keeps the pane open
    for bad in ('https://evil.example/', '//evil.example/', '/\\evil.example/'):
        assert 'rh-pane' not in cl.get(f'/w/{jid}/2', params=dict(rh=bad)).text         # no pane for a URL off the app
    assert 'Unfinished side walk' in cl.get('/').text

def test_side_walk_logs_from_and_comes_back(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    sid = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url'].split('/')[2]
    cl.get(f'/w/{sid}/0/check'); cl.post(f'/w/{sid}/0/answer', data=dict(answer='the slope', confidence=70))
    assert lr.attempts('gradients', limit=1)[0]['from'] == f'{jid}/2'
    r = cl.post(f'/rh/back/{sid}', follow_redirects=False)
    assert r.headers['location'] == f'/w/{jid}/2'
    page = cl.get(f'/w/{jid}/2').text
    assert 'Back on the paper' in page and 'on the way' in page
    assert sid not in cl.get('/journeys').text.split('Side walks')[0]                    # listed under its parent only
    s2 = cl.get('/start?focus=gradients', follow_redirects=False).headers['location'].split('/')[-1]
    cl.get(f'/s/{s2}')
    assert 'You first met this on the way to' in cl.post(f'/s/{s2}/answer', data=dict(answer='slope')).text

def test_a_miss_that_names_a_gap_offers_it(mk, walk_fake, lr):
    walk_fake.rules['You grade one answer'] = dict(correct=False, grade=2, first_error='No slope.', misconception='',
                                                   feedback='Think of the slope.', gaps=['gradients'])
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    lr.walk_step(jid, 2, check=dict(way='words', kind='short', depth=2, why=''))
    cl.get(f'/w/{jid}/2/check')
    r = cl.post(f'/w/{jid}/2/answer', data=dict(answer='it is faster', confidence=70)).text
    assert 'Your answer points at' in r and '⌥B' in r

def test_term_offer_and_depth_limit(mk, walk_fake, lr):
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start'); needs_gradients(lr)
    t = cl.get('/rh/term', params=dict(t='gradients', at=f'{jid}/2')).text
    assert 'A quick primer' in t and 'A short side walk' in t and 'Its own session' in t
    a = cl.post('/rh/open', data=dict(slug='gradients', at=f'{jid}/2', how='primer')).json()['url'].split('/')[2]
    b = cl.post('/rh/open', data=dict(slug='softmax', at=f'{a}/0', how='primer')).json()['url'].split('/')[2]
    r = cl.post('/rh/open', data=dict(slug='softmax', at=f'{b}/0', how='primer')).json()
    assert r['how'] == 'session'                                                          # past the limit: only its own session
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/blocks/test_detour.py -q`
Expected: FAIL with 404 on `/rh/open`.

- [ ] **Step 3: Implement.**
  - The block never imports the walk block. It adds to the step only through the hooks, and links by route strings.
  - The offer is one sunken card with three choices (1, 2, 3) and the pick from `pick_way_down`; at the limit, only "Its own session ↗". Esc closes it.
  - `detour.js`: ⌥B opens the offer for the first unmet need, or for the selected text in `#passage` (a small tool "I don't know this ⌥B" next to the selection). Bind ⌥B in the form `tests/test_keys.py` reads. Choice 1 or 2 calls `abhyasaPane.open(url, title)`; choice 3 opens the url in a new tab.
  - The walk block: the step route reads `rh` and draws `PaneHost(rh, …)` (which draws nothing for a URL off the app). A side walk step shows the foot "← Back to the paper: idea k of n ⌥Z" (k and n from `trail`) and a held note on the parent's check card ("Held while you learn …. Your draft is kept."). The parent saves the draft in `sessionStorage` by `qid` and puts it back on load.
  - On `rh:done`, the parent posts `/rh/back/{sid}`, closes the pane and puts the focus in the answer box.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/blocks/test_detour.py tests/test_blocks.py tests/test_keys.py -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add abhyasa/blocks abhyasa/core/hooks.py abhyasa/core/keys.py tests/blocks/test_detour.py
git commit -m "Learn a missing idea beside the step in a side walk, and come back to the same place"
```

---

### Task 13: A walk from a link: a paper, a docs site or a repo

Spec 6.11. Read the signatures in `.venv/lib/python3.13/site-packages/vishalakshi/acquire.py` (`Vault.url`, `crawl`, `arxiv`, `pdf`, `github`, `gh_file`, `grab`) and `fossick.what_is`.

**Files:**
- Modify: `nbs/04_sources.ipynb` (new section "From a link": `LINK_MAX`, `link_folder`, `in_scope`, `link_sel`, `reading_order`, `file_link`)
- Modify: `nbs/11_journey.ipynb` (`journey_from_sources`; split `_walk` into `_steps` and the save, so that the Task 3 tests still pass; this extends Task 3)
- Modify: `abhyasa/blocks/walk/{cfg.py, app.py, ui.py}` (`/walk/new` takes `url` and `pages`; `Routes.job = '/walk/job'`)
- Modify: `abhyasa/blocks/add/app.py` (a "From a link" field and a page cap in the walk form of Task 9)
- Test: `tests/blocks/test_walk.py`
- Generated: `abhyasa/sources.py`, `abhyasa/journey.py`

**Interfaces:**
- Consumes: Task 1 `doc_pages`, `from_vault`, `placement`; Task 3 `_walk`, `_check`, `_new_id`; `Vault.route`, `Vault.doc`, the vishalakshi readers.
- Produces:
  - `LINK_MAX = 20`
  - `link_folder(url:str) -> str` — the scheme, host and folder: `'https://docs.claude.com/en/docs/claude-code/'` for `'https://docs.claude.com/en/docs/claude-code/overview'`; `'https://ai.pydantic.dev/'` for `'https://ai.pydantic.dev'`.
  - `in_scope(url:str, start:str) -> bool` — `url` (without query and fragment) starts with `link_folder(start)`.
  - `link_sel(start:str) -> str` — the CSS selector of links into the folder: `a[href^="/en/docs/claude-code/"], a[href^="https://docs.claude.com/en/docs/claude-code/"]`.
  - `reading_order(docs:list, start_text:str) -> L` — the start page, then the pages in the order of their first link in `start_text`, then the rest in their given order.
  - `file_link(lr:Learning, url:str, max_pages:int=8, read=None) -> L` — `AttrDict(shelf, doc_id, title, url)` for each filed page in folder, in reading order, at most `min(max_pages, LINK_MAX)`. `read(how, target, **kw) -> list[dict]` names the `Vault` method (`arxiv`, `pdf`, `github`, `gh_file`, `crawl`, `url`); the default calls it on `lr.vault.route(kind)`, and `shelf` is that shelf's `name`. Raise `ValueError('abhyasa could not read this link.')` when no page is filed.
  - `journey_from_sources(lr:Learning, ask, docs:list, title:str='', subject:str='', **extra) -> AttrDict` — one walk across `docs` (spec 6.11); `source=dict(url=docs[0].url, docs=[…])`; `extra` (for example `tool`, `packages`) goes into the journey.
  - `/walk/new` with `url` (and `pages`, default 8) starts a pool job and returns a pending card (class `pending`) that polls `GET /walk/job?url=…` every 2 s; that route returns the pending card, an `HX-Redirect` to `/w/{jid}`, or `P(…, cls='req-err')`.

- [ ] **Step 1: Write the failing tests**

```python
# nbs/04_sources.ipynb, section "From a link"
START = 'https://docs.example.dev/en/docs/tool/overview'
test_eq(link_folder(START), 'https://docs.example.dev/en/docs/tool/')
test_eq(link_folder('https://ai.pydantic.dev'), 'https://ai.pydantic.dev/')
assert in_scope('https://docs.example.dev/en/docs/tool/setup#a', START) and not in_scope('https://docs.example.dev/en/api/x', START)
assert not in_scope('https://evil.example/en/docs/tool/x', START) and not in_scope('https://docs.example.dev.evil.example/en/docs/tool/', START)

SITE = {START: '# Overview\n\nSee [Setup](/en/docs/tool/setup) and [Hooks](/en/docs/tool/hooks).',
        'https://docs.example.dev/en/docs/tool/hooks': '# Hooks\n\nA hook runs a command at a set point.',
        'https://docs.example.dev/en/docs/tool/setup': '# Setup\n\nInstall the tool with one command.',
        'https://docs.example.dev/blog/news': '# News\n\nWe have a new logo.'}
calls = []
def fake_read(lr):
    "File every page of SITE in crawl order, and keep the call."
    def read(how, target, **kw):
        calls.append((how, target, kw))
        return [lr.vault.add(md, md.split('\n')[0][2:], source=u, kind='web', meta=dict(url=u)) for u, md in SITE.items()]
    return read
```

```python
# crawl_stays_under_the_link: the crawl gets the folder and the cap, and a page outside the folder is not used
lr = temp_learning()
docs = file_link(lr, START, max_pages=500, read=fake_read(lr))
test_eq((calls[0][0], calls[0][2]['max_pages']), ('crawl', LINK_MAX))
assert 'a[href^="/en/docs/tool/"]' in calls[0][2]['follow_sel']
test_eq([d.title for d in docs], ['Overview', 'Setup', 'Hooks'])        # the start page, then its links in order; no blog page
calls.clear(); file_link(lr, START, max_pages=1, read=fake_read(lr)); test_eq(calls[0][0], 'url')
calls.clear(); file_link(lr, '1706.03762', read=fake_read(lr)); test_eq(calls[0][0], 'arxiv')
test_fail(lambda: file_link(temp_learning(), START, read=lambda how, target, **kw: []), contains='could not read')
```

```python
# nbs/11_journey.ipynb: one walk across two pages
lr = temp_learning()
a = lr.vault.add(PAGES[0][1], 'Introduction', source='https://example.dev/docs/intro', kind='web')
b = lr.vault.add([(0, PAGES[1][1]), (1, PAGES[2][1])], 'Attention', source='https://example.dev/docs/attention', kind='web')
docs = [AttrDict(shelf='store', doc_id=d['doc_id'], title=t, url=u) for d, t, u in
        [(a, 'Introduction', 'https://example.dev/docs/intro'), (b, 'Attention', 'https://example.dev/docs/attention')]]
ask = Fake({'Return JSON: {"concepts"': EXTRACT_REPLY})
j = journey_from_sources(lr, ask, docs, 'Attention docs')
test_eq([s['slug'] for s in j.steps], ['sequential-computation', 'softmax', 'scaling-by-the-root-of-dk'])
test_eq([s['read']['doc_id'] for s in j.steps], [a['doc_id'], b['doc_id'], b['doc_id']])   # softmax is named in both; its step is where its passage is
assert j.steps[1]['read']['text'].startswith('apply a softmax function') and j.source['url'] == 'https://example.dev/docs/intro'
test_eq(journey_from_sources(lr, ask, docs, 'Tool docs', tool='cli').tool, 'cli')         # extra fields go on the journey
```

```python
# tests/blocks/test_walk.py
from fastcore.utils import L
from vishalakshi.core import Vault

def test_walk_from_a_link(mk, walk_fake, lr, monkeypatch):
    def crawl(self, start_url, max_pages=10, sel=None, **kw):
        return L([self.add(PAGES, 'Attention docs', source=start_url, kind='web', meta=dict(url=start_url))])
    monkeypatch.setattr(Vault, 'crawl', crawl)
    cl = mk(); u = 'https://docs.example.dev/attention/'
    assert 'From a link' in cl.get('/add').text
    r = cl.post('/walk/new', data=dict(url=u, pages=3)).text
    assert 'pending' in r and '/walk/job' in r                                     # a link walk is made as a job
    jid = wait_for(lambda: (cl.get('/walk/job', params=dict(url=u)).headers.get('hx-redirect') or '').split('/')[-1] or None, secs=10)
    assert lr.journey(jid).source['url'] == u and len(lr.journey(jid).steps) == 3
    monkeypatch.setattr(Vault, 'crawl', lambda self, *a, **kw: L())
    cl.post('/walk/new', data=dict(url='https://docs.example.dev/empty/'))
    t = wait_for(lambda: (t := cl.get('/walk/job', params=dict(url='https://docs.example.dev/empty/')).text) if 'pending' not in t else None, secs=10)
    assert 'could not read this link' in t
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run nbdev-test --path nbs/04_sources.ipynb; uv run nbdev-test --path nbs/11_journey.ipynb; uv run pytest tests/blocks/test_walk.py -k link -q`
Expected: FAIL with `NameError: name 'link_folder' is not defined`, `NameError: name 'journey_from_sources' is not defined`, and no "From a link" on `/add`.

- [ ] **Step 3: Implement.**
  - `file_link` picks the reader from `fossick.what_is(url)`: `arxiv` → `arxiv`; `pdf` → `pdf`; `github` → `github` (then keep its prose docs, README first, up to the cap); `ghfile` → `gh_file`; any other → `crawl(url, max_pages=cap, follow_sel=link_sel(url))`, or `url` when the cap is 1. It reads each filed doc back with `Vault.doc` for its `title` and `source`, drops the docs that are not `in_scope` (web cases only), orders them with `reading_order` (the start text from `doc_pages`), and cuts to the cap.
  - `journey_from_sources`: `from_vault` on each doc; a slug goes to the first doc where its placement has a passage, else to its first doc; steps in doc order, then placement order; one `_steps` helper shared with `_walk`.
  - The block: the job key is the URL; the job runs `file_link` then `journey_from_sources` with `ask` for the `extract` task; it never runs inside a request. The Add walk form gets "From a link" (a URL field) and "Pages to read" (1 to 20, default 8). The plan page of a link walk names each page title once, as a section group.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run nbdev-prepare && uv run nbdev-test --path nbs/04_sources.ipynb && uv run nbdev-test --path nbs/11_journey.ipynb && uv run pytest -q`
Expected: PASS, with the Task 1 and Task 3 tests unchanged.

- [ ] **Step 5: Commit**

```bash
git add nbs/04_sources.ipynb nbs/11_journey.ipynb abhyasa/sources.py abhyasa/journey.py abhyasa/_modidx.py abhyasa/blocks/walk abhyasa/blocks/add tests/blocks/test_walk.py
git commit -m "Make a walk from a link: file a paper, a docs site or a repo, then walk its pages in reading order"
```

---

### Task 14: Open in Leela: a link for code and tools

Spec 6.12, and the owner's decision of 28 Oct: "abhyasa can just have minimal code footprint and we can have a link to open leela for full fledged in depth learning." abhyasa keeps the small stdlib code check of Tasks 7-8. Code with a library, tool environments, code lookup and the agent tutor are in Leela (`abhyasa-designs/leela-reuse.md`, section 6). This task adds only the link, the `kind='tool'` marker and the rule that a tool walk gets no code check in abhyasa.

Facts from the Leela repo (read only): `serve_ide` writes `~/.config/leela/serving.json` (`$XDG_CONFIG_HOME/leela/serving.json`) with `host`, `port`, `pid` and `url` while it answers, and removes it when it stops (`leela/core/projects.py`, `now_serving`, `served`). Leela's default port is 5010, but Leela.app takes the first free port in 5010-5019, so the file, not a fixed port, gives the address. Leela.app registers no URL scheme (it answers only the `odoc` Apple Event), so this task makes no `leela://` link. Leela has no `/learn` route yet; Leela builds it to the contract below.

**Files:**
- Modify: `nbs/11_journey.ipynb` (new section "Open in Leela": `LEELA_ROUTE`, `HANDOFF_CASES`, `handoff`, `read_handoff`; `TOOL_WAYS`; `_check(lr, c, kind='')`; the makers take `kind` and set `leela` on a step)
- Create: `abhyasa/core/leela.py` (`LEELA_INSTALL`, `leela_address`, `leela_base`, `leela_link`, `leela_line`)
- Modify: `abhyasa/core/cfg.py` (`cfg.leela`)
- Modify: `abhyasa/blocks/walk/{app.py, ui.py, walk.css}` (`/walk/new` takes `tool`; the Leela line on the plan page of a tool walk, on a step with `leela`, under the code card, and on the concept page through `concept_more`; the plan refuses `code` on a tool walk)
- Modify: `abhyasa/blocks/add/app.py` (a tick box in the walk form)
- Modify: `tests/walk_data.py` (`leela_file`), `tests/conftest.py` (an `autouse` fixture `no_leela`)
- Test: `tests/test_leela.py`, `tests/blocks/test_walk.py`
- Generated: `abhyasa/journey.py`

**Interfaces:**
- Consumes: Task 3 `_check`, `_walk`, the makers; Task 13 `journey_from_sources(**extra)`, `_steps`; Task 5 the plan page and the step page; Task 8 `CHECKS['code']`; Task 9 the `concept_more` hook and the walk form on Add.
- Produces:
  - `LEELA_ROUTE = '/learn'`.
  - `handoff(jid:str='', i:int|None=None, topic:str='') -> str` — the path and query that Leela opens: `'/learn?walk=attention-ab12&step=3'`. Keys in this order, each only when given: `walk`, `step`, `topic` (`urllib.parse.urlencode`). `ValueError('nothing to open')` when `jid` and `topic` are both empty.
  - `read_handoff(query:str) -> AttrDict(walk:str, step:int|None, topic:str)` — the other side of `handoff`, for Leela. `ValueError` names the bad key: `walk` must match `^[a-z0-9-]{1,48}$` (the form of `_new_id`), `step` must be a whole number from 0, `topic` is at most 200 chars; `ValueError('nothing to open')` with no `walk` and no `topic`.
  - `HANDOFF_CASES: list[tuple[dict, str]]` — the shared cases that both test suites run (below).
  - `TOOL_WAYS = tuple(w for w in WALK_WAYS if w != 'code')`.
  - `_check(lr, c, kind:str='') -> AttrDict` — for `kind='tool'`, the candidates are the concept's ways in `TOOL_WAYS`, else `('words',)`; so a tool walk never gets a `code` check.
  - `journey_from_source(..., kind:str='')`, `journey_from_text(..., kind:str='')`, `walk_from_topic(..., kind:str='')`, `journey_from_sources(..., kind:str='', **extra)` — `kind` goes on the journey (`''` or `'tool'`). On a tool walk, a step whose concept has `code` in its ways gets `leela=True`.
  - `cfg.leela = os.getenv('ABHYASA_LEELA', '')` — a base URL that the owner sets only when Leela runs where its address file cannot be seen.
  - `LEELA_INSTALL = 'https://github.com/vedicreader/leela#install'`.
  - `leela_address() -> Path` — `$XDG_CONFIG_HOME/leela/serving.json`, else `~/.config/leela/serving.json`. Read at each call, not at import.
  - `leela_base() -> str|None` — the `url` of the address file when its `pid` is alive (`os.kill(pid, 0)`, as Leela's own `serving()` does), else `cfg.leela` when it is set, else None. A URL that is not `http://` on `127.0.0.1`, `localhost` or `[::1]` with a port gives None. No network call: one small file read, so there is no cache.
  - `leela_link(j, i:int|None=None, topic:str='') -> str|None` — `leela_base()` (without its last `/`) plus `handoff(j.id if j else '', i, topic)`, or None when `leela_base()` is None.
  - `leela_line(j, i:int|None=None, topic:str='', say:str='Open in Leela for code and tools', quiet:bool=False) -> FT` — with a link: `P(A(f'{say} ↗', href=…, target='_blank', rel='noopener'), cls='leela-line')`. With no link: `P('Open this in Leela for code and tools. ', A('Get Leela', href=LEELA_INSTALL, target='_blank', rel='noopener'), cls='leela-line muted')`, or `''` when `quiet`. Never a link to a Leela that is not running.
  - Where the line shows: the plan page of a tool walk (`leela_line(j)`), under the title; the step page of a step with `leela` (`leela_line(j, i)`), under `#check`; under the code card of any walk (`leela_line(j, i, say='Go further with real code in Leela', quiet=True)`); the concept page, for a concept with `code` in its ways (`concept_more`: `leela_line(None, topic=c.name, say=f'Learn {c.name} with code in Leela', quiet=True)`).
  - `/walk/new` takes `tool` (a tick box): `tool='on'` makes `kind='tool'`, for a document, a text, a topic or a link. The Add walk form gets the tick box "It is a library or a command-line tool. Code and tools open in Leela." `/w/{jid}/plan` with `act='check'` and `way='code'` on a tool walk returns 400.

- [ ] **Step 1: Write the failing tests**

```python
# nbs/11_journey.ipynb, section "Open in Leela": the shared cases, which Leela's contract test also runs
HANDOFF_CASES = [(dict(jid='attention-ab12'), '/learn?walk=attention-ab12'),
                 (dict(jid='attention-ab12', i=3), '/learn?walk=attention-ab12&step=3'),
                 (dict(topic='Agents and tools'), '/learn?topic=Agents+and+tools'),
                 (dict(jid='pydantic-ai-docs-9f0c', i=0, topic='Agents'), '/learn?walk=pydantic-ai-docs-9f0c&step=0&topic=Agents')]
```

```python
# each case makes its path, and the path reads back to the same values
for kw, path in HANDOFF_CASES:
    test_eq(handoff(**kw), path)
    test_eq(read_handoff(path.split('?', 1)[1]), AttrDict(walk=kw.get('jid', ''), step=kw.get('i'), topic=kw.get('topic', '')))
test_fail(lambda: read_handoff('walk=../x'), contains='walk')            # an id that is not a walk id
test_fail(lambda: read_handoff('walk=a-1&step=-1'), contains='step')
test_fail(lambda: handoff(), contains='nothing to open')
```

```python
# a tool walk has no code check; the step of an idea with the code way points to Leela
lr = temp_learning(); did = add_paper(lr)
ask = Fake({'Return JSON: {"concepts"': EXTRACT_REPLY})
j = journey_from_source(lr, ask, did, kind='tool')
assert lr.journey(j.id).kind == 'tool' and j.id in [x.id for x in lr.journeys()]   # the marker does not change how a journey is kept
assert all(s['check']['kind'] != 'code' for s in j.steps)
test_eq([bool(s.get('leela')) for s in j.steps], [False, True, False])              # softmax has the code way
assert 'leela' not in journey_from_source(lr, ask, did).steps[1]                    # a walk to read does not change
```

```python
# tests/walk_data.py: add (with `import os` at the top)
def leela_file(root, port=5011, pid=None, url=None):
    "Write the address file that a running Leela writes, under `root`; the pid of this test makes it look alive."
    f = Path(root)/'leela'/'serving.json'; f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(dict(host='127.0.0.1', port=port, pid=pid or os.getpid(), url=url or f'http://127.0.0.1:{port}/')))
    return f
```

```python
# tests/conftest.py: add. No test reads the owner's real Leela address file.
@pytest.fixture(autouse=True)
def no_leela(monkeypatch, tmp_path_factory):
    from abhyasa.core.cfg import cfg
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path_factory.mktemp('xdg'))); monkeypatch.setitem(cfg, 'leela', '')
```

```python
# tests/test_leela.py
import json, subprocess, sys
from fastcore.basics import AttrDict
from abhyasa.core.cfg import cfg
from abhyasa.core.leela import leela_link
from walk_data import leela_file

def test_leela_link_is_local_and_live(monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path)); j = AttrDict(id='attention-ab12')
    assert leela_link(j, 2) is None                                                     # no address file: no link
    f = leela_file(tmp_path)
    assert leela_link(j, 2) == 'http://127.0.0.1:5011/learn?walk=attention-ab12&step=2'
    assert leela_link(None, topic='Softmax') == 'http://127.0.0.1:5011/learn?topic=Softmax'
    p = subprocess.Popen([sys.executable, '-c', '']); p.wait()
    leela_file(tmp_path, pid=p.pid); assert leela_link(j) is None                       # a stale file: that Leela stopped
    leela_file(tmp_path, url='http://evil.example:5011/'); assert leela_link(j) is None  # not on this computer
    f.unlink(); monkeypatch.setitem(cfg, 'leela', 'http://127.0.0.1:5020/')
    assert leela_link(j) == 'http://127.0.0.1:5020/learn?walk=attention-ab12'           # the owner's setting
    monkeypatch.setitem(cfg, 'leela', 'https://evil.example/'); assert leela_link(j) is None
```

```python
# tests/blocks/test_walk.py
import os
from abhyasa.core.leela import LEELA_INSTALL

def test_tool_walk_opens_in_leela(mk, walk_fake, lr, monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    cl = mk(); assert 'Code and tools open in Leela' in cl.get('/add').text
    jid = cl.post('/walk/new', data=dict(ref=add_paper(lr), tool='on')).headers['hx-redirect'].split('/')[-1]
    assert lr.journey(jid).kind == 'tool'
    plan = cl.get(f'/w/{jid}').text
    assert 'Open this in Leela for code and tools' in plan and LEELA_INSTALL in plan and '/learn?' not in plan   # no Leela: never a broken link
    assert cl.post(f'/w/{jid}/plan', data=dict(i=1, act='check', way='code')).status_code == 400                # no library code check in abhyasa
    leela_file(tmp_path)
    assert f'href="http://127.0.0.1:5011/learn?walk={jid}"' in cl.get(f'/w/{jid}').text
    cl.post(f'/w/{jid}/start')
    step = cl.get(f'/w/{jid}/1').text
    assert f'http://127.0.0.1:5011/learn?walk={jid}&amp;step=1' in step and 'target="_blank"' in step
    assert 'code-editor' not in cl.get(f'/w/{jid}/1/check').text                                                 # the check here is short or order
    assert '/learn?' not in cl.get(f'/w/{jid}/0').text                                                           # an idea with no code way has no link

def test_code_card_and_concept_page_offer_leela_only_when_it_runs(mk, walk_fake, lr, monkeypatch, tmp_path):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 1, check=dict(way='code', kind='code', depth=4, why=''))
    card = cl.get(f'/w/{jid}/1/check').text
    assert 'code-editor' in card and 'Leela' not in card and 'Leela' not in cl.get('/c/softmax').text   # quiet when Leela is not running
    leela_file(tmp_path)
    card = cl.get(f'/w/{jid}/1/check').text
    assert 'code-editor' in card and f'/learn?walk={jid}&amp;step=1' in card                           # the small stdlib check stays in abhyasa
    assert '/learn?topic=Softmax' in cl.get('/c/softmax').text
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run nbdev-test --path nbs/11_journey.ipynb; uv run pytest tests/test_leela.py tests/blocks/test_walk.py -k leela -q`
Expected: FAIL with `NameError: name 'handoff' is not defined`, `ModuleNotFoundError: No module named 'abhyasa.core.leela'`, and no "Code and tools open in Leela" on `/add`.

- [ ] **Step 3: Implement.**
  - `handoff` and `read_handoff` use only `urllib.parse` (`urlencode`, `parse_qs`). `read_handoff` takes the first value of each key and ignores other keys, so Leela can add its own.
  - `_check`: for `kind='tool'`, call `check_for` with `AttrDict(c, ways=[w for w in (c.get('ways') or TEXT_WAYS) if w in TOOL_WAYS] or ['words'])`. Do not change `check_for`.
  - The makers pass `kind` to `_check` and to the journey. `journey_from_sources` takes `kind` out of `extra`, so it reaches `_steps`.
  - `abhyasa/core/leela.py` imports `handoff` from `abhyasa.journey`. The blocks import `leela_line` from `abhyasa.core.leela`; no block imports another.
  - `walk.css`: `.leela-line` is one muted line with no box (`docs/design-layers.md`).
  - abhyasa never calls Leela. It reads the address file and makes a link. The learner's browser opens the link.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run nbdev-prepare && uv run nbdev-test --path nbs/11_journey.ipynb && uv run pytest -q`
Expected: PASS, with the Task 3, Task 8 and Task 13 tests unchanged.

- [ ] **Step 5: Commit**

```bash
git add nbs/11_journey.ipynb abhyasa/journey.py abhyasa/_modidx.py abhyasa/core/leela.py abhyasa/core/cfg.py abhyasa/blocks/walk abhyasa/blocks/add tests/walk_data.py tests/conftest.py tests/test_leela.py tests/blocks/test_walk.py
git commit -m "Add Open in Leela: a tool walk has no code check here and links its code steps to Leela"
```

---

### Task 15: A trial on real material

Spec 6.13. The script uses the real model and the network. CI and the test suite never run it in full; the test below runs it in its dry mode only. No library code runs in abhyasa: the PydanticAI and Claude Code walks are tool walks (Task 14), and the trial checks their Leela links. The trial never starts or calls Leela.

**Files:**
- Create: `tools/walk_trial.py` (a script, not a test)
- Create: `tests/test_trial.py` (the dry run)
- Output (the real run): `design/screens/trial/report.md` and `design/screens/trial/<walk>-<i>.png`

**Interfaces:**
- Consumes: Task 13 `file_link`, `journey_from_sources`; Task 14 `kind='tool'`, `leela_link`, `handoff`; Task 7 `code_task`, `run_code`; Task 3 `walk_from_topic`; Task 4 `tutor_note`, `open_short`; `Session`; `ground.VaultSource`; `app.mk_app`; `tools/grade_eval.py` `question_checks` (`from grade_eval import question_checks`: the script folder is on `sys.path`); `llm.Router`, `rishi_ask`, `for_task`.
- Produces:
  - `CASES = [dict(name='attention', link='1706.03762', pages=1), dict(name='gradient-descent', topic='how gradient descent works'), dict(name='pydantic-ai', link='https://ai.pydantic.dev', pages=8, kind='tool'), dict(name='claude-code', link='https://docs.claude.com/en/docs/claude-code/overview', pages=8, kind='tool')]`
  - `build(lr, ask, case, read=None) -> AttrDict(j, secs)` — a link through `file_link` and `journey_from_sources(kind=case.get('kind', ''))`; a topic through `walk_from_topic(sources=[VaultSource(lr)])`, after the other cases are filed.
  - `measure(lr, ask, j) -> AttrDict(steps, found, figures, kinds, asks_ok, asks, secs_step, bad_asks)` — for each step: `tutor_note`, and `open_short` for a short check, with `question_checks` on the question; `secs_step` is the mean time of a step.
  - `grade_trip(lr, ask, j) -> AttrDict(good, weak)` — on the first short step: the concept statement as the answer (it must grade correct), then a new question answered "I am not sure." (it must grade not correct).
  - `code_trip(lr, ask, j) -> AttrDict(naive, good, secs)` — on the attention walk only (a stdlib exercise): `code_task` on the first code step (or on step 0, set to `code`); the stub as the naive try, then the solution kept on the server (`tutor.open[qid].answer`) as the good try; each as `passed of total`.
  - `handoff_trip(lr, ask, j, cfg_home) -> AttrDict(code_checks, leela_steps, links_ok, pages_ok)` — on a tool walk: `leela_file(cfg_home, port=5019)` (Task 14: a fake address file in a temp folder; no Leela runs), then for each step: `code_checks` counts checks of kind `code` (it must be 0); for each step with `leela`, `leela_link(j, i)` must equal `http://127.0.0.1:5019` + `handoff(j.id, i)`, and the step page and its check card (through `mk_app(lr, ask)` and a test client) must have that link and no `code-editor`. It sets `XDG_CONFIG_HOME` to `cfg_home` for the trial run only.
  - `shoot(lr, ask, jid, idxs, out) -> list[Path]` — the app (`mk_app(lr, ask)`) under uvicorn in a thread on a free port on 127.0.0.1 (never 5001, 5055, 5077, 5078 or 9223); Playwright `p.chromium.launch(headless=True)`, 1280×900; for steps 0, the middle and the last: wait until `#check` has no `.pending` (120 s), save a full-page PNG; browser and server closed in a `finally`.
  - `report(rows, out) -> str` — a Markdown table (walk, steps, with passage, figures, checks short/demo/order/code, one ask, grade round trip, code naive/good, Leela steps and links right, s/step, build s), then for each walk: the questions that fail a check (in full), the grade, code and Leela results, the screens. Writes `out/report.md` and prints the table.
  - Options: `--model`, `--only NAME`, `--out` (default `design/screens/trial`), `--dry` (`Fake` with the replies of `walk_fake`, and a fake `read` that files `PAGES`), `--no-shots`.
  - The vault is always `temp_learning()`. The script never opens `~/.vishalakshi/vault.db` or `~/.config/abhyasa`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_trial.py: the trial script works on the shared data, with no model, no network and no browser
import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).parents[1]

def test_trial_dry_run(tmp_path):
    r = subprocess.run([sys.executable, 'tools/walk_trial.py', '--dry', '--no-shots', '--out', str(tmp_path)],
                       capture_output=True, text=True, timeout=180, cwd=ROOT)
    assert r.returncode == 0, r.stderr
    rep = (tmp_path/'report.md').read_text()
    for name in ('attention', 'gradient-descent', 'pydantic-ai', 'claude-code'): assert name in rep
    assert 'one ask' in rep and 's/step' in rep and 'naive' in rep and 'Leela' in rep
```

- [ ] **Step 2: Run the test to see it fail**

Run: `uv run pytest tests/test_trial.py -q`
Expected: FAIL: `can't open file '.../tools/walk_trial.py'`.

- [ ] **Step 3: Write `tools/walk_trial.py`** to the interfaces above. A module docstring says what it does and how to run it, as `tools/grade_eval.py` does. Each case runs alone: an error in one case goes into its row, and the next case still runs.

- [ ] **Step 4: Run the dry test and the suite**

Run: `uv run pytest tests/test_trial.py -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/walk_trial.py tests/test_trial.py
git commit -m "Add a trial script that makes walks from a paper, a topic and two docs sites, and checks their Leela links"
```

- [ ] **Step 6: The controller runs the trial with the real model**

Run: `uv run --all-extras python tools/walk_trial.py`
Expected: a table with 4 rows, `design/screens/trial/report.md`, and 12 screens. This output is for the owner to read. The report marks a value that is outside these guides: 5 to 40 steps; at least 70% of steps with a passage for the paper and the docs walks; every question passes the one-ask checks; the grade round trip is right both ways; on the attention walk, the naive code fails at least one test and the good code passes all; on the two tool walks, no `code` check, and every Leela link is right; at most 30 s for each step.

- [ ] **Step 7: Fix what the trial finds.** For each problem, make one small follow-up: a failing test that shows it (with `Fake` or the dry data), the fix, and one commit. Then run the trial again for that walk only (`--only NAME`). List each fix at the end of `report.md`.

- [ ] **Step 8: Commit the report and the screens**

```bash
git add design/screens/trial
git commit -m "Add the report and screens of the walk trial on real material"
```

---

### Task 16: Docs and one look in a real browser

**Files:**
- Modify: `nbs/index.ipynb` (short sections "Learn a paper, a topic or a link as a walk", "Rabbit holes" and "Open in Leela"; check for stale references)
- Modify: `README.md` (made by `nbdev-prepare` from `index.ipynb`), `CHANGELOG.md` (an entry under the next version), `docs/design-layers.md` (the walk page and the side pane in the list of pages)
- Create: `tools/walk_look.py` (a script, not a test: it starts the app on a temp vault with `Fake`, opens walk steps in Playwright's bundled Chromium, and saves `design/screens/walk-code.png`, `walk-demo.png` and `walk-pane.png`)

**Interfaces:**
- Consumes: everything above.
- Produces: docs only, and three screens.

- [ ] **Step 1: Write the failing check.** `tools/walk_look.py` asserts, at 1280 px:
  - in the step page: `#rail`, `#passage`, `#check .code-editor`, no horizontal scroll (`document.documentElement.scrollWidth <= 1280`), and that ⌥S presses "Next idea" (⌥F still opens the keyboard shortcuts);
  - on step 3 with an unmet need: ⌥B opens the offer, `2` opens the side walk in `#rh-pane`, the URL has `rh=` with a local path, there is still no horizontal scroll, and ⌥Z closes the pane, takes `rh` out of the URL and puts the focus on the check;
  - `?rh=https://evil.example/` draws no `#rh-pane`, and `window.postMessage({type: 'rh:at', url: 'https://evil.example/'}, '*')` from the main page leaves `rh` unchanged;
  - at 1000 px, ⌥B and `2` open the side walk in the same tab, with "Back to the paper" at the top;
  - on a tool walk, with a fake Leela address file in a temp `XDG_CONFIG_HOME`, the code step has the "Open in Leela" link with `target="_blank"`; with no file, the step has the muted line and the "Get Leela" link, and no link to `/learn`.

- [ ] **Step 2: Run it to see it fail**

Run: `uv run python tools/walk_look.py`
Expected: PASS when Tasks 5-14 are right. A FAIL names the missing element, the scroll width, the key or the URL; fix it in the block's `.css`, `ui.py` or `.js`, or in `core/pane.js`, before Step 3.

- [ ] **Step 3: Write the docs** in STE grade 9, with no odd machine phrasing:
  - what a walk is, the three checks, and that reading never waits for a check;
  - that learner code runs in a closed process with no network (never "a security sandbox");
  - rabbit holes: the needs line, the three ways down, the side pane and its keys (⌥B, ⌥Z, Esc), the depth limit, and that the open check and the draft stay;
  - a walk from a link: what links work, that abhyasa fetches only when you ask, only pages in the folder of the link, and at most the page cap;
  - Open in Leela: abhyasa installs no libraries and runs only short stdlib exercises; for code with a library or a tool, a step links to Leela, which has the tool environments, code lookup and the agent tutor; a tool walk (a library or a command-line tool) asks short-answer and order checks here; with no Leela running, the step says so and links to the install page.
  Run `uv run nbdev-prepare`, and look for stale references in `index.ipynb`.

- [ ] **Step 4: Run everything**

Run: `uv run nbdev-prepare && uv run pytest -q && uv run python tools/walk_look.py`
Expected: PASS; three new screens in `design/screens/`.

- [ ] **Step 5: Commit**

```bash
git add nbs/index.ipynb README.md CHANGELOG.md docs/design-layers.md tools/walk_look.py design/screens/walk-code.png design/screens/walk-demo.png design/screens/walk-pane.png
git commit -m "Document the walk, rabbit holes, links and Open in Leela, and add screens of a code check, a demo and the side pane"
```

### Task 17: Runner options for Leela

Added by ruling (28 Oct): Leela uses abhyasa's runner and needs no copy of it. Run Task 17, then Task 18, then Task 16, because the docs describe the new Settings page.

**Files:**
- Modify: `nbs/06_check.ipynb` (`run_isolated`), then `uv run nbdev-prepare`

**Interfaces:**
- Produces: `run_isolated(kind, fname, source, tests, *, total=10., setup=(), sandbox=True, python=None, unix=False) -> dict`

- [ ] **Step 1: Write the failing tests** in `nbs/06_check.ipynb`:
  - `python=` runs the given interpreter (use `sys.executable` in the test, and check that the result reports the same `sys.version`). With `python=None` the runner uses `sys.executable`, as before.
  - `unix=True` lets the learner code make an `AF_UNIX` `socket.socketpair()` and send bytes across it. `connect`, `bind`, `getaddrinfo` and `sendto` to an internet address are still refused, both by the audit hook and, on macOS, by the sandbox-exec profile.
  - `unix=False` (the default) refuses `socketpair` as it does now.
  - `total` stays as passed with both options.
- [ ] **Step 2: Implement.** `python` replaces `sys.executable` in `cmd` and keeps `-I -B`. `unix` changes only the audit hook's socket rule and adds the sandbox-exec rule for local unix sockets. It never allows network. Docstring: one line, and say "a closed process with no network", never "a security sandbox".
- [ ] **Step 3: Run** `uv run nbdev-test --fname nbs/06_check.ipynb` and `uv run pytest -q`. Expected: PASS.
- [ ] **Step 4: Commit**: `Let run_isolated use another Python and local unix sockets, for Leela`

### Task 18: Settings for everything

Added by ruling (28 Oct). The owner wants every value a person might change on the Settings page, in clear groups, with practical defaults, including the number of ideas in a walk. The inventory of current values, with file:line, is in the plan workspace: `settings-inventory.md` (marks S = safe to expose, L = a resource cap, K = keep fixed).

**Rules:**
- One table is the single source: for each setting, its group, key, label, a one-line help text, the type, the default and, for numbers, a min and a max. The engine, the web code and the Settings page all read this table. Values are read at call time, as the prompts are.
- A saved value outside its range is clamped to the range, and a value of the wrong type uses the default. A bad settings file never stops the app.
- Defaults are the values the code uses now (the inventory lists them). The app must behave the same when nobody changes a setting.
- K items stay fixed and get no setting: no network in the code runner, the sandbox-exec profile, the audit hook, `python -I`, `sandbox=True`, the link checks for local addresses, plain HTTP with `auto=False`, link kinds, the HTML allowlist, the pane URL check, local-only hosts, the test allowlist, the grade scale and the depth ladder.
- Each row has "Use the default". Each group has "Use the defaults for this group".
- Remove copies: one value per setting. Fix the copies the inventory names, for example the default page count in three places, the "10 s" message in walk.py, "up to 4 ideas" in detour/ui.py, the GOAL copy in journey.py and "every 10 seconds" on the Settings page.

**Groups, in page order (labels in STE). Ranges are the controller's ruling:**
1. **Look**: theme and mode (as now).
2. **Learning** (the same values as the Profile page, stored once, editable in both places): pace, session length (3 to 40, default 12), new ways (never, sometimes, often).
3. **Walks**: ideas in a walk `MAX_STEPS` (3 to 30, default 12); hands-on share `MAX_HANDS_ON` (0 to 1, default 1/3); passage length (200 to 2000 chars, default 600); note length (20 to 120 words, default 60); rabbit-hole depth (1 to 4, default 2); ideas in a side walk (2 to 8, default 4); how long "Back on the paper" shows (1 to 60 min, default 10); demo wait (30 to 300 s, default 90).
4. **Checks and grading**: tries `MAX_TRIES` (1 to 5, default 3); shaky pass `NEAR` (5 to 9, default 7); learned depth `GOAL` (2 to 5, default 4); sure confidence `HIGH` (40 to 90, default 60); hints before a pass is shaky (1 to 4, default 2); one ask per question (on/off, default on); use my sources (on/off, default on); misses before a demo (1 to 5, default 2); retest a miss after N questions (1 to 6, default 2).
5. **Review**: first interval after a solid answer (0.25 to 7 days, default 1); after a shaky answer (0.1 to 3 days, default 0.5); growth factor (1 to 6, default the current 3); new: most reviews a day (0 = no limit, up to 200, default 0); fading below recall (0.3 to 0.9, default 0.6).
6. **Links**: pages read by default (1 to the page cap, default 8); page cap (1 to 50, default 20); time per fetch (5 to 120 s, default 30); download speed cap (0.1 to 10 MB/s, default 1); characters kept per page (default 400000) and read per page (default 100000), both 10000 to 1000000.
7. **Code runner**: total time (5 to 60 s, default 10); time per test (1 to 10 s, default 2); largest file (1 to 100 MB, default 10). The kill time and the CPU limit follow the total time (total + 2 and total + 1), as now.
8. **Speech to text**: as now, plus the pause before a cut (300 to 2000 ms, default 700) and the longest segment (5 to 30 s, default 12).
9. **Models**: new: the default model (now only `--model`, `$ABHYASA_MODEL` or the Mac app; those still win when set). Own rows, each falling back to the task it borrows now: plan, pick, walk note, profile and code exercise. The existing rows stay. Add `extract` to the defaults.
10. **Lists** (advanced, closed by default): the visible list lengths in the inventory's U2 row.
11. **Prompts**: as now, plus registering the prompts that are not registered yet: `PRIMER_SP`, `ONBOARD_SP`, `OBSERVE_SP`, `STT_SP`, `CODE_RULES`, `ORDER_AIM` and `DEPTH_ASK`. Keep the existing format checks, for example `need_lines`.

Groups 10 and the rarely changed caps in groups 6 and 7 go under a closed "More" part of their group, so the page stays short.

**Files:** the settings table goes in the notebook that has `settings()` now (`nbs/` for `voice.py`) or in a new small notebook `nbs/15_settings.ipynb` if it is cleaner. Change each engine notebook that uses one of the values. Change `abhyasa/blocks/settings/` and `abhyasa/blocks/profile/` for the page.

- [ ] **Step 1: Write the failing tests**:
  - the table has every group above, and every default equals the value the code used before (one test per group);
  - a saved value outside its range is clamped, a wrong type gives the default, and an unknown key is ignored;
  - one engine use per group reads the saved value at call time (for example a walk of 5 steps after setting ideas to 5, a run that stops at the new total, a link that reads the new page count);
  - the Settings page lists every group in order, each row shows its help text and range, "Use the default" restores the default, and a POST with a value out of range saves the clamped value;
  - pace, session length and new ways saved on Settings show on the Profile page, and the other way round;
  - no K item has a setting (a test that names them).
- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement.** Keep each value in one place. Short docstrings. Help texts in STE grade 9, with no odd machine phrasing.
- [ ] **Step 4: Run** `uv run nbdev-prepare` and `uv run pytest -q`. Expected: PASS. Check by hand that a settings file from before this task still loads.
- [ ] **Step 5: Commit** in small steps, one plain STE line each.

### Task 19: Design polish: one calm, cohesive app

Added by ruling (28 Oct). The owner asked for a design review so the app feels cohesive, not overwhelming, inviting and "like magic", and approved all of it. The design review, with 17 ranked findings, 7 magic touches and a system note, is in the plan workspace: `design-review.md`. The screens it refers to are in `design-review/`. Run this task after Task 18 and before Task 16.

**Owner rulings:**
- Build all 17 findings (F1 to F17) and all 7 magic touches.
- Keys: ⌥S means Send everywhere, as in a session. In a walk, ⌥S sends the open check. Skipping is a quiet "Skip this idea" link. Once the check is closed, "Next idea" is the one main button, and ⌥S presses it. Update `abhyasa/core/keys.py`, the shortcut sheet and the Sanketa pack in one place. Fix the two clashing keys that F14 names. Check `keys.py` before you add any key. Keys stay left-hand.
- Follow the system note (design-review.md section 5): shared tokens, one spacing scale and shared components in `core/` (for example the one `Check` component of F3). A block never imports another block. Blocks use the shared pieces through `core/`.
- Motion: every magic touch respects `prefers-reduced-motion`. No sound.
- All copy follows ASD-STE100 at US grade 9, with no machine-sounding phrasing.

**Files:** `abhyasa/core/` (base.css, ui.py, core.js, keys.py, a new shared check component), and the blocks the findings name (walk, detour, session, today, add, graph, profile, settings, strengths, concepts). Engine notebooks only if a finding needs engine data (for example the walk summary of F2).

- [ ] **Step 1: Write the failing checks.** For each finding and magic touch, add one pytest test (HTML structure, classes, copy, keys) or one Playwright assertion in `tools/walk_look.py`. Examples: a walk step has exactly one primary button; the end of a walk shows "You finished the walk" with one dot for each idea; the session and the walk render the same `Check` markup; the side pane at 1280 px leaves the top bar on one row; a missing figure shows no broken image; every animation is off under reduced motion.
- [ ] **Step 2: Run them to see them fail.**
- [ ] **Step 3: Implement**, in small commits by finding. Take screens of each changed page at 1280 and 1000 px, light and dark, Paper and Signal, into `design/screens/polish-*.png`.
- [ ] **Step 4: Run** `uv run nbdev-prepare`, `uv run pytest -q` and `uv run python tools/walk_look.py`. Expected: PASS.
- [ ] **Step 5: Design re-check.** The controller sends the new screens to the design reviewer, who confirms each finding is closed or names what is left.
