# The Group Talk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a walk into a talk for a group: one slide for each idea, a presenter window and an audience window that stay in step, questions for the room (hands first, then phones on the same Wi-Fi with a second vote and questions from the room), a side pane beside a slide, and a recap after the talk, with no change to the owner's learner model.

**Architecture:** Option A first. A new engine module `abhyasa/talk.py` (from `nbs/17_talk.ipynb`) holds the deck shape, `check_talk`, the public deck, the run log and the recap, with no web code, so Leela can import it. A stage bundle in `abhyasa/core/` (`stage.js`, `stage.css`, `stage.py`) holds the `BroadcastChannel` with checked messages, the laser, the blank screen, the audience frame style, the mirrored demo and the talk keys. A new block `abhyasa/blocks/talk/` draws the editor, the presenter view, the audience view and "After the talk", and talks to other blocks only through hooks. Option B then adds the subpackage `abhyasa/sabha/`, a small room server that imports no abhyasa code, runs on its own port only during a talk, and serves only the public deck and the phone page. The talk block calls the room in the same process.

**Tech Stack:** Python 3.12+, nbdev 3 on hatchling (engine notebooks in `nbs/`), FastHTML + htmx (blocks), Starlette + uvicorn (the room, from `python-fasthtml`'s dependencies), `BroadcastChannel` and server-sent events in the browser, rupaka 0.0.3 demos, one vendored MIT QR encoder, `abhyasa.llm.Fake`, pytest, httpx (from Starlette's test client), node for the js checks, Playwright bundled Chromium for the browser checks.

**Spec:** `docs/superpowers/specs/2026-10-29-group-talk-design.md`

## Global Constraints

- Engine code is edited only in `nbs/*.ipynb`; then run `uv run nbdev-prepare` (hyphen). Never edit a generated `abhyasa/*.py` engine file. The new engine notebook is `nbs/17_talk.ipynb` (generates `abhyasa/talk.py`); add it to `nbs/sidebar.yml`.
- `abhyasa.talk` imports no web code (`fasthtml`, `starlette`, `abhyasa.core`, `abhyasa.blocks`, `abhyasa.app`). `tests/test_import_weight.py` checks it.
- Web code (`abhyasa/blocks/`, `abhyasa/core/`, `abhyasa/app.py`) and `abhyasa/sabha/` are written by hand and tested with `uv run pytest`.
- A block never imports another block. It adds to other pages only through hooks (`core/hooks.py`). `NAMES` in `abhyasa/blocks/__init__.py` gets `talk` after `detour` and before `today`.
- `abhyasa/sabha/` imports only the standard library, `starlette` and `uvicorn`, and its own modules with relative imports. It never imports `abhyasa`. Its tests use a fixture public deck, not the engine.
- Prose (UI text, prompts, notebooks, docs, commit messages) is ASD-STE100 Simplified Technical English, US grade 9, with no odd machine phrasing.
- Notebooks read as documents: an intro, short sections, a one-line lead before each code cell, small tests with a line on what each checks. Test imports go in their own cell (the docs build runs only import, export and `show_doc` cells).
- Tests use `temp_learning()` and `abhyasa.llm.Fake`. Never open `~/.vishalakshi/vault.db` or `~/.config/abhyasa`. `tests/conftest.py` already points both at temp folders.
- Browser checks: Playwright `p.chromium.launch(headless=True)`, no `executable_path`, one browser at a time, closed in a `finally`. Never the user's Chrome, port 9223 or `~/.cache/fastcdp/cdp-chrome`. No check takes the focus from the user's desktop (headless only).
- New prompt text is registered with `prompts.register`: `talk.choice`. The model task `talk` borrows `question` (`BORROWS`).
- New values that a person can change go into the settings table (`nbs/16_settings.ipynb`, group `talks`, spec section 16). Code reads them with `val(...)` at call time. Security limits are fixed and their names go into `FIXED`: `bind`, `join_code`, `rate`, `body`, `room_headers`.
- Keys (controller ruling): left hand only. Read `abhyasa/core/keys.py` before you bind a key; the task that binds a key adds it to `KEYS` (through `STAGE_KEYS`). The plain talk keys (D, space, A, Q, R, E, X, B, G, 1-6, F; B adds W, C, ⇧C, T, V) work only when `html` has the class `talk`, the focus is not in a text box and not in the demo. ⌥S, ⌥B, ⌥Z and ⌥F keep their app meanings. No new ⌥ key. In a talk window, ⌥T, ⌥C, ⌥G, ⌥D and / do nothing, and Esc never ends the talk.
- No new runtime dependency. Ruling: "no new vendored script" is lifted for one file only, the MIT QR encoder in `abhyasa/core/vendor/` (Task 11).
- The room's answers and the presenter's pick at a demo gate in a talk never go into `Learning.record`.
- No `answer` of a question goes into the public deck, the audience HTML, an `ask` stage message, the phone page or `/events` before the presenter shows the result.
- Text from the room is set as text (`textContent`, or an FT text node). Never `Md`, `NotStr` or `innerHTML`. The recap file escapes with `html.escape`.
- This plan never edits the rupaka repo. Task 4 ends in an ask to the rupaka owner.
- Commit messages are one plain STE line. No AI credit. No Co-Authored-By line.

## Review Focus

1. **A stale or second audience window** (an old run, another talk, a reload in the middle of a question): it shows the current place, and an old window never drives or shows another run. Tests: `test_place_survives_a_reload` and `test_audience_needs_the_run_key` in Task 6; the old-key check in `tools/talk_look.py` (Task 8).
2. **An answer that shows before R** in the audience HTML, an `ask` message, the phone page or `/events`. Tests: `test_audience_has_no_notes_and_no_answers` (Task 6), the `ask` case with `answer` in `STAGE_CASES` (Task 3), `test_events_have_no_answer_before_reveal` (Task 9).
3. **Room answers, hands or the presenter's gate pick that reach the learner model.** Tests: `test_hands_and_result_stay_out_of_learning` (Task 6), `test_room_rounds_stay_out_of_learning` (Task 11), the attempts check in `tools/talk_look.py` (Task 8).
4. **Hostile requests to the room** (a wrong Host, a foreign Origin, no cookie, a code flood, a 3 kB body, HTML in a question, a path out of `/img/` or `/static/`): each is refused, and text stays text. Tests: `test_hostile_cases_on_a_live_room` (Task 9), `test_question_html_stays_text` (Task 12).
5. **A room that stays open** after the talk ends, after the presenter closes the tab, after abhyasa stops, or after 3 hours: the port is closed. Tests: `test_room_closes_at_the_end` (Task 11), `test_room_expires` (Task 9), `test_close_all_on_shutdown` (Task 11).

---

## Shared test data

Task 1 writes this data once, as the plain module `tests/talk_data.py`. The engine notebook loads it with one hidden cell (`#| hide`: `import sys; sys.path.insert(0, '../tests'); from talk_data import *`). Block tests use `from talk_data import *`. Task 5 adds the fixture `talk_fake(walk_fake)` to `tests/conftest.py`: it adds `TALK_RULES` to the same `fake` and returns it.

```python
from walk_data import *
from abhyasa.journey import journey_from_source
from abhyasa.llm import Fake
from rupaka.spec import gallery

CHOICE = dict(q='What does softmax give for a list of scores?',
              options=['Weights above 0 that add to 1', 'The largest score only', 'The scores in order', 'Scores that are all above 1'], answer=0)
TALK_RULES = {'Return JSON: {"concepts"': EXTRACT_REPLY, 'You turn one check into a choice question': CHOICE}
PNG = b'\x89PNG\r\n\x1a\n'

def prep_walk(lr, jid):
    "Give the walk a short check on ideas 1 and 2, a note on idea 2, and a demo check on idea 3 with the softmax demo."
    lr.walk_step(jid, 0, check=dict(way='words', kind='short', depth=2, why=''))
    lr.walk_step(jid, 1, check=dict(way='maths', kind='short', depth=2, why=''), note='Softmax makes weights from scores.')
    lr.put_demo(gallery()['softmax-temperature'], 'scaling-by-the-root-of-dk')
    lr.walk_step(jid, 2, check=dict(way='demo', kind='demo', depth=2, why=''))
    return jid

def talk_walk(lr):
    "File the paper, make its walk in the engine, and prepare it; return the journey id."
    return prep_walk(lr, journey_from_source(lr, Fake(TALK_RULES), add_paper(lr)).id)

def make_talk(cl, jid):
    "Make a talk from walk `jid` through the app and wait for the job; return the talk id."
    cl.post('/talk/new', data=dict(jid=jid))
    loc = wait_for(lambda: cl.get(f'/talk/job?jid={jid}').headers.get('hx-redirect'))
    return loc.split('/')[-1]

def free_port():
    "A free TCP port on 127.0.0.1."
    import socket
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); return s.getsockname()[1]
```

The talk made from this walk, used by many tests: slides `s1` (Sequential computation, a choice from `CHOICE`), `s2` (Softmax, with the figure and the note), `s3` (Scaling by the root of dk, the softmax demo, a choice from the gate `hot` with the answer 1, "It falls"), `s4` (questions), `s5` (recap). Minutes `[4, 4, 5, 5, 2]`, 20 in total.

---

### Task 1: The talk engine: the deck shape, its checks, and a talk from a walk

Spec 7.1 to 7.6, 8, 16, 17.1, 17.4.

**Files:**
- Create: `nbs/17_talk.ipynb` → generated `abhyasa/talk.py`; `tests/talk_data.py` (above)
- Modify: `nbs/sidebar.yml` (add `17_talk.ipynb`), `nbs/16_settings.ipynb` (group `talks`, its rows, the model task `talk`, `FIXED`), `tests/test_settings_table.py` (`test_groups_in_order`, new `test_talks_defaults`), `tests/test_import_weight.py` (add `abhyasa.talk` to the light import)
- Generated: `abhyasa/settings.py`, `abhyasa/_modidx.py`

**Interfaces:**
- Consumes: `Learning`, `_src`, `slugify` (store); `journey.minutes`, `Learning.journey`, `Learning.demo_for`, `Learning.demo`; `llm.ask_json`, `for_task`; `prompts.register`, `prompt`; `settings.val`.
- Produces (in `abhyasa.talk`):
  - `TALK_SCHEMA = 1`; `SLIDE_KINDS = ('idea', 'pause', 'questions', 'recap', 'primer', 'board', 'timeline', 'code')`; `ASK_KINDS = ('choice', 'order', 'words', 'scale', 'none')`; `BEATS = ('passage', 'figure', 'demo', 'ask')` plus the prefixes `lit:` and (Leela) `lines:`, `out`; `QUESTIONS_MIN = 5`; `RECAP_MIN = 2`; `WORDS_MOST = 80`.
  - `check_talk(t:dict, schemes=('asset',)) -> list[str]` with exactly these problem texts: `f'schema {v} is not 1'`, `f'{sid}: the slide id is used twice'`, `f'{sid}: unknown kind {k!r}'`, `f'{sid}: unknown ask kind {k!r}'`, `f'{sid}: a choice needs 2 to 6 options'`, `f'{sid}: the answer {a!r} is not an option'`, `f'{sid}: the answer {a!r} is not an order of the options'`, `f'{sid}: unknown beat {b!r}'`, `f'{sid}: the beat {b!r} needs a {part} to show'`, `f'{sid}: the beat {b!r} lights text that is not in the passage'`, `f'{sid}: the figure {f!r} is not an image id'`. It never raises.
  - `TALK_CASES: list[tuple[dict, list[str]]]` (the cases in Step 1).
  - `ask_from_gate(spec:dict, gate:str) -> dict|None` (`kind`, `q`, `options`, `answer`); `public_ask(ask:dict|None) -> dict|None` (only `kind`, `q`, `options`, `most`).
  - `CHOICE_SP = register('talk.choice', 'Talk question', 'How the tutor turns a short check into a choice question for a room.', ...)`; its text starts "You turn one check into a choice question."
  - `ask_from_check(lr, ask, slug:str, passage:str='') -> dict` — a choice (`q`, 4 `options`, `answer`) through `for_task(ask, 'talk')`, or, when the reply is bad or the call fails, `dict(kind='words', q=f'Say in one or two sentences: what is {name}?', most=80)`.
  - `ask_for_concept(lr, ask, slug) -> dict` — the same as `ask_from_check` with the concept's statement as the passage (Task 7 uses it).
  - `slide_minutes(step:dict, ask:dict|None) -> int`; `talk_minutes(t) -> int`.
  - `talk_from_walk(lr, ask, jid:str, choice:bool|None=None) -> AttrDict` (spec 8). Talk id: `f'{slugify(title)[:34]}-talk-{uuid4().hex[:4]}'`, cut so it matches `^[a-z0-9-]{1,48}$`.
  - `Learning.put_talk(t) -> AttrDict` (raises `ValueError` with the problems joined by `; ` when `check_talk` finds any), `Learning.talk(tid) -> AttrDict|None`, `Learning.talks() -> L` (newest first), `Learning.drop_talk(tid)`. Kind `talk`, source `_src('talk', tid)`.
- Settings rows (spec 16): `talks.choice`, `talks.ask_min`, `talks.pair_min`, `talks.weak`, `talks.split_lo`, `talks.split_hi`, `talks.laser_ms`, `talks.image_mb`, `talks.port`, `talks.room_hours`, `talks.phones`, `talks.nets` (`ui=False`), with the labels, defaults and ranges of the spec table. `GROUPS['talks'] = ('Talks', 'Set how a talk runs and how the room works.')`, after `walks`. `TASK_HELP['talk'] = 'Writes a choice question for a talk from a short check.'`, `TASK_LABEL['talk'] = 'Talk questions'`, `BORROWS['talk'] = 'question'`.

- [ ] **Step 1: Write the failing tests** (test cells at the end of `nbs/17_talk.ipynb`, each with a one-line lead)

```python
# a talk from the walk: one slide for each idea, then questions and the recap
lr = temp_learning(); jid = talk_walk(lr); ask = Fake(TALK_RULES)
t = talk_from_walk(lr, ask, jid)
s1, s2, s3 = t.slides[:3]
assert [s['id'] for s in t.slides] == ['s1', 's2', 's3', 's4', 's5']
assert [s['kind'] for s in t.slides] == ['idea', 'idea', 'idea', 'questions', 'recap']
assert (s1['title'], s1['section'], s1['step'], s1['concept']) == ('Sequential computation', '1 Introduction', 0, 'sequential-computation')
assert s1['show']['passage'].startswith('This inherently sequential nature') and s1['show']['figure'] is None and s1['beats'] == ['passage']
assert s1['ask'] == dict(kind='choice', **CHOICE, src=dict(check='short'))
assert s2['show']['figure'] == 'asset:attention/images/fig2.png' and s2['beats'] == ['passage', 'figure'] and s2['notes'] == 'Softmax makes weights from scores.'
assert s3['show']['demo'] == 'softmax-temperature' and s3['beats'] == ['passage', 'demo']
assert s3['ask'] == dict(kind='choice', q='T goes from 1 to 2. What happens to the share of Paris?',
                         options=['It rises', 'It falls', 'It stays the same'], answer=1, src=dict(demo='softmax-temperature', gate='hot'))
assert [s['mins'] for s in t.slides] == [4, 4, 5, 5, 2] and talk_minutes(t) == 20 and t.minutes == 20
assert len([c for c in ask.calls if 'You turn one check into a choice question' in c[0] + c[1]]) == 2   # no call for the demo step
assert t.src == {'walk': jid} and t.schema == TALK_SCHEMA and t.live is None and t.phones is False
assert check_talk(t) == [] and lr.talk(t.id).title == 'Attention Is All You Need' and [x.id for x in lr.talks()] == [t.id]
```

```python
# a bad reply, or choice=False, gives a words question; a demo step with no demo falls back to its concept
lr2 = temp_learning(); jid2 = talk_walk(lr2)
bad = talk_from_walk(lr2, Fake({**TALK_RULES, 'You turn one check into a choice question': dict(q='', options=[], answer=9)}), jid2)
assert bad.slides[0]['ask'] == dict(kind='words', q='Say in one or two sentences: what is Sequential computation?', most=80, src=dict(check='short'))
off = talk_from_walk(lr2, Fake(TALK_RULES), jid2, choice=False)
assert off.slides[1]['ask']['kind'] == 'words'
lr2.v.forget(lr2.demo('softmax-temperature').doc_id)
nodemo = talk_from_walk(lr2, Fake(TALK_RULES), jid2)
assert nodemo.slides[2]['show']['demo'] is None and nodemo.slides[2]['beats'] == ['passage'] and nodemo.slides[2]['ask']['kind'] == 'choice'
```

```python
# a question from a gate needs fixed options and an answer that the spec holds
g = gallery()
assert ask_from_gate(g['parabola-vertex'], 'move') == dict(kind='choice', q='b goes from 0 to 2. Where does the lowest point move?',
                                                          options=['Left and down', 'Right and down', 'Straight up', 'It stays'], answer=0)
assert ask_from_gate(g['reciprocal-rank-fusion'], 'win') is None   # the answer needs derive
assert ask_from_gate(g['vowel-sandhi'], 'join') is None            # the options need derive
assert ask_from_gate(g['softmax-temperature'], 'nope') is None
assert public_ask(s3['ask']) == dict(kind='choice', q='T goes from 1 to 2. What happens to the share of Paris?', options=['It rises', 'It falls', 'It stays the same'])
assert public_ask(None) is None
```

```python
# TALK_CASES: each talk gives exactly its problems
GOOD = dict(id='t-1', kind='talk', schema=1, title='T', src={'walk': 'w-1'}, minutes=10, phones=False, live=None,
            slides=[dict(id='s1', kind='idea', title='A', section='', notes='', mins=3,
                         show=dict(passage='Scores become weights.', figure='asset:a/fig.png', demo=None),
                         beats=['passage', 'lit:weights', 'figure'], ask=dict(kind='choice', q='Q?', options=['a', 'b'], answer=1))])
for case, want in TALK_CASES: assert check_talk(case) == want, (case, want)
wants = [w for _, w in TALK_CASES]
assert [] in wants and ['schema 2 is not 1'] in wants and ["s1: unknown kind 'video'"] in wants
assert ['s1: the answer 2 is not an option'] in wants and ['s1: a choice needs 2 to 6 options'] in wants
assert ["s1: the beat 'demo' needs a demo to show"] in wants and ["s1: the beat 'lit:gradients' lights text that is not in the passage"] in wants
assert ["s1: the figure '/Users/k/fig.png' is not an image id"] in wants and ["s1: the figure 'asset:../vault.db' is not an image id"] in wants
assert ['s1: the slide id is used twice'] in wants and ["s1: unknown ask kind 'poll'"] in wants and ["s1: unknown beat 'fly'"] in wants
assert ['s1: the answer [0, 0, 1] is not an order of the options'] in wants
test_fail(lambda: lr.put_talk(dict(GOOD, schema=2)), contains='schema 2 is not 1')
```

Write `TALK_CASES` in the notebook as `GOOD` and one changed copy of it for each problem above (13 cases, the order case with `ask=dict(kind='order', q='Q?', options=['a', 'b', 'c'], answer=[0, 0, 1])`).

```python
# tests/test_settings_table.py: test_talks_defaults
def test_talks_defaults():
    assert [r.name for r in rows('talks')] == ['talks.choice', 'talks.ask_min', 'talks.pair_min', 'talks.weak', 'talks.split_lo', 'talks.split_hi',
                                               'talks.laser_ms', 'talks.image_mb', 'talks.port', 'talks.room_hours', 'talks.phones', 'talks.nets']
    assert (val('talks.choice'), val('talks.ask_min'), val('talks.pair_min'), val('talks.port'), val('talks.room_hours'), val('talks.phones')) == (True, 1, 2, 5180, 3, 300)
    assert (val('talks.weak'), val('talks.split_lo'), val('talks.split_hi'), val('talks.image_mb'), val('talks.laser_ms')) == (.7, .3, .7, 5, 1500)
    assert set_val('talks.phones', 900) == 300 and {'bind', 'join_code', 'rate', 'body', 'room_headers'} <= set(FIXED)
```

In `tests/test_import_weight.py`, add `abhyasa.talk` to the import line of `test_engine_import_is_light`.

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run nbdev-test --path nbs/17_talk.ipynb; uv run pytest tests/test_settings_table.py tests/test_import_weight.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'talk_data'` (after Task 1's data file: `NameError: name 'talk_from_walk' is not defined`), and `KeyError: 'talks.choice'`.

- [ ] **Step 3: Implement** the interfaces in `nbs/17_talk.ipynb` and the rows in `nbs/16_settings.ipynb`.
  - The notebook reads as a document: "What a talk is", "Slides and beats", "Questions for the room", "A talk from a walk", "Store calls", each with a short lead.
  - `check_talk` collects problems slide by slide in slide order; one slide can give more than one problem. The image id rule is spec 7.3.
  - `ask_from_gate`: walk the spec blocks (nested `blocks` too) for the gate id. Options: a list, or `{"from": path}` read from `spec['state']` by dotted path. Answer: `{"is": v}`, or a dotted path read from `spec['state']`. When a path is not in `spec['state']`, return None. The answer must be one of the options. Draw `prompt` with `str.format_map` on the state values in `{name}` form, and keep a `{…}` that has no value as it is.
  - `talk_from_walk` follows spec 8. The demo of a step is `lr.demo_for(slug, 'order' if kind == 'order' else None)`; take the first gate of its spec for which `ask_from_gate` gives a question; with none, use `ask_from_check`. The short-check calls run one after the other.
  - `put_talk` saves the talk text as `f"Talk: {title} ({id})\n\nSlides: {titles}"`, as `put_journey` does.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run nbdev-prepare && uv run nbdev-test --path nbs/17_talk.ipynb && uv run pytest -q`
Expected: PASS; the whole suite still passes (`test_groups_in_order` lists `talks` after `walks`).

- [ ] **Step 5: Commit**

```bash
git add nbs/17_talk.ipynb nbs/sidebar.yml nbs/16_settings.ipynb abhyasa/talk.py abhyasa/settings.py abhyasa/_modidx.py tests/talk_data.py tests/test_settings_table.py tests/test_import_weight.py
git commit -m "Add the talk engine: the deck shape, its checks, and a talk made from a walk"
```

---

### Task 2: The public deck, the run log, the weak ideas and the recap file

Spec 7.7 to 7.9, 13, 17.2, 17.3.

**Files:**
- Modify: `nbs/17_talk.ipynb` (new sections "What the room sees", "The run log", "After the talk")
- Generated: `abhyasa/talk.py`, `abhyasa/_modidx.py`

**Interfaces:**
- Consumes: Task 1 `talk_from_walk`, `public_ask`, `check_talk`; `Learning.vault.assets()`.
- Produces:
  - `IMAGE_TYPES = {b'\x89PNG\r\n\x1a\n': 'image/png', b'\xff\xd8\xff': 'image/jpeg', b'GIF87a': 'image/gif', b'GIF89a': 'image/gif'}` plus webp (`RIFF` at 0 and `WEBP` at 8); `image_type(b:bytes) -> str|None`.
  - `asset_resolver(lr) -> Callable[[str], Path|None]` — spec 7.3.
  - `public_deck(t, resolve) -> AttrDict(title, slides, images)` — spec 7.7; each slide has exactly `id, kind, title, section, passage, figure, ask`; an image over `val('talks.image_mb')` MB is left out.
  - `new_run(t, now:float=None) -> dict` — spec 7.8; `id = 'run-' + 8 hex`, `key = 16 hex` (`secrets.token_hex(8)`), `at = dict(slide=<first idea id>, beat=1, blank=False, pane=None, ask=None)`, `shown=[dict(slide=<first>, at=now, secs=0.)]`.
  - `log_go(run, slide:str, beat:int, now:float)`; `log_round(run, slide, kind, counts:list, n:int, **extra)` (raises `ValueError('a question has at most two rounds')` on a third); `log_main(run, slide, kind, main:int)`; `log_question(run, text, at, shown=False, note='') -> dict` (id `q1`, `q2` …); `log_beside(run, slug, slide, at, secs)`; `end_run(run, now)`.
  - `Learning.put_run(r)`, `Learning.run(rid) -> dict|None`, `Learning.runs(tid) -> L` (newest first). Kind `talk-run`, source `_src('run', rid)`.
  - `share_right(ask, round) -> float|None`; `is_split(ask, round, lo=None, hi=None) -> bool` (defaults `talks.split_lo`, `talks.split_hi`; inclusive; False for `n == 0` and for kinds with no answer).
  - `weak(t, run, below=None) -> list[dict]`; `recap(t, run) -> AttrDict(unsure, slides, questions, beside, follow)`.
  - `recap_html(t, run, resolve) -> str` — one file: inline style that uses the token names with the Paper light values, images as `data:` URLs, each question with the right answer marked "✓ Right" and the share as `f'{round(100 * share)}% right'` for each round, the kept questions (`shown=True`) with their notes. No script, no speaker notes. All text through `html.escape`.

- [ ] **Step 1: Write the failing tests** (at the end of `nbs/17_talk.ipynb`)

```python
# the public deck has no notes, no answers, no demo and no path; a figure comes by its hash
lr = temp_learning(); jid = talk_walk(lr); t = talk_from_walk(lr, Fake(TALK_RULES), jid)
pub, h = public_deck(t, asset_resolver(lr)), hashlib.sha256(PNG).hexdigest()
assert all(set(s) == {'id', 'kind', 'title', 'section', 'passage', 'figure', 'ask'} for s in pub.slides)
assert pub.slides[1]['figure'] == h and pub.images == {h: (PNG, 'image/png')}
assert pub.slides[2]['ask'] == dict(kind='choice', q='T goes from 1 to 2. What happens to the share of Paris?', options=['It rises', 'It falls', 'It stays the same'])
js = json.dumps(pub.slides)
assert 'Softmax makes weights' not in js and '"answer"' not in js and 'softmax-temperature' not in js and '/Users/' not in js and '/tmp/' not in js
```

```python
# a path out of the assets, or a file that is not an image, gives no figure
t2 = deepcopy(t); t2.slides[1]['show']['figure'] = 'asset:../vault.db'
assert public_deck(t2, asset_resolver(lr)).slides[1]['figure'] is None
(lr.vault.assets('attention')/'images'/'fake.png').write_bytes(b'<script>alert(1)</script>')
t2.slides[1]['show']['figure'] = 'asset:attention/images/fake.png'
assert public_deck(t2, asset_resolver(lr)).images == {}
```

```python
# the run log: the time on each slide, the rounds, the hands, the side pane and the questions
r = new_run(t, now=100.)
assert r['id'].startswith('run-') and len(r['key']) == 16 and r['at'] == dict(slide='s1', beat=1, blank=False, pane=None, ask=None)
log_go(r, 's2', 1, now=160.); log_go(r, 's2', 2, now=170.); log_go(r, 's3', 1, now=400.)
assert r['shown'] == [dict(slide='s1', at=100., secs=60.), dict(slide='s2', at=160., secs=240.), dict(slide='s3', at=400., secs=0.)]
assert r['at']['slide'] == 's3' and r['at']['beat'] == 1
log_main(r, 's1', 'choice', 1)
log_round(r, 's2', 'choice', [20, 2, 1, 1], 24); log_round(r, 's2', 'choice', [22, 1, 1, 0], 24)
test_fail(lambda: log_round(r, 's2', 'choice', [1, 1, 1, 1], 4), contains='at most two rounds')
log_round(r, 's3', 'choice', [11, 10, 4], 25)
log_beside(r, 'softmax', 's3', at=420., secs=120.)
q = log_question(r, 'Is √dk the best number?', at=430., shown=True, note='It keeps the variance near 1.')
end_run(r, now=1300.); lr.put_run(r)
assert q['id'] == 'q1' and r['ended'] == 1300. and r['shown'][-1]['secs'] == 900. and lr.runs(t.id)[0]['id'] == r['id']
```

```python
# weak ideas: the last round below 0.7, or hands that chose a wrong option
w = weak(t, r)
assert [x['slide'] for x in w] == ['s1', 's3']
assert w[1] == dict(slide='s3', title='Scaling by the root of dk', share=.4, top_wrong='It rises', n=25, main=None)
assert (w[0]['share'], w[0]['main'], w[0]['top_wrong']) == (None, 1, 'The largest score only')
assert is_split(t.slides[2]['ask'], dict(counts=[11, 10, 4], n=25)) and not is_split(t.slides[1]['ask'], dict(counts=[22, 1, 1, 0], n=24))
assert not is_split(t.slides[2]['ask'], dict(counts=[0, 0, 0], n=0))
rc = recap(t, r)
assert rc.follow == ['sequential-computation', 'scaling-by-the-root-of-dk'] and rc.beside == [dict(slug='softmax', slide='s3', at=420., secs=120.)]
assert rc.questions[0]['text'] == 'Is √dk the best number?' and len(lr.attempts(limit=1000)) == 0   # the room is not the owner
```

```python
# the recap file: no script, no notes, the figures inline, the right answers and the shares, and text from the room escaped
log_question(r, '<img src=x onerror=alert(1)>', at=440., shown=True)
page = recap_html(t, r, asset_resolver(lr))
assert '<script' not in page.lower() and 'src="http' not in page and 'Softmax makes weights' not in page
assert 'data:image/png;base64,' in page and '✓ Right' in page and '40% right' in page and 'It keeps the variance near 1.' in page
assert '<img src=x' not in page and '&lt;img src=x onerror=alert(1)&gt;' in page
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run nbdev-test --path nbs/17_talk.ipynb`
Expected: FAIL with `NameError: name 'public_deck' is not defined`.

- [ ] **Step 3: Implement** the interfaces in the notebook.
  - `public_deck` builds each slide from the allowed fields only. `passage` is `show.passage` only when the slide has the beat `passage` or no beats.
  - `log_go` adds the time since the last move to the last `shown` entry, then adds a new entry only when the slide changes; one slide can have more than one entry (the presenter can go back).
  - `weak` reads the last round. For hands, `top_wrong` is the option at `main`.
  - `recap_html` order: the title, the date, then for each shown slide its title, passage and figure, its question and result, then the questions from the room.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run nbdev-prepare && uv run nbdev-test --path nbs/17_talk.ipynb && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add nbs/17_talk.ipynb abhyasa/talk.py abhyasa/_modidx.py
git commit -m "Add the public deck, the run log, the weak ideas and the recap file of a talk"
```

---

### Task 3: The stage bundle in core: the checked channel, the laser, the blank screen and the audience style

Spec 9.1, 9.2, 11, 17.5.

**Files:**
- Create: `abhyasa/core/stage.py`, `abhyasa/core/stage.js`, `abhyasa/core/stage.css`, `tests/test_stage.py`
- Modify: `abhyasa/core/__init__.py` (export `stage_assets`)

**Interfaces:**
- Produces:
  - `stage.py`: `STAGE_V = 1`; `STAGE_TYPES = ('go', 'point', 'demo', 'ask', 'result', 'pair', 'pane', 'blank', 'end', 'hello', 'here', 'join', 'room', 'question')`; `STAGE_CASES: list[tuple[dict, bool]]` (Step 1); `PLAN_KEYS`, `TALK_KEYS`, `ROOM_KEYS`, `VOTE_KEYS` and `STAGE_KEYS` (their sum), as `(group, keys, action)` rows (the table below); the task that binds each list adds it to `KEYS`: Task 5 `PLAN_KEYS`, Task 6 `TALK_KEYS`, Task 11 `ROOM_KEYS`, Task 12 `VOTE_KEYS`; `stage_assets() -> tuple` (`asset_css('stage.css')`, `asset_js('stage.js')`).
  - `stage.js` (one global `abhyasaStage`, and `module.exports = abhyasaStage` when `module` exists, so node can load it): `valid(msg) -> bool`, `isLocal(url) -> bool`, `channel(name) -> {send, on, close}`, `audience(el, {ch, draw, fade})`, `presenter(el, ch, {keys})`. Task 4 adds `mirror`.
  - `stage.css`: `.stage` (the 16:9 slide box, the page surface), `.stage h1` 46 px and `.stage .passage` 28 px at a 1280 by 720 window (`calc(46 / 1280 * 100vw)` capped by `calc(46 / 720 * 100vh)`, the same for 28), `.stage-dot` (the laser, `--acc`), `.stage-blank`, `mark.lit`, `.stage.beside` (the slide at the left, the pane at the right), and `@media (prefers-reduced-motion: reduce)` with no fade animation (the dot hides at once).

- [ ] **Step 1: Write the failing tests** (`tests/test_stage.py`)

```python
import json, shutil, subprocess, pytest
from pathlib import Path
from abhyasa.core.stage import STAGE_CASES, STAGE_TYPES, STAGE_V, STAGE_KEYS, stage_assets

JS = Path(__file__).parents[1]/'abhyasa'/'core'/'stage.js'
HARNESS = ("const s = require(process.argv[1]); const cs = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
           "process.stdout.write(JSON.stringify(cs.map(([m]) => s.valid(m))));")

@pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')
def test_each_case_in_node():
    r = subprocess.run(['node', '-e', HARNESS, str(JS)], input=json.dumps(STAGE_CASES), capture_output=True, text=True, check=True)
    assert json.loads(r.stdout) == [ok for _, ok in STAGE_CASES]

def test_cases_cover_each_type():
    assert STAGE_V == 1 and {m['t'] for m, ok in STAGE_CASES if ok} == set(STAGE_TYPES)

def test_stage_keys_are_left_hand():
    plain = {k for g, k, _ in STAGE_KEYS if len(k) == 1}
    assert plain == {'D', 'A', 'Q', 'R', 'E', 'X', 'B', 'G', 'F', 'W', 'C', 'T', 'V', 'S'}   # S: "Talk plan" focus down
    assert ('Talk', 'esc', 'Close the open question, the demo focus or the side pane. It never ends the talk') in STAGE_KEYS

def test_assets_are_registered(mk):
    from fasthtml.common import to_xml
    h = to_xml(stage_assets())
    assert '/assets/' in h and h.count('<script') == 1
```

The key rows (in `stage.py`), with this exact text:

```python
PLAN_KEYS = [('Talk plan', 'W', 'Move the focus to the slide above'), ('Talk plan', 'S', 'Move the focus to the slide below'),
             ('Talk plan', '⇧W ⇧S', 'Move the slide up or down'), ('Talk plan', 'E', 'Change the slide'), ('Talk plan', 'X', 'Take out the slide'),
             ('Talk plan', 'Q', 'Add a pause after the slide'), ('Talk plan', '⌥S', 'Present the talk')]
TALK_KEYS = [('Talk', 'D', 'Next beat, then the next slide'), ('Talk', 'space', 'Next beat, then the next slide'), ('Talk', 'A', 'Back one beat'),
             ('Talk', 'Q', 'Ask the room, or close the question'), ('Talk', 'R', 'Show the result and the right answer'),
             ('Talk', '⌥S', 'The main button: start the talk, ask the room, vote again, end the talk'),
             ('Talk', 'E', 'Go into the demo. Esc comes out'), ('Talk', 'X', 'Laser on or off'), ('Talk', 'B', 'Blank the room screen, and back'),
             ('Talk', 'G', 'Go to a slide: G, then its number'), ('Talk', '1–6', 'With no phones: the option that most hands chose'),
             ('Talk', 'F', 'In the audience window: fill the screen'), ('Talk', '⌥B', 'Learn beside: open a missing idea next to the slide'),
             ('Talk', '⌥Z', 'Back to the slide: close the side pane'),
             ('Talk', 'esc', 'Close the open question, the demo focus or the side pane. It never ends the talk')]
ROOM_KEYS = [('Talk', 'C', 'Show the join code on the room screen, and back'), ('Talk', '⇧C', 'Make a new join code'),
             ('Talk', 'T', 'Lock the room, so no new phones join')]
VOTE_KEYS = [('Talk', 'V', 'Vote again on the closed question'), ('Talk', 'W', 'Show the next question from the room')]
STAGE_KEYS = PLAN_KEYS + TALK_KEYS + ROOM_KEYS + VOTE_KEYS
```

`STAGE_CASES` (in `stage.py`), each `(message, valid)`:

```python
OK = [dict(v=1, t='go', slide='s4', beat=2), dict(v=1, t='point', x=.31, y=.62), dict(v=1, t='point', id='scale'), dict(v=1, t='point', off=True),
      dict(v=1, t='demo', slug='softmax-temperature', state=dict(t=2), gates=dict(hot='done')),
      dict(v=1, t='ask', slide='s3', ask=dict(kind='choice', q='T goes from 1 to 2. What happens to the share of Paris?', options=['It rises', 'It falls', 'It stays the same'])),
      dict(v=1, t='ask', slide='s3', ask=None),
      dict(v=1, t='result', slide='s3', kind='choice', rounds=[dict(counts=[11, 10, 4], n=25)], right=1, main=None),
      dict(v=1, t='pair', on=True, prompt='Talk to your neighbour about your answer.'), dict(v=1, t='pane', url='/w/g-1a2b/0'), dict(v=1, t='pane', url=None),
      dict(v=1, t='blank', on=True), dict(v=1, t='end'), dict(v=1, t='hello'), dict(v=1, t='here'),
      dict(v=1, t='join', url='http://192.168.1.23:5180/j/K7PQ2M', code='K7PQ2M'), dict(v=1, t='join', url=None, code=None),
      dict(v=1, t='room', joined=34, answered=27), dict(v=1, t='question', text='Is √dk the best number?')]
BAD = [dict(v=2, t='go', slide='s4', beat=2), dict(v=1, t='eval', code='alert(1)'), dict(v=1, t='go', slide='s4', beat=-1), dict(v=1, t='go', slide='../x', beat=1),
       dict(v=1, t='go', slide='s4', beat=2, extra=1), dict(v=1, t='point', x=1.5, y=.2), dict(v=1, t='point', id='<b>'),
       dict(v=1, t='pane', url='https://evil.example/'), dict(v=1, t='pane', url='//evil.example'), dict(v=1, t='pane', url='/\\evil.example'),
       dict(v=1, t='pane', url='javascript:alert(1)'),
       dict(v=1, t='ask', slide='s3', ask=dict(kind='choice', q='Q?', options=['a', 'b'], answer=1)),
       dict(v=1, t='ask', slide='s3', ask=dict(kind='choice', q='Q?', options=list('abcdefg'))),
       dict(v=1, t='question', text='x' * 281), dict(v=1, t='join', url='http://evil.example/j/K7PQ2M', code='K7PQ2M'),
       dict(v=1, t='join', url='http://192.168.1.23:5180/j/K7PQ2O', code='K7PQ2O'), dict(v=1, t='blank', on='yes'),
       dict(v=1, t='room', joined=-1, answered=0), dict(v=1, t='demo', slug='x', state=dict(a='x' * 70000), gates={}), [1, 2]]
STAGE_CASES = [(m, True) for m in OK] + [(m, False) for m in BAD]
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/test_stage.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'abhyasa.core.stage'`.

- [ ] **Step 3: Implement.**
  - `valid`: one table of field rules for each `t` (spec 9.2), and a size check (`JSON.stringify(m).length <= 65536`). A join `url` matches `^http://(10\.\d{1,3}|172\.(1[6-9]|2\d|3[01])|192\.168|127\.0)\.\d{1,3}\.\d{1,3}:\d{2,5}/j/[A-HJKMNP-Z2-9]{6}$` and its code equals `code`.
  - `isLocal`: the same three rules as `is_local` in `core/pane.py` (one `/` at the start, not `//`, no backslash or control character).
  - `channel(name)`: `new BroadcastChannel('abhyasa-stage:' + name)`; `send` adds `v: 1`, throws `Error('not a valid stage message')` when `valid` is false; `on(t, fn)` calls `fn` only for valid messages of type `t`.
  - `audience`: draws the blank screen, the laser dot (fades after `fade` ms, default 1500), the lit id (3 s), and the pane (an `iframe` with the URL from the message, only when `isLocal`); sends `hello` at the start and `here` every 2 s; calls `draw(msg)` for `go`, `ask`, `result`, `pair`, `join`, `room`, `question`, `demo`, `end`. Text goes in with `textContent` only.
  - `presenter`: binds the keys of `keys` (an object `code -> function`) on `document` only when `document.documentElement.classList.contains('talk')`, no text box has the focus, and the focus is not inside `[data-rupaka]`; with the laser on, sends `point` from `pointermove` over `el`, at most once for each animation frame; sends `point {off: true}` when the pointer leaves.
  - Every plain key is checked by `e.code` (for example `e.code === 'KeyD'`), digits by `e.key`, so `tests/test_keys.py` can read them.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/test_stage.py tests/test_js_syntax.py -q && uv run pytest -q`
Expected: PASS (`test_keys.py` still passes: Task 6 adds the rows to `KEYS` and the `listed()` change).

Note: `tests/test_keys.py` reads `core/*.js` and checks that the table and the js bind the same letters. So `stage.js` names no `KeyX` in a form that `bound()` reads. The key tables are in `talk.js` (Tasks 5, 6, 11, 12), and `presenter` takes them as `keys`.

- [ ] **Step 5: Commit**

```bash
git add abhyasa/core/stage.py abhyasa/core/stage.js abhyasa/core/stage.css abhyasa/core/__init__.py tests/test_stage.py
git commit -m "Add the stage bundle: a checked channel between two windows, the laser, the blank screen and the audience style"
```

---

### Task 4: The mirrored demo: a mirror on the rupaka 0.0.3 store now, and the ask to the rupaka owner

Spec 10, 17.6. This task does not edit rupaka.

**Files:**
- Modify: `abhyasa/core/stage.js` (add `mirror`)
- Create: `tests/test_stage_mirror.py`

**Interfaces:**
- Consumes: rupaka 0.0.3: `Rupaka.mount(host, spec)` puts the store on `host.rupaka` (`st`, `set(k, v)`, `on(f)`, `spec`); a gate keeps its state in `st.gate[id]` (`'open' | 'pending' | 'done'`); a gate fires `rk-predict` with `detail.settle(saved)`.
- Produces: `abhyasaStage.mirror(host) -> {snapshot() -> {state, gates}, apply(state, gates), watch(fn)}`.
  - `snapshot`: the keys of `host.rupaka.spec.state`, with their values now, and `{id: 'done'}` for each done gate.
  - `apply`: when `window.Rupaka.set` exists, `Rupaka.set(host, state)` and `Rupaka.settle(host, id, null)` for each new done gate; else `host.rupaka.set(k, v)` for each key whose value changed, and for each new done gate `host.rupaka.st.gate[id] = 'done'`, then one `host.rupaka.set('_', (st._ || 0) + 1)` so the blocks after the gate draw.
  - `watch(fn)`: `host.rupaka.on(() => fn(snapshot()))`, at most once each 50 ms.
  - The audience copy marks each `.rk-gate` element `inert`.

- [ ] **Step 1: Write the failing test** (`tests/test_stage_mirror.py`, Playwright; skip when Playwright or its Chromium is not there)

```python
import json, pytest
from pathlib import Path
from rupaka.render import page
from rupaka.spec import gallery

pw = pytest.importorskip('playwright.sync_api')
JS = (Path(__file__).parents[1]/'abhyasa'/'core'/'stage.js').read_text()

def test_mirror_follows_the_presenter_copy():
    spec = gallery()['softmax-temperature']
    with pw.sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page(); pg.set_content(page([spec, spec])); pg.add_script_tag(content=JS)
            pg.wait_for_function("document.querySelectorAll('[data-rupaka][data-rk-ready]').length === 2")
            got = pg.evaluate("""() => {
              const [a, b] = document.querySelectorAll('[data-rupaka]'), ma = abhyasaStage.mirror(a), mb = abhyasaStage.mirror(b);
              a.rupaka.set('t', 2); mb.apply(ma.snapshot().state, {});
              a.rupaka.st.gate.hot = 'done'; mb.apply(ma.snapshot().state, ma.snapshot().gates);
              return {t: b.rupaka.st.t, gate: b.rupaka.st.gate.hot, keys: Object.keys(ma.snapshot().state).sort()};
            }""")
            assert got == dict(t=2, gate='done', keys=['logits', 't'])
        finally: b.close()
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/test_stage_mirror.py -q`
Expected: FAIL with `TypeError: abhyasaStage.mirror is not a function`.

- [ ] **Step 3: Implement `mirror`** in `core/stage.js` as in Interfaces. Keep the feature check (`window.Rupaka && Rupaka.set`) in one place, so the store path can go when rupaka ships.

- [ ] **Step 4: Run it to see it pass**

Run: `uv run pytest tests/test_stage_mirror.py tests/test_stage.py -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add abhyasa/core/stage.js tests/test_stage_mirror.py
git commit -m "Add the mirrored demo for the audience window, on the rupaka store"
```

- [ ] **Step 6: Ask the rupaka owner.** Report this text to the controller, who sends it to the rupaka owner. Do not edit rupaka.

> abhyasa's talk mode mirrors a demo from the presenter window to the audience window. It works on rupaka 0.0.3 through `host.rupaka`, but it reaches into the store. Please add these to rupaka 0.0.4:
> 1. `Rupaka.state(el)`: the input keys (the keys of `spec.state`) and their values now.
> 2. `Rupaka.set(el, state)`: set the input keys, run `derive`, and draw. It fires no gate and no `rk-predict`.
> 3. `Rupaka.settle(el, gate, pick)`: open `gate` with `pick` as if the user picked it, and draw the verdict. It fires no `rk-predict`. With `pick` null, mark the gate done with no verdict.
> 4. `Rupaka.mount(el, spec, {save})`: call `save(state)` on each change of an input key.
> 5. `rupaka.poll.of_gate(spec, gate)` and `rupaka.poll.public(p)`, with the contract and tests of `abhyasa.talk.ask_from_gate` and `public_ask` (abhyasa spec 2026-10-29-group-talk, section 17.4), so abhyasa and Leela share one version.
> 6. A Playwright check in rupaka: mount one spec twice, change a slider in one, `set` the other, check that both draw the same; `settle` a gate in both; only the first fires `rk-predict`.

---

### Task 5: The talk block: make a talk from a walk, and change it

Spec 7, 8, 11 ("Talk plan"), screen `shots/a1-deck.png`.

**Files:**
- Create: `abhyasa/blocks/talk/{__init__.py, cfg.py, ui.py, app.py, talk.css, talk.js}`, `tests/blocks/test_talk.py`
- Modify: `abhyasa/core/keys.py` (add `PLAN_KEYS` to `KEYS`, after the "Side pane" rows), `tests/test_keys.py` (`listed()` also takes the plain letters of the groups "Talk" and "Talk plan": `{k for g, k, _ in KEYS if g in ('Graph', 'Talk', 'Talk plan') and re.fullmatch('[A-Z]', k)}`)
- Modify: `abhyasa/blocks/__init__.py` (`NAMES`), `abhyasa/core/hooks.py` (docstring: the hook `walk_actions(j)`), `abhyasa/blocks/walk/ui.py` or `app.py` (the plan page runs `walk_actions`), `abhyasa/blocks/journeys/app.py` (the journey page of a walk runs `walk_actions`), `tests/conftest.py` (fixture `talk_fake`)

**Interfaces:**
- Consumes: Task 1 `talk_from_walk`, `check_talk`, `talk_minutes`, `slide_minutes`, `Learning.put_talk`, `talk`, `talks`; `core.Page`, `Primary`, `Secondary`, `Md`, `asset_css`, `asset_js`, `hooks.hook`, `hooks.run`.
- Produces:
  - `Routes` in `cfg.py`: `new='/talk/new'`, `job='/talk/job'`, `one='/t/{tid}'`, `slide='/t/{tid}/slide'`, `slot='/t/{tid}/slot'`, `start='/t/{tid}/start'`, `present='/t/{tid}/present'`, `audience='/t/{tid}/audience'`, `at='/t/{tid}/at'`, `ask='/t/{tid}/ask'`, `img='/t/{tid}/img/{h}'`, `beside='/t/{tid}/beside'`, `end='/t/{tid}/end'`, `after='/t/{tid}/after'`, `recap='/t/{tid}/recap.html'`, `follow='/t/{tid}/follow'`, and `Routes.of(route, **kw)`. Tasks 6 and 7 fill the later routes; Tasks 11 and 12 add `/t/{tid}/room/...` and `/t/{tid}/q`.
  - `CAPS = ('learning', 'ask', 'pool', 'sources')`.
  - Hook `walk_actions(j)` → the talk block returns a form that posts `jid` to `/talk/new`, with the label "Present this walk".
  - Hook `learning_end` → "Your talks": each talk as a link to `/t/{tid}`, with its slide count and slot.
  - `POST /t/{tid}/slide` with `sid` and `act` in `up`, `down`, `drop`, `edit`, `pause`, `primer`, `questions`. `edit` takes `notes`, `beats` (one beat on each line), `show_passage`, `show_figure`, `show_demo` (`on` or absent), and the ask fields `kind`, `q`, `options` (one on each line), `answer` (an index, or for `order` the indexes joined by commas). `pause` takes `prompt` and `secs` and adds a pause after `sid`. `edit` changes only the fields that the form sends. Each change runs `check_talk`; with a problem, 400 with the first problem as text, and nothing is saved. An unknown `sid` gives 404, an unknown `act` 400.
  - `POST /t/{tid}/slot` with `minutes` (5 to 240).
  - The editor page: `html` has the class `talk`; one row for each slide (`li.slide[data-sid]`) with a small picture, the title, what shows, the question and the minutes; the total line `f'About {talk_minutes(t)} min of a {t.minutes} min slot'`; the line "A change here does not change the walk."; "Room phones" (`phones`, Task 11 uses it); and "Present" as the `Primary` button with ⌥S.
  - `talk.js` "Talk plan" keys: W and S move the focus, ⇧W and ⇧S post `up` and `down`, E opens the slide's edit form, X posts `drop` (after a confirm line), Q posts `pause` with "Talk to your neighbour." and 120 s.

- [ ] **Step 1: Write the failing tests** (`tests/blocks/test_talk.py`)

```python
from talk_data import *

def test_present_this_walk(mk, talk_fake, lr):
    cl = mk(); jid = prep_walk(lr, walk(cl, lr))
    assert 'Present this walk' in cl.get(f'/w/{jid}').text and 'Present this walk' in cl.get(f'/j/{jid}').text
    tid = make_talk(cl, jid); page = cl.get(f'/t/{tid}').text
    assert page.index('Sequential computation') < page.index('Softmax') < page.index('Scaling by the root of dk')
    assert 'About 20 min of a 20 min slot' in page and 'A change here does not change the walk.' in page
    assert 'T goes from 1 to 2' in page and 'Softmax makes weights from scores.' in page   # the editor shows the question and the note

def test_change_the_slides(mk, talk_fake, lr):
    cl = mk(); jid = prep_walk(lr, walk(cl, lr)); before = lr.journey(jid).steps; tid = make_talk(cl, jid)
    cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='up'))
    assert [s['id'] for s in lr.talk(tid).slides] == ['s2', 's1', 's3', 's4', 's5']
    cl.post(f'/t/{tid}/slide', data=dict(sid='s1', act='drop'))
    cl.post(f'/t/{tid}/slide', data=dict(sid='s3', act='pause', prompt='Talk to your neighbour: why divide?', secs=120))
    t = lr.talk(tid)
    assert [s['id'] for s in t.slides] == ['s2', 's3', 's6', 's4', 's5'] and t.slides[2]['kind'] == 'pause' and t.slides[2]['mins'] == 2
    cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='edit', notes='Point at the figure.', beats='passage\nlit:softmax function\nfigure'))
    assert lr.talk(tid).slides[0]['beats'] == ['passage', 'lit:softmax function', 'figure'] and lr.talk(tid).slides[0]['notes'] == 'Point at the figure.'
    r = cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='edit', beats='lit:gradients'))
    assert r.status_code == 400 and 'lights text that is not in the passage' in r.text
    assert lr.talk(tid).slides[0]['beats'] == ['passage', 'lit:softmax function', 'figure']
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s99', act='up')).status_code == 404
    assert cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='fly')).status_code == 400
    cl.post(f'/t/{tid}/slot', data=dict(minutes=40))
    assert 'of a 40 min slot' in cl.get(f'/t/{tid}').text and lr.journey(jid).steps == before   # the walk does not change

def test_talks_on_your_learning_and_search(mk, talk_fake, lr):
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr)))
    page = cl.get('/learning').text
    assert 'Your talks' in page and f'href="/t/{tid}"' in page
    assert cl.get('/search?q=Attention').status_code == 200 and cl.get('/t/nope').status_code == 404
```

`talk_fake` in `tests/conftest.py`: `walk_fake.rules.update(TALK_RULES)`, return it.

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/blocks/test_talk.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'talk_data'` until Task 1, then `'Present this walk' in ...` fails.

- [ ] **Step 3: Implement the block.**
  - `connect` registers every route at its end. `ask` is `for_task(ctx.ask, 'talk')` on each call.
  - `/talk/new` puts `talk_from_walk` on `ctx.pool` and returns a pending card that polls `/talk/job?jid=` every 2 s (as `/walk/job` does). `/talk/job` answers with `HX-Redirect: /t/{tid}` when the job is done, or a message "abhyasa could not make the talk." when it failed.
  - The walk plan page and the journey page of a walk add `*run('walk_actions', j)` beside their actions. No import of the talk block.
  - Look: as `shots/a1-deck.png`: the sections, then the rows; one column; the total against the slot at the top; one main button.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/blocks/test_talk.py tests/test_blocks.py tests/test_js_syntax.py tests/test_keys.py -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add abhyasa/blocks/talk abhyasa/blocks/__init__.py abhyasa/core/hooks.py abhyasa/core/keys.py abhyasa/blocks/walk abhyasa/blocks/journeys/app.py tests/conftest.py tests/blocks/test_talk.py tests/test_keys.py
git commit -m "Add the talk block: make a talk from a walk and change its slides"
```

---

### Task 6: The presenter view, the audience view, hands, and the talk keys

Spec 9, 10, 11, screens `shots/a2-presenter.png`, `a3-audience.png`, `a4-hands.png`.

**Files:**
- Modify: `abhyasa/blocks/talk/{app.py, ui.py, talk.js, talk.css}`, `abhyasa/core/keys.py` (add `TALK_KEYS` to `KEYS`, after `PLAN_KEYS`)
- Test: `tests/blocks/test_talk.py`

**Interfaces:**
- Consumes: Task 2 `public_deck`, `asset_resolver`, `new_run`, `log_go`, `log_main`, `public_ask`, `Learning.put_run`, `run`; Task 3 `stage_assets`, `abhyasaStage.channel`, `audience`, `presenter`; Task 4 `abhyasaStage.mirror`; the demo block's rupaka assets (`/rupaka/rupaka.js`, `/rupaka/rupaka.css`).
- Produces:
  - `POST /t/{tid}/start` → `new_run`, `t.live = run.id`, 303 to `/t/{tid}/present`. A talk with a live run goes to the same run.
  - `GET /t/{tid}/present` — 303 to `/t/{tid}` when `t.live` is None. The page: `html.talk`; `#stage` (the slide now, with `data-slide` and `data-beat` from `run.at`); `#rail`; `#notes` (`Md`); `#next`; `#ask-card` (the one raised card: the question, the right answer for the presenter, the hands buttons 1 to n); `#clock`; the foot line of keys; `data-channel=f'{tid}:{run.key}'`; and the audience URL `f'/t/{tid}/audience?k={run.key}'`.
  - `GET /t/{tid}/audience?k=` — 403 when `k` is not `run.key` of the live run. The page: `html.talk.audience`, every slide of the public deck as `section.stage[data-sid]` (hidden but the one in `run.at`), the figure as `/t/{tid}/img/{hash}`, the demo of each demo slide as a rupaka host, and no top bar.
  - `GET /t/{tid}/img/{h}` — the bytes of the public deck image with hash `h` (`^[0-9a-f]{64}$`), with its media type; else 404.
  - `POST /t/{tid}/at` with `slide`, `beat`, `blank` (`0`/`1`), `pane` (a walk step path or empty) → `log_go`, saves `run.at`; 400 for an unknown slide, a beat out of `1..max(1, len(beats))`, or a pane that is not a walk step path.
  - `POST /t/{tid}/ask` with `slide` and `act`: `open` (sets `run.at.ask`; returns the `ask` stage message as JSON, from `public_ask`), `close` (returns `{v: 1, t: 'ask', slide, ask: null}`), `main` with `main` (hands, `log_main`), `reveal` (returns the `result` message with `right` from the talk), `pair` with `on` (returns the `pair` message with the prompt "Talk to your neighbour for 2 minutes." using `talks.pair_min`). 400 when the slide has no question.
  - `talk.js`: the key table (spec 11) passed to `abhyasaStage.presenter`; each key posts to the server first and sends the stage message from the reply, so the server is always the source of the place; the rk-predict catch on the presenter's demo (`preventDefault()`, `detail.settle(true)`, no post); the audience-window watch ("The audience window is closed. Open it again." after 5 s with no `here`); the Abhyasa.app line (spec 9.4).
  - `KEYS` gains `TALK_KEYS` after `PLAN_KEYS`.

- [ ] **Step 1: Write the failing tests** (add to `tests/blocks/test_talk.py`)

```python
def started(cl, lr):
    "A talk on the prepared walk, started; return (tid, run)."
    tid = make_talk(cl, prep_walk(lr, walk(cl, lr))); cl.post(f'/t/{tid}/start')
    return tid, lr.run(lr.talk(tid).live)

def test_start_and_present(mk, talk_fake, lr):
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr)))
    assert cl.get(f'/t/{tid}/present', follow_redirects=False).headers['location'] == f'/t/{tid}'
    r = cl.post(f'/t/{tid}/start', follow_redirects=False)
    run = lr.run(lr.talk(tid).live)
    assert r.headers['location'] == f'/t/{tid}/present' and run['at']['slide'] == 's1'
    page = cl.get(f'/t/{tid}/present').text
    assert '<nav' not in page and 'Softmax makes weights from scores.' in page and f'/t/{tid}/audience?k={run["key"]}' in page
    assert f'data-channel="{tid}:{run["key"]}"' in page

def test_audience_has_no_notes_and_no_answers(mk, talk_fake, lr):
    cl = mk(); tid, run = started(cl, lr)
    a = cl.get(f'/t/{tid}/audience?k={run["key"]}').text
    assert '<nav' not in a and 'Softmax makes weights' not in a and '"answer"' not in a and 'data-answer' not in a
    assert 'It falls' in a and 'softmax-temperature' in a                                   # the public options, and the demo spec for the live demo
    h = hashlib.sha256(PNG).hexdigest()
    assert f'/t/{tid}/img/{h}' in a and cl.get(f'/t/{tid}/img/{h}').headers['content-type'] == 'image/png'
    assert cl.get(f'/t/{tid}/img/{"0" * 64}').status_code == 404 and cl.get(f'/t/{tid}/img/vault.db').status_code == 404

def test_audience_needs_the_run_key(mk, talk_fake, lr):
    cl = mk(); tid, run = started(cl, lr)
    assert cl.get(f'/t/{tid}/audience?k=0000000000000000').status_code == 403 and cl.get(f'/t/{tid}/audience').status_code == 403

def test_place_survives_a_reload(mk, talk_fake, lr):
    cl = mk(); tid, run = started(cl, lr)
    assert cl.post(f'/t/{tid}/at', data=dict(slide='s3', beat=2)).status_code == 200
    assert lr.run(run['id'])['at'] == dict(slide='s3', beat=2, blank=False, pane=None, ask=None)
    assert 'data-slide="s3" data-beat="2"' in cl.get(f'/t/{tid}/present').text
    assert 'data-slide="s3" data-beat="2"' in cl.get(f'/t/{tid}/audience?k={run["key"]}').text
    for bad in (dict(slide='s9', beat=1), dict(slide='s3', beat=3), dict(slide='s3', beat=0), dict(slide='s3', beat=1, pane='https://evil.example/')):
        assert cl.post(f'/t/{tid}/at', data=bad).status_code == 400, bad
    assert lr.run(run['id'])['at']['slide'] == 's3'

def test_hands_and_result_stay_out_of_learning(mk, talk_fake, lr):
    cl = mk(); tid, run = started(cl, lr); n0 = len(lr.attempts(limit=1000))
    m = cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='open')).json()
    assert m == dict(v=1, t='ask', slide='s3', ask=dict(kind='choice', q='T goes from 1 to 2. What happens to the share of Paris?', options=['It rises', 'It falls', 'It stays the same']))
    cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='main', main=0))
    res = cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='reveal')).json()
    assert res == dict(v=1, t='result', slide='s3', kind='choice', rounds=[], right=1, main=0)
    assert lr.run(run['id'])['asks']['s3'] == dict(kind='choice', rounds=[], main=0, shown=[])
    assert len(lr.attempts(limit=1000)) == n0
    assert cl.post(f'/t/{tid}/ask', data=dict(slide='s4', act='open')).status_code == 400   # the questions slide has no question

def test_talk_keys_are_in_the_table():
    from abhyasa.core.keys import KEYS
    assert ('Talk', 'D', 'Next beat, then the next slide') in KEYS and ('Talk', 'Q', 'Ask the room, or close the question') in KEYS
    assert ('Talk', '⌥S', 'The main button: start the talk, ask the room, vote again, end the talk') in KEYS
    assert not [k for g, k, _ in KEYS if g == 'Talk' and k in ('⌥Q', '⌥R', '⌥X', '⌥E')]   # no new ⌥ key
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/blocks/test_talk.py tests/test_keys.py -q`
Expected: FAIL with 404 on `/t/{tid}/start`, and `test_talk_keys_are_in_the_table` fails.

- [ ] **Step 3: Implement.**
  - The presenter and audience pages use `Page(..., pane=True)` style output with no nav and no crumbs, and add the class `talk` (and `audience`) to `html`.
  - `talk.js` on the presenter page: D or space or Page Down or → posts `at` with the next beat (or the next slide at beat 1); A or Page Up or ← the beat before (or the slide before at its last beat); G starts a 1 s wait for one or two digits; Q posts `ask` `open` or `close`; 1 to n post `main` when a question is open; R posts `reveal`; E focuses the first control of the demo; X toggles the laser; B posts `at` with `blank`; Esc closes the open question, else leaves the demo, else closes the pane, else does nothing. It stops ⌥T, ⌥C, ⌥G, ⌥D and / (`preventDefault` and `stopImmediatePropagation` in a capture listener).
  - A `lit:<text>` beat wraps the first match of the text in the passage with `mark.lit`, in both windows (text nodes only).
  - On a demo slide, the presenter page mounts the demo, `mirror(host).watch(s => ch.send({t: 'demo', slug, ...s}))`; the audience page calls `mirror(host).apply` on each `demo` message.
  - The clock counts from `run.started`, in the presenter view only.
  - The audience page passes `fade=val('talks.laser_ms')` to `abhyasaStage.audience` (a `data-fade` attribute).
  - Look: as `shots/a2-presenter.png` and `a3-audience.png`; dark mode from the theme tokens.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/blocks/test_talk.py tests/test_keys.py tests/test_js_syntax.py -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add abhyasa/blocks/talk abhyasa/core/keys.py tests/blocks/test_talk.py
git commit -m "Add the presenter view and the audience view of a talk, questions with hands, and the talk keys"
```

---

### Task 7: The side pane in a talk, and "After the talk"

Spec 12, 13, screens `shots/a5-beside.png`, `b5-recap.png`.

**Files:**
- Modify: `abhyasa/core/pane.py` (`pane_url(url, talk=False)`), `abhyasa/core/ui.py` (`Page`: with `pane=1&talk=1`, `html` gets `in-pane talk-type`; a helper `in_talk() -> bool`), `abhyasa/core/pane.css` (talk type: larger text in the pane page), `abhyasa/blocks/walk/ui.py` (the step page draws no `#check` slot when `in_talk()`), `abhyasa/blocks/talk/{app.py, ui.py, talk.js, talk.css}`
- Test: `tests/test_pane.py`, `tests/blocks/test_talk.py`

**Interfaces:**
- Consumes: `journey.needs`, `pick_way_down`, `detour`; Task 1 `ask_for_concept`; Task 2 `log_beside`, `end_run`, `recap`, `weak`, `recap_html`; `journey.walk_from_topic`.
- Produces:
  - `pane_url(url, talk=False) -> str|None` — with `talk`, the query also gets `talk=1`.
  - `POST /t/{tid}/beside` with `slide`: the offer (the needs of the slide's concept, the way that `pick_way_down` picks, keys 1 and 2). With `slide`, `slug`, `how` in `primer`, `walk`: `detour(lr, ask, slug, parent={'talk': tid, 'slide': slide}, how=how)`, and the reply JSON `dict(url=f'/w/{sid}/0', pane=pane_url(f'/w/{sid}/0', talk=True), title=name)`. `how='session'` gives 400. With `close=1`: `log_beside` with the time since it opened.
  - `POST /t/{tid}/ask` gains `act='open'` with `pane=1`: the question for the pane's concept (`ask_for_concept`), kept in the run so a second open makes no second call.
  - `POST /t/{tid}/end` → `end_run`, `t.live = None`, the reply sends `end`, 303 to `/t/{tid}/after?run={rid}`.
  - `GET /t/{tid}/after?run=` — the page of spec 13 for that run (default: the newest run).
  - `GET /t/{tid}/recap.html?run=` — `recap_html`, with `Content-Disposition: attachment; filename="<talk slug>-recap.html"`.
  - `POST /t/{tid}/follow` with `run` → `walk_from_topic(lr, ask, goal='Review: ' + ', '.join(names of the weak slides))`, 303 to `/w/{jid}`.
  - `POST /t/{tid}/slide` gains `act='primer'` with `slug` and `sid`: a `primer` slide on concept `slug` before `sid` (title: the name; passage: the statement; no figure; ask from `ask_for_concept`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pane.py
def test_pane_url_in_talk_type():
    assert pane_url('/w/g-1a2b/0', talk=True) == '/w/g-1a2b/0?pane=1&talk=1' and pane_url('https://evil.example/', talk=True) is None

def test_walk_step_in_talk_type_has_no_check(mk, walk_fake, lr):
    from walk_data import walk
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    page = cl.get(f'/w/{jid}/1?pane=1&talk=1').text
    assert 'id="check"' not in page and 'talk-type' in page and 'apply a softmax function' in page
    assert not lr.journey(jid).steps[1].get('qid')
```

```python
# tests/blocks/test_talk.py
def test_beside_opens_a_primer_for_the_room(mk, talk_fake, lr):
    cl = mk(); tid, run = started(cl, lr)
    assert 'Softmax' in cl.post(f'/t/{tid}/beside', data=dict(slide='s3')).text      # the needs of idea 3
    d = cl.post(f'/t/{tid}/beside', data=dict(slide='s3', slug='softmax', how='primer')).json()
    sid = d['url'].split('/')[2]
    assert d['pane'] == f'/w/{sid}/0?pane=1&talk=1' and lr.journey(sid).parent == {'talk': tid, 'slide': 's3'}
    assert cl.post(f'/t/{tid}/at', data=dict(slide='s3', beat=1, pane=d['url'])).status_code == 200
    cl.post(f'/t/{tid}/beside', data=dict(close='1'))
    assert lr.run(run['id'])['beside'][0]['slug'] == 'softmax'
    assert cl.post(f'/t/{tid}/beside', data=dict(slide='s3', slug='softmax', how='session')).status_code == 400

def test_end_and_after_the_talk(mk, talk_fake, lr, monkeypatch):
    cl = mk(); tid, run = started(cl, lr)
    cl.post(f'/t/{tid}/ask', data=dict(slide='s1', act='open')); cl.post(f'/t/{tid}/ask', data=dict(slide='s1', act='main', main=1))
    r = cl.post(f'/t/{tid}/end', follow_redirects=False)
    assert r.headers['location'] == f'/t/{tid}/after?run={run["id"]}' and lr.talk(tid).live is None and lr.run(run['id'])['ended']
    page = cl.get(r.headers['location']).text
    assert 'Where the room was unsure' in page and 'Most hands: B (right: A)' in page
    assert 'The answers of the room do not change your own learning.' in page
    f = cl.get(f'/t/{tid}/recap.html?run={run["id"]}')
    assert 'attachment' in f.headers['content-disposition'] and '-recap.html' in f.headers['content-disposition'] and '<script' not in f.text
    goals = []
    monkeypatch.setattr('abhyasa.blocks.talk.app.walk_from_topic', lambda lr, ask, goal, **kw: goals.append(goal) or AttrDict(id='review-ab12'))
    assert cl.post(f'/t/{tid}/follow', data=dict(run=run['id']), follow_redirects=False).headers['location'] == '/w/review-ab12'
    assert goals == ['Review: Sequential computation']
    cl.post(f'/t/{tid}/slide', data=dict(sid='s3', act='primer', slug='softmax'))
    t = lr.talk(tid); assert [s['kind'] for s in t.slides][2:4] == ['primer', 'idea'] and t.slides[2]['title'] == 'Softmax'
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/test_pane.py tests/blocks/test_talk.py -q`
Expected: FAIL with `TypeError: pane_url() got an unexpected keyword argument 'talk'`, and 404 on `/t/{tid}/beside`.

- [ ] **Step 3: Implement.**
  - ⌥B in the presenter view posts `beside` and shows the offer in the presenter window only; 1 and 2 pick; the pick opens `abhyasaPane.open(d.pane, d.title)` and sends `{t: 'pane', url: d.url}`; the audience window opens `pane_url` of it with `talk=1` beside the slide (`.stage.beside`). ⌥Z closes the pane in both windows and posts `beside` with `close=1`.
  - The pane in a talk never nests: the talk block refuses `beside` while a pane is open (409).
  - "After the talk" layout: as `shots/b5-recap.png`. Each unsure item: the title, the share right for each round (or the hands line), the most chosen wrong answer, and one plain line. "Next time: put the <name> primer before idea <n>" for each `beside` entry, with "Add it to the talk".

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/test_pane.py tests/blocks/test_talk.py tests/blocks/test_walk.py tests/blocks/test_detour.py -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add abhyasa/core/pane.py abhyasa/core/ui.py abhyasa/core/pane.css abhyasa/blocks/walk/ui.py abhyasa/blocks/talk tests/test_pane.py tests/blocks/test_talk.py
git commit -m "Open a missing idea beside a slide for the room, and add the page after the talk with the recap file"
```

---

### Task 8: Docs for Option A, and a look in a real browser

**Files:**
- Create: `tools/talk_look.py` (a script, not a test, in the form of `tools/walk_look.py`: a temp vault and settings folder, the app with `Fake` on a free port, Playwright's bundled Chromium, headless, one browser, closed in a `finally`; `--shots` saves screens; `--only` runs named checks)
- Modify: `nbs/index.ipynb` (a short section "Teach a topic to a group"), `README.md` (from `nbdev-prepare`), `CHANGELOG.md` (an entry under the next version), `docs/design-layers.md` (the editor, the presenter view and the audience view in the list of pages)
- Screens: `design/screens/talk-editor.png`, `talk-presenter.png`, `talk-presenter-dark.png`, `talk-audience.png`, `talk-hands.png`, `talk-beside.png`, `talk-after.png`

**Interfaces:**
- Consumes: everything in Tasks 1 to 7.
- Produces: docs, one script and seven screens.

- [ ] **Step 1: Write the failing check.** `tools/talk_look.py` makes the prepared walk (`talk_data.prep_walk`) and a talk, then asserts, at 1280 by 800 for the presenter and 1280 by 720 for the audience:
  - the editor: rows in walk order, W and S move the focus, ⇧S moves the slide, ⌥F still opens the keyboard shortcuts;
  - ⌥S on the editor opens the presenter view; the first D opens the audience window (`context.expect_page`); its URL has `k=`;
  - the audience `h1` is 46 px and the passage 28 px (`getComputedStyle`); no horizontal scroll in either window (`scrollWidth <= innerWidth`);
  - D goes to `s2` beat 1, then beat 2 shows the figure, and a `lit:` beat added in the editor shows `mark.lit` with "softmax function" in both windows;
  - X, then a pointer move over the slide, shows `.stage-dot` in the audience; 2 s with no move hides it;
  - B shows `.stage-blank` in the audience; B again hides it;
  - G then 3 goes to `s3`; E puts the focus in the demo; a change of `t` in the presenter's demo gives the same `host.rupaka.st.t` in the audience;
  - Q shows the question and 3 options in the audience and no "✓ Right"; 1 then R shows "✓ Right" beside "It falls";
  - ⌥B, then 1, opens the Softmax primer in `#rh-pane` in both windows, with `talk=1` in the frame URL and no `#check` in the frame; ⌥Z closes both;
  - a reload of the audience window shows the same slide and beat; closing it shows "The audience window is closed. Open it again." in the presenter within 6 s;
  - from the presenter page, `new BroadcastChannel(<the channel name>).postMessage({v: 1, t: 'pane', url: 'https://evil.example/'})` and `{v: 2, t: 'go', slide: 's1', beat: 1}` change nothing in the audience; a message on a channel with an old run key changes nothing;
  - Esc with nothing open, ⌥T and / leave the presenter on its URL;
  - ⌥S on the last slide ends the talk and shows "After the talk"; the Learning of the app has the same number of attempts as before the talk.

- [ ] **Step 2: Run it to see it fail**

Run: `uv run --all-extras python tools/talk_look.py`
Expected: PASS when Tasks 1 to 7 are right. A FAIL names the element, the size, the key or the message; fix it in `blocks/talk` or `core/stage.*` before Step 3.

- [ ] **Step 3: Write the docs** in STE grade 9: what a talk is; how to make one from a walk; the two windows and how to put the audience window on the projector; the keys; asking the room with hands; the side pane in a talk; the page after the talk and the recap file; that the room's answers do not change your own learning. Run `uv run nbdev-prepare` and look for stale references in `index.ipynb`.

- [ ] **Step 4: Run everything**

Run: `uv run nbdev-prepare && uv run pytest -q && uv run --all-extras python tools/talk_look.py --shots`
Expected: PASS; seven new screens in `design/screens/`.

- [ ] **Step 5: Commit**

```bash
git add nbs/index.ipynb README.md CHANGELOG.md docs/design-layers.md tools/talk_look.py design/screens/talk-*.png
git commit -m "Document talks, and add a browser check and screens of the editor, the two windows and the page after the talk"
```

---

### Task 9: `sabha`: the room server and its security tests

Spec 14.3, 14.4, 15.2, 17.7.

**Files:**
- Create: `abhyasa/sabha/__init__.py` (exports `Room`, `addresses`, `clean_text`, `HOSTILE`, `CODE_ABC`), `abhyasa/sabha/room.py` (the state: codes, tokens, rounds, tally, questions, limits; no web), `abhyasa/sabha/server.py` (`make_app(room) -> Starlette`: the routes and the headers), `abhyasa/sabha/net.py` (`addresses`, `parse_ifconfig`, `private_v4`), `abhyasa/sabha/text.py` (`clean_text`), `abhyasa/sabha/hostile.py` (`HOSTILE`), `abhyasa/sabha/pages.py` (the HTML of the join page and the phone page, as plain strings with `html.escape`; Task 10 fills the phone markup), `tests/sabha/sabha_data.py`, `tests/sabha/test_room.py`, `tests/sabha/test_hostile.py` (no `__init__.py`: a package named `sabha` in `tests/` would hide the real `sabha` package later)
- Modify: `CLAUDE.md` (a third kind of code: `abhyasa/sabha/`, written by hand, imports no `abhyasa`, its own tests in `tests/sabha/`)

**Interfaces:**
- Produces (spec 17.7), with these exact values:
  - `CODE_ABC = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'`; `CODE_LEN = 6`; `WRONG_PER_MIN = 5`; `BLOCK_SECS = 60`; `WRONG_MOST = 50`; `BODY_MOST = 2048`; `QUESTION_MOST = 280`; `WORDS_MOST = 80`; `QUESTIONS_PER_MIN = 3`; `QUESTIONS_HELD = 200`; `EVENT_GAP = .05`; `CSP` and `RECAP_CSP` (the exact strings of spec 14.3).
  - `Room(deck:dict, host:str, port:int=5180, most:int=300, hours:float=3, theme:dict=None, clock=time.monotonic)`: raises `ValueError` for a bind address that is not private IPv4 or `127.0.0.1` (the message names the address and says "private"), and for a deck with a `notes`, `answer` or `src` key at any depth (the message names the key).
  - `room.join(code:str, addr:str) -> str` (a token); raises `sabha.Wrong`, `sabha.Blocked`, `sabha.Locked`, `sabha.Full` (each a `ValueError` with a short STE message).
  - `room.answer(token, value)`, `room.question(token, text) -> dict`; raise `sabha.NoQuestion`, `sabha.TooMany`.
  - `room.port` (the port asked for, then the port in use after `open`), `room.code`, `room.closed`; `room.show(slide_id, beat=1)`; `room.ask(public_ask, round=1)`; `room.close_ask() -> dict(kind, counts, n)` (for `order` also `swap`; for `words` `dict(kind, n, texts)`); `room.reveal(result)`; `room.stats() -> dict(joined, answered, most)`; `room.questions() -> list[dict(id, text, at)]`; `room.pick(qid) -> dict`; `room.lock(on=True)`; `room.new_code() -> str`; `room.share_recap(html)`.
  - `room.open() -> AttrDict(url, code, port)`; `room.close() -> AttrDict(people, rounds=[dict(slide, round, kind, counts, n)], questions=[dict(text, at)])`; `room.now(token=None) -> dict` (`v`, `slide` `{id, title}`, `ask` (public, with `round`), `result`, `pair`, `recap` (bool), `answered` (this token's answer or None)).
  - `make_app(room)`: the routes of spec 14.3. Replies: wrong `Host` 403; cross-site 403; `POST` with a foreign or missing `Origin` 403; no cookie 401; body over 2048 bytes 413; wrong code 403 "This code is not right."; blocked 429; locked 423; full 503; no open question 409; too many questions 429; an expired room 410; any other path 404.
  - `addresses() -> list[AttrDict(name, ip)]` — the private IPv4 addresses of the interfaces, from `/sbin/ifconfig` when it is there (`parse_ifconfig`), else the address of the default route (a UDP socket `connect`, which sends no packet). Never loopback or link-local.
  - `clean_text(s, most) -> str` — spec 14.4.
  - `HOSTILE: list[dict(name, method, path, headers, body, cookie, want)]` with at least: wrong Host (`evil.example`) → 403; DNS rebinding Host (`attacker.example:5180`) → 403; `POST /a` with `Origin: http://evil.example` → 403; `POST /a` with no `Origin` → 403; `POST /a` with no cookie → 401; `GET /now` with `Sec-Fetch-Site: cross-site` → 403; a 3 kB body → 413; `GET /img/..%2f..%2fvault.db` → 404; `GET /img/abc` → 404; `GET /static/room.py` → 404; `GET /static/..%2froom.py` → 404; `GET /vault` → 404; `GET /recap` before it is shared → 404; `POST /q` with `<script>alert(1)</script>` → 201, and the question text kept as that literal text.

- [ ] **Step 1: Write the failing tests**

`tests/sabha/sabha_data.py` (no engine import): `DECK = dict(title='Attention Is All You Need', slides=[dict(id='s1', kind='idea', title='Sequential computation', section='1 Introduction', passage='This inherently sequential nature precludes parallelization within training examples.', figure=None, ask=dict(kind='choice', q='What does softmax give?', options=['Weights', 'The largest score', 'An order'])), dict(id='s2', kind='idea', title='Softmax', section='3.2.1', passage='apply a softmax function', figure=H, ask=None)], images={H: (PNG, 'image/png')})` with `PNG = b'\x89PNG\r\n\x1a\n'` and `H = hashlib.sha256(PNG).hexdigest()`; and `free_port()` (as in `tests/talk_data.py`), `Clock` and `client` below.

```python
# tests/sabha/test_room.py
import re, json, pytest, httpx
from pathlib import Path
from starlette.testclient import TestClient
from abhyasa.sabha import Room, CODE_ABC, clean_text, Wrong, Blocked, Locked, Full
from abhyasa.sabha.server import make_app
from abhyasa.sabha.net import parse_ifconfig, private_v4
from sabha_data import DECK, H, PNG, Clock, client   # Clock: a clock that a test moves; client(room) -> (TestClient with the room's Origin, origin)

def test_sabha_imports_no_abhyasa():
    src = '\n'.join(p.read_text() for p in (Path(__file__).parents[2]/'abhyasa'/'sabha').rglob('*.py'))
    assert not re.search(r'^\s*(from|import)\s+abhyasa\b', src, re.M)

def test_bind_and_deck_rules():
    for bad in ('0.0.0.0', '::', '8.8.8.8'):
        with pytest.raises(ValueError, match='private'): Room(DECK, bad)
    with pytest.raises(ValueError, match='notes'): Room({**DECK, 'slides': [{**DECK['slides'][0], 'notes': 'x'}]}, '127.0.0.1')
    with pytest.raises(ValueError, match='answer'): Room({**DECK, 'slides': [{**DECK['slides'][0], 'ask': {**DECK['slides'][0]['ask'], 'answer': 0}}]}, '127.0.0.1')
    r = Room(DECK, '192.168.1.23'); assert len(r.code) == 6 and set(r.code) <= set(CODE_ABC)

def test_join_answer_and_tally():
    room = Room(DECK, '127.0.0.1', port=5180); cl, o = client(room)
    r = cl.post('/join', data=dict(code=f'{room.code[:3].lower()} {room.code[3:]}'), follow_redirects=False)
    c = r.headers['set-cookie']
    assert r.status_code == 303 and r.headers['location'] == '/now' and 'sabha=' in c and 'HttpOnly' in c and 'SameSite=Strict' in c
    room.show('s1'); room.ask(dict(kind='choice', q='What does softmax give?', options=['Weights', 'The largest score', 'An order']))
    assert cl.post('/a', data=dict(pick=1)).status_code == 204 and cl.post('/a', data=dict(pick=2)).status_code == 204   # a later answer replaces it
    assert room.stats() == dict(joined=1, answered=1, most=1)
    assert room.close_ask() == dict(kind='choice', counts=[0, 0, 1], n=1)
    assert cl.post('/a', data=dict(pick=0)).status_code == 409

def test_events_have_no_answer_before_reveal():
    room = Room(DECK, '127.0.0.1'); room.show('s1'); room.ask(dict(kind='choice', q='Q?', options=['a', 'b']))
    assert 'answer' not in json.dumps(room.now()) and room.now()['result'] is None
    room.close_ask(); room.reveal(dict(kind='choice', rounds=[dict(counts=[0, 1], n=1)], right=1))
    assert room.now()['result']['right'] == 1

def test_code_limits():
    clock = Clock(); room = Room(DECK, '127.0.0.1', clock=clock)
    for _ in range(5):
        with pytest.raises(Wrong): room.join('AAAAAA', '10.0.0.2')
    with pytest.raises(Blocked): room.join(room.code, '10.0.0.2')        # blocked for 60 s, also with the right code
    clock.t += 61; assert room.join(room.code, '10.0.0.2')
    for i in range(45):
        with pytest.raises((Wrong, Blocked)): room.join('AAAAAA', f'10.0.1.{i // 5}')
    with pytest.raises(Locked): room.join(room.code, '10.0.9.9')          # 50 wrong codes lock the joins
    new = room.new_code(); assert room.join(new, '10.0.9.9')
    room.lock()
    with pytest.raises(Locked): room.join(new, '10.0.9.8')
    full = Room(DECK, '127.0.0.1', most=1); full.join(full.code, '10.0.0.1')
    with pytest.raises(Full): full.join(full.code, '10.0.0.3')

def test_questions_are_text_and_limited():
    clock = Clock(); room = Room(DECK, '127.0.0.1', clock=clock); tok = room.join(room.code, '10.0.0.2')
    q = room.question(tok, '  <script>alert(1)</script>\x00\n  is it safe? ')
    assert q['text'] == '<script>alert(1)</script> is it safe?'
    room.question(tok, 'x' * 400); room.question(tok, 'third')
    assert len(room.questions()[1]['text']) == 280
    with pytest.raises(ValueError): room.question(tok, 'fourth in one minute')
    assert clean_text('á \t b', 80) == 'á b' and clean_text(' \x07 ', 80) == ''

def test_headers_routes_and_paths():
    room = Room(DECK, '127.0.0.1'); cl, o = client(room)
    for path in ('/', f'/j/{room.code}', '/nope'):
        r = cl.get(path)
        assert r.headers['content-security-policy'].startswith("default-src 'none'; script-src 'self'") and r.headers['x-content-type-options'] == 'nosniff'
        assert r.headers['referrer-policy'] == 'no-referrer' and r.headers['cache-control'] == 'no-store'
    assert cl.get(f'/img/{H}').content == PNG and cl.get('/img/' + '0' * 64).status_code == 404
    assert cl.get('/static/phone.js').status_code == 200 and cl.get('/static/room.py').status_code == 404
    assert cl.get('/recap').status_code == 404
    room.share_recap('<h1>What we covered</h1>')
    r = cl.get('/recap'); assert r.status_code == 200 and r.headers['content-security-policy'] == "default-src 'none'; img-src data:; style-src 'unsafe-inline'"
    assert cl.post('/join', content=b'code=' + b'A' * 3000, headers={'content-type': 'application/x-www-form-urlencoded'}).status_code == 413
    assert cl.get(f'/j/{room.code}').text.count(room.code) >= 1 and cl.get('/j/<b>').status_code == 404

def test_room_expires():
    clock = Clock(); room = Room(DECK, '127.0.0.1', hours=3, clock=clock); cl, o = client(room)
    clock.t += 3 * 3600 + 1
    assert cl.get('/').status_code == 410 and room.closed

def test_close_keeps_counts_only():
    room = Room(DECK, '127.0.0.1'); tok = room.join(room.code, '10.0.0.2')
    room.show('s1'); room.ask(dict(kind='choice', q='Q?', options=['a', 'b'])); room.answer(tok, 1); room.close_ask()
    room.question(tok, 'Is it safe?'); log = room.close()
    js = json.dumps(log)
    assert log.people == 1 and tok not in js and '10.0.0.2' not in js and log.rounds == [dict(slide='s1', round=1, kind='choice', counts=[0, 1], n=1)]

def test_addresses_are_private_only():
    text = 'lo0: flags=8049<UP>\n\tinet 127.0.0.1 netmask 0xff000000\nen0: flags=8863<UP>\n\tinet 192.168.1.23 netmask 0xffffff00 broadcast 192.168.1.255\nutun3: flags=8051<UP>\n\tinet 100.64.0.7 --> 100.64.0.7\nen5: flags=8863<UP>\n\tinet 169.254.3.4 netmask 0xffff0000\n'
    assert parse_ifconfig(text) == [dict(name='en0', ip='192.168.1.23')]
    assert private_v4('10.1.2.3') and private_v4('172.31.0.1') and not private_v4('172.32.0.1') and not private_v4('8.8.8.8') and not private_v4('127.0.0.1')
```

```python
# tests/sabha/test_hostile.py: the live room on 127.0.0.1
import httpx, pytest
from abhyasa.sabha import Room, HOSTILE
from sabha_data import DECK, free_port

def test_hostile_cases_on_a_live_room():
    room = Room(DECK, '127.0.0.1', port=free_port()); info = room.open()
    try:
        with httpx.Client(base_url=info.url, timeout=5) as ok:
            ok.post('/join', data=dict(code=info.code), headers={'Origin': info.url})
            for case in HOSTILE:
                c = ok if case['cookie'] else httpx.Client(base_url=info.url, timeout=5)
                r = c.request(case['method'], case['path'], headers=case['headers'], content=case['body'])
                assert r.status_code == case['want'], case['name']
        assert room.questions()[-1]['text'] == '<script>alert(1)</script>'
    finally: room.close()
    with pytest.raises(httpx.ConnectError): httpx.get(info.url, timeout=2)
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/sabha -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'abhyasa.sabha'`.

- [ ] **Step 3: Implement.**
  - `room.py` holds all state under one `threading.Lock`. A wrong-code record is `addr -> [times]`; a blocked address has an end time. Tokens map to `{answers: {round_key: value}, questions: [times]}`. The tally counts the latest answer of each token in the round.
  - `server.py`: one pure-ASGI guard in front of the routes (as `LocalOnly` is), for `Host`, `Sec-Fetch-Site`, `Origin`, the body size (the length header, then a counted read), the expiry and the headers on every reply. Routes take fixed paths only; `/img/{h}` and `/static/{name}` look up a dict and never build a file path. `/events` is a `StreamingResponse` of `text/event-stream` that sends `room.now(token)` as one `data:` line each time the room's version changes, at most once each 50 ms, and a comment line each 15 s.
  - `room.open()` runs `uvicorn.Server(uvicorn.Config(make_app(self), host=self.host, port=p, log_level='warning', timeout_keep_alive=5))` on a daemon thread, for `p` from `port` to `port + 9` until one binds; `close()` sets `should_exit` and joins the thread for at most 5 s.
  - `pages.py` writes the join page now: the title, the code box (`maxlength="7"`, `autocomplete="off"`, `inputmode="text"`), "Join", and the line "This room uses plain HTTP. Other people on this Wi-Fi can read what you send." No inline script or style.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/sabha -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add abhyasa/sabha tests/sabha CLAUDE.md
git commit -m "Add sabha, the room server for phones, with its join code, limits and security tests"
```

---

### Task 10: `sabha`: the phone page and the recap on the phones

Spec 14.1 (steps 3 to 8 on the phone), 14.2, screen `shots/b4-phones.png`.

**Files:**
- Create: `abhyasa/sabha/static/phone.js`, `abhyasa/sabha/static/phone.css`
- Modify: `abhyasa/sabha/pages.py` (the phone page markup), `abhyasa/sabha/server.py` (`/static/theme.css` from `Room.theme`), `abhyasa/sabha/room.py` (`theme` check)
- Test: `tests/sabha/test_phone.py`

**Interfaces:**
- Consumes: Task 9 `Room`, `make_app`, `room.now(token)`.
- Produces:
  - The phone page (`GET /now`; 303 to `/` with no cookie): `#slide` (the slide title), `#q` (the question), `#opts` (choice and scale buttons, `button[data-i]`), `#order` (order cards with up and down buttons), `#words` (`textarea maxlength="80"`), `#state` ("Your answer is in. You can change it until the vote closes."), `#result` (the chart: one row for each option, two thin bars, "✓ Right" as text), `#pair` ("Talk to your neighbour."), the tab "Ask the speaker" (`textarea maxlength="280"`, "Send"), the tab "Recap" when it is shared, and the plain HTTP line.
  - `phone.js`: `EventSource('/events')`; draws `room.now(token)` into those parts with `textContent` only; posts answers and questions with `fetch` (same origin); with the stream lost, tries again after 2 s, 4 s, 8 s (at most 8 s).
  - `phone.css`: uses `--bg --fg --ink2 --mute --line --rule --acc --ok --no --serif --head --mono` with Paper light defaults; `theme.css` sets them from `Room.theme`.
  - `Room(theme=...)`: keys must be in that token list and values must match `^#[0-9a-fA-F]{3,8}$` or a font list of `^[A-Za-z0-9 ,"'-]{1,120}$`; else `ValueError`.

- [ ] **Step 1: Write the failing tests** (`tests/sabha/test_phone.py`)

```python
import re
from abhyasa.sabha import Room
from sabha_data import DECK, client

INLINE = re.compile(r'<script(?![^>]*\bsrc=)|\sstyle=|\son[a-z]+=', re.I)

def test_join_page_and_phone_page():
    room = Room(DECK, '127.0.0.1'); cl, o = client(room)
    j = cl.get(f'/j/{room.code}').text
    assert f'value="{room.code}"' in j and 'This room uses plain HTTP. Other people on this Wi-Fi can read what you send.' in j and not INLINE.search(j)
    assert cl.get('/now', follow_redirects=False).headers['location'] == '/'
    cl.post('/join', data=dict(code=room.code))
    p = cl.get('/now').text
    for part in ('id="slide"', 'id="q"', 'id="opts"', 'id="order"', 'maxlength="80"', 'maxlength="280"', 'Ask the speaker', '/static/phone.js'):
        assert part in p, part
    assert not INLINE.search(p) and 'Recap' not in p

def test_theme_values_are_checked():
    import pytest
    assert '--bg: #f4efe6' in client(Room(DECK, '127.0.0.1', theme={'--bg': '#f4efe6'}))[0].get('/static/theme.css').text
    for bad in ({'--bg': 'red;}</style>'}, {'--evil': '#fff'}, {'--serif': 'x; background:url(http://e)'}):
        with pytest.raises(ValueError): Room(DECK, '127.0.0.1', theme=bad)

def test_recap_shows_when_shared():
    room = Room(DECK, '127.0.0.1'); cl, o = client(room); cl.post('/join', data=dict(code=room.code))
    room.share_recap('<h1>What we covered</h1>')
    assert room.now()['recap'] is True and 'Recap' in cl.get('/now').text and 'What we covered' in cl.get('/recap').text
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/sabha/test_phone.py -q`
Expected: FAIL on the missing parts (`id="slide"`) and on `theme`.

- [ ] **Step 3: Implement** the page, the script and the style as in Interfaces. The phone page is one column, large tap targets (at least 44 px), and the page surface with no raised cards except the question.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/sabha tests/test_js_syntax.py -q && uv run pytest -q`
Expected: PASS (`test_js_syntax` also parses `sabha/static/phone.js`).

- [ ] **Step 5: Commit**

```bash
git add abhyasa/sabha tests/sabha/test_phone.py
git commit -m "Add the phone page of the room: join, answer, ask the speaker and read the recap"
```

---

### Task 11: The room in the presenter view: open it, the join screen with the QR code, and live counts

Spec 14.1 (steps 1 to 5), 6.6, screens `shots/b1-join.png`, `b2-presenter-poll.png`.

**Files:**
- Create: `abhyasa/core/vendor/qrcodegen.js` (one MIT file, its license header kept; Nayuki's `qrcodegen` or Kazuhiko Arase's `qrcode-generator`)
- Modify: `abhyasa/blocks/talk/{app.py, ui.py, talk.js, talk.css}`, `abhyasa/core/keys.py` (add `ROOM_KEYS` to `KEYS`: C, ⇧C and T)
- Test: `tests/blocks/test_talk_room.py`

**Interfaces:**
- Consumes: Task 9 and 10 `sabha.Room`, `addresses`; Task 2 `public_deck`, `log_round`, `recap_html`; Task 1 `public_ask`; settings `talks.port`, `talks.phones`, `talks.room_hours`, `talks.nets`.
- Produces:
  - `ROOMS: dict[tid, Room]` in `blocks/talk/app.py`, and `close_all()` registered with `atexit` and on the app's shutdown event.
  - `GET /t/{tid}/room/nets` — the ask: for each address of `sabha.addresses()`, `f'Open the room on {ip} ({name})?'`, the plain HTTP line "The room uses plain HTTP, so other people on this Wi-Fi can read the answers.", and, when the `/24` subnet of the address is not in `talks.nets`, "You have not opened a room on this network before."
  - `POST /t/{tid}/room/open` with `ip` (must be in `sabha.addresses()`, else 400) → `Room(public_deck(t, asset_resolver(lr)), ip, port=val('talks.port'), most=val('talks.phones'), hours=val('talks.room_hours'))`, then `open()`; it adds the subnet to `talks.nets` and returns the `join` stage message `dict(v=1, t='join', url=f'{info.url}/j/{info.code}', code=info.code)`. The phones use the Paper light colours; a theme from the talk is left for later.
  - `GET /t/{tid}/room/state` — JSON for the presenter only: `joined`, `answered`, `counts` of the open round, `n`, `right`, `questions` (waiting), `locked`. The presenter view polls it every 1 s while the room is open.
  - `POST /t/{tid}/room/lock` (T), `POST /t/{tid}/room/code` (⇧C, returns a new `join` message), `POST /t/{tid}/room/close`.
  - The relay: `POST /t/{tid}/at` calls `room.show(slide, beat)`; `ask` `open` calls `room.ask(public_ask(ask), round=1)`; `ask` `reveal` calls `room.close_ask()` (when a round is open), `log_round`, then `room.reveal(result)`. Only these three. `POST /t/{tid}/end` calls `room.close()`, keeps `people` in the run, and removes the room.
  - The audience draws `join` with the QR code (`/vendor/qrcodegen.js`, an SVG `svg.qr`), the address, the code as `K7P Q2M`, the joined count, and the plain HTTP line. C shows and hides it.

- [ ] **Step 1: Write the failing tests** (`tests/blocks/test_talk_room.py`)

```python
import json, httpx, pytest
from fastcore.basics import AttrDict
from talk_data import *
from abhyasa.settings import set_val, val

@pytest.fixture
def room_on_loopback(monkeypatch):
    monkeypatch.setattr('abhyasa.sabha.addresses', lambda: [AttrDict(name='en0', ip='127.0.0.1')])
    set_val('talks.port', p := free_port()); return p

def phone(url, code):
    c = httpx.Client(base_url=url, timeout=5, headers={'Origin': url}); c.post('/join', data=dict(code=code)); return c

def test_open_the_room(mk, talk_fake, lr, room_on_loopback):
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr))); cl.post(f'/t/{tid}/start')
    nets = cl.get(f'/t/{tid}/room/nets').text
    assert 'Open the room on 127.0.0.1 (en0)?' in nets and 'plain HTTP' in nets and 'You have not opened a room on this network before.' in nets
    assert cl.post(f'/t/{tid}/room/open', data=dict(ip='8.8.8.8')).status_code == 400
    j = cl.post(f'/t/{tid}/room/open', data=dict(ip='127.0.0.1')).json()
    try:
        assert j == dict(v=1, t='join', url=f'http://127.0.0.1:{room_on_loopback}/j/{j["code"]}', code=j['code'])
        assert '127.0.0' in val('talks.nets') and 'not opened a room' not in cl.get(f'/t/{tid}/room/nets').text
        ph = phone(j['url'].split('/j/')[0], j['code'])
        assert cl.get(f'/t/{tid}/room/state').json()['joined'] == 1
        cl.post(f'/t/{tid}/at', data=dict(slide='s3', beat=1)); cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='open'))
        assert ph.post('/a', data=dict(pick=1)).status_code == 204
        st = cl.get(f'/t/{tid}/room/state').json()
        assert (st['counts'], st['n'], st['right']) == ([0, 1, 0], 1, 1)
        cl.post(f'/t/{tid}/room/lock')
        assert httpx.post(j['url'].split('/j/')[0] + '/join', data=dict(code=j['code']), headers={'Origin': j['url'].split('/j/')[0]}).status_code == 423
        assert cl.post(f'/t/{tid}/room/code').json()['code'] != j['code']
    finally: cl.post(f'/t/{tid}/room/close')

def test_room_rounds_stay_out_of_learning(mk, talk_fake, lr, room_on_loopback):
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr))); cl.post(f'/t/{tid}/start'); n0 = len(lr.attempts(limit=1000))
    j = cl.post(f'/t/{tid}/room/open', data=dict(ip='127.0.0.1')).json(); base = j['url'].split('/j/')[0]
    ph = phone(base, j['code'])
    cl.post(f'/t/{tid}/at', data=dict(slide='s3', beat=1)); cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='open')); ph.post('/a', data=dict(pick=1))
    cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='reveal'))
    rid = lr.talk(tid).live
    assert lr.run(rid)['asks']['s3']['rounds'] == [dict(counts=[0, 1, 0], n=1)] and len(lr.attempts(limit=1000)) == n0
    cl.post(f'/t/{tid}/end')

def test_room_closes_at_the_end(mk, talk_fake, lr, room_on_loopback):
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr))); cl.post(f'/t/{tid}/start'); rid = lr.talk(tid).live
    j = cl.post(f'/t/{tid}/room/open', data=dict(ip='127.0.0.1')).json(); base = j['url'].split('/j/')[0]; phone(base, j['code'])
    cl.post(f'/t/{tid}/end')
    assert lr.run(rid)['people'] == 1
    with pytest.raises(httpx.ConnectError): httpx.get(base, timeout=2)

def test_close_all_on_shutdown(mk, talk_fake, lr, room_on_loopback):
    from abhyasa.blocks.talk.app import ROOMS, close_all
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr))); cl.post(f'/t/{tid}/start')
    base = cl.post(f'/t/{tid}/room/open', data=dict(ip='127.0.0.1')).json()['url'].split('/j/')[0]
    close_all()
    assert not ROOMS
    with pytest.raises(httpx.ConnectError): httpx.get(base, timeout=2)
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/blocks/test_talk_room.py -q`
Expected: FAIL with 404 on `/t/{tid}/room/nets`.

- [ ] **Step 3: Implement.**
  - At "Present" with `phones=True`, the presenter view shows the nets ask before the first slide; "Not now" goes on with hands.
  - The presenter's question card (`shots/b2-presenter-poll.png`): the first vote line `f'First vote · {n} of {joined} answered'`, a bar for each option, "Only you see the counts and the right answer (B). The room sees nothing until you show it."; the audience shows only the `room` message (`f'{answered} of {joined} answered'`).
  - The vendored file: keep its license header; serve it from `/vendor/`; `tests/test_js_syntax.py` skips `vendor`, so no change there.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/blocks/test_talk_room.py tests/blocks/test_talk.py tests/sabha -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add abhyasa/core/vendor/qrcodegen.js abhyasa/blocks/talk abhyasa/core/keys.py tests/blocks/test_talk_room.py
git commit -m "Open the room for phones from the presenter view, with the join screen, the QR code and live counts"
```

---

### Task 12: Vote twice, questions from the room, words answers, and the recap on the phones

Spec 7.8, 14.1 (steps 6 to 8), 14.4, screen `shots/b3-result.png`.

**Files:**
- Modify: `abhyasa/blocks/talk/{app.py, ui.py, talk.js, talk.css}`, `abhyasa/core/keys.py` (add `VOTE_KEYS` to `KEYS`: V and W)
- Test: `tests/blocks/test_talk_room.py`

**Interfaces:**
- Consumes: Task 2 `is_split`, `log_round`, `log_question`, `recap_html`; Task 11 `ROOMS`, the relay.
- Produces:
  - `POST /t/{tid}/ask` acts: `vote2` (closes round 1 with `log_round`, sends `pair` with the prompt "Talk to your neighbour about your answer.", returns it), `round2` (opens round 2 on the room: `room.ask(public_ask(ask), round=2)`), `again` (V: the same as `round2` on a closed question that has one round). A third round gives 400. Nothing starts round 2 except `round2` and `again`.
  - The main button of the question card, from `is_split` on the open round: split → "Talk, then vote again ⌥S" (`vote2`); after `vote2` → "Start the second vote ⌥S" (`round2`); else "Show the result ⌥S" (`reveal`). R always reveals.
  - `POST /t/{tid}/q` with `act`: `show` with `qid` (`room.pick`, `log_question(..., shown=True)`, returns `dict(v=1, t='question', text=<the text>)`), `hide` (returns `text=None`), `note` with `qid` and `note` (plain text, at most 500 characters, kept on the run question).
  - Words answers: `room/state` lists the texts of the open words round for the presenter; `POST /t/{tid}/ask` `act='word'` with `i` shows one (adds it to `asks[slide]['shown']` and sends it as a `question` message). The run keeps only the shown texts.
  - `POST /t/{tid}/room/recap` → `room.share_recap(recap_html(t, run, asset_resolver(lr)))`.

- [ ] **Step 1: Write the failing tests** (add to `tests/blocks/test_talk_room.py`)

```python
def test_vote_twice_starts_only_on_the_key(mk, talk_fake, lr, room_on_loopback):
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr))); cl.post(f'/t/{tid}/start')
    j = cl.post(f'/t/{tid}/room/open', data=dict(ip='127.0.0.1')).json(); base = j['url'].split('/j/')[0]
    try:
        phones = [phone(base, j['code']) for _ in range(5)]
        cl.post(f'/t/{tid}/at', data=dict(slide='s3', beat=1)); cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='open'))
        for ph, pick in zip(phones, [0, 0, 1, 1, 2]): ph.post('/a', data=dict(pick=pick))
        assert 'Talk, then vote again' in cl.get(f'/t/{tid}/present').text      # 2 of 5 right: a split vote
        assert cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='vote2')).json() == dict(v=1, t='pair', on=True, prompt='Talk to your neighbour about your answer.')
        rid = lr.talk(tid).live
        assert lr.run(rid)['asks']['s3']['rounds'] == [dict(counts=[2, 2, 1], n=5)]
        assert phones[0].post('/a', data=dict(pick=1)).status_code == 409                 # no second vote until the key
        assert 'Start the second vote' in cl.get(f'/t/{tid}/present').text
        cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='round2'))
        for ph in phones: ph.post('/a', data=dict(pick=1))
        res = cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='reveal')).json()
        assert res['rounds'] == [dict(counts=[2, 2, 1], n=5), dict(counts=[0, 5, 0], n=5)] and res['right'] == 1
        assert cl.post(f'/t/{tid}/ask', data=dict(slide='s3', act='again')).status_code == 400   # two rounds at most
    finally: cl.post(f'/t/{tid}/room/close')

def test_question_html_stays_text(mk, talk_fake, lr, room_on_loopback):
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr))); cl.post(f'/t/{tid}/start')
    j = cl.post(f'/t/{tid}/room/open', data=dict(ip='127.0.0.1')).json(); base = j['url'].split('/j/')[0]
    try:
        phone(base, j['code']).post('/q', data=dict(text='<b>Is √dk the best?</b>'))
        qid = cl.get(f'/t/{tid}/room/state').json()['questions'][0]['id']
        page = cl.get(f'/t/{tid}/present').text
        assert '&lt;b&gt;Is √dk the best?&lt;/b&gt;' in page and '<b>Is √dk the best?</b>' not in page
        assert cl.post(f'/t/{tid}/q', data=dict(act='show', qid=qid)).json() == dict(v=1, t='question', text='<b>Is √dk the best?</b>')
        cl.post(f'/t/{tid}/q', data=dict(act='note', qid=qid, note='<script>x</script>'))
        rid = lr.talk(tid).live
        assert lr.run(rid)['questions'][0]['note'] == '<script>x</script>'
        cl.post(f'/t/{tid}/end')
        after = cl.get(f'/t/{tid}/after?run={rid}').text
        assert '&lt;script&gt;x&lt;/script&gt;' in after and '<script>x</script>' not in after
    finally: cl.post(f'/t/{tid}/room/close')

def test_words_answers_keep_only_the_shown_ones(mk, talk_fake, lr, room_on_loopback):
    cl = mk(); tid = make_talk(cl, prep_walk(lr, walk(cl, lr)))
    cl.post(f'/t/{tid}/slide', data=dict(sid='s2', act='edit', kind='words', q='Why divide by √dk?'))
    cl.post(f'/t/{tid}/start')
    j = cl.post(f'/t/{tid}/room/open', data=dict(ip='127.0.0.1')).json(); base = j['url'].split('/j/')[0]
    try:
        a, b = phone(base, j['code']), phone(base, j['code'])
        cl.post(f'/t/{tid}/at', data=dict(slide='s2', beat=1)); cl.post(f'/t/{tid}/ask', data=dict(slide='s2', act='open'))
        a.post('/a', data=dict(text='It keeps the variance near one')); b.post('/a', data=dict(text='private words'))
        texts = cl.get(f'/t/{tid}/room/state').json()['words']
        cl.post(f'/t/{tid}/ask', data=dict(slide='s2', act='word', i=texts.index('It keeps the variance near one')))
        cl.post(f'/t/{tid}/ask', data=dict(slide='s2', act='reveal'))
        run = lr.run(lr.talk(tid).live)
        assert run['asks']['s2']['shown'] == ['It keeps the variance near one'] and 'private words' not in json.dumps(run)
        cl.post(f'/t/{tid}/room/recap')
        assert 'Attention Is All You Need' in httpx.get(base + '/recap', timeout=5, cookies=a.cookies).text
    finally: cl.post(f'/t/{tid}/room/close')
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/blocks/test_talk_room.py -q`
Expected: FAIL with 400 on `act='vote2'`.

- [ ] **Step 3: Implement.**
  - The result chart in the audience (`shots/b3-result.png`): spec 14.2 "The chart". The first vote is an outline bar, the second a filled bar, "✓ Right" as text with `--ok`, the percentages in the text ink, a legend for two votes, a `title` on each bar.
  - W shows the oldest waiting question (`act='show'`), and W again hides it and shows the next.
  - The presenter view draws room text as FT text nodes, never `Md` or `NotStr`. `talk.js` sets it with `textContent`.

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/blocks/test_talk_room.py tests/blocks/test_talk.py tests/sabha -q && uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add abhyasa/blocks/talk abhyasa/core/keys.py tests/blocks/test_talk_room.py
git commit -m "Let the room vote twice when the presenter asks, send questions, and read the recap on their phones"
```

---

### Task 13: A security review, docs for Option B, a look with phones in a real browser, and a trial on real phones

**Files:**
- Modify: `tools/talk_look.py` (a `room` part, run with `--only room`), `nbs/index.ipynb` (the room: how to open it, the join code, the plain HTTP warning, what the room can and cannot see, that it closes at the end), `README.md`, `CHANGELOG.md`
- Screens: `design/screens/talk-join.png`, `talk-poll.png`, `talk-result.png`, `talk-result-dark.png`, `talk-phones.png`, `talk-recap.png`
- Create (by the controller, after the trial): `design/screens/trial/talk-phones.md`

**Interfaces:**
- Consumes: everything above.
- Produces: review fixes (each with its own test), docs, the room checks and six screens.

- [ ] **Step 1: Write the failing check.** The `room` part of `tools/talk_look.py` patches `abhyasa.sabha.addresses` to `127.0.0.1`, opens the room, and asserts:
  - the audience join screen has `svg.qr` with at least one `path` or `rect`, the code as two groups of three (`/^[A-HJKMNP-Z2-9]{3} [A-HJKMNP-Z2-9]{3}$/`), and the plain HTTP line;
  - a second browser context at 390 by 844 (a phone) opens the join URL, taps "Join" and sees the slide title; the page has no console message about the Content Security Policy;
  - Q shows the question on the phone and in the audience, with no "✓ Right" anywhere; a tap on "It rises" shows "1 of 1 answered" in the audience and the count in the presenter card within 2 s;
  - with 2 of 5 phones right, the main button is "Talk, then vote again"; after it, the phones show "Talk to your neighbour." and no options until "Start the second vote"; R then shows both votes in the audience and on the phones, with "✓ Right" beside "It falls";
  - a question `<b>Is it safe?</b>` from a phone shows in the presenter as that literal text, and W shows it in the audience as literal text (no `b` element in the audience);
  - ⌥S on the last slide ends the talk; the phone page then fails to load (the room is closed); the Learning of the app has the same number of attempts as before.

- [ ] **Step 2: Run it to see it fail**

Run: `uv run --all-extras python tools/talk_look.py --only room`
Expected: PASS when Tasks 9 to 12 are right. A FAIL names the element or the reply; fix it before Step 3.

- [ ] **Step 3: Security review.** The controller sends Review Focus 2, 4 and 5, spec 14.3, 14.4 and 15, and the diff of `abhyasa/sabha/`, `abhyasa/core/stage.js` and `abhyasa/blocks/talk/` to a fresh reviewer. The reviewer checks: the bind address; the join code (alphabet, `secrets`, the limits); the rate limits under many addresses; that no route reads a file from input (path traversal); the body and text limits; that the run log and `room.close()` keep no token, address or unshown words answer; CSRF and `Origin` for every `POST` on the room port and for the presenter routes on loopback; every `BroadcastChannel` message type against `valid`; and every place that draws room text (no `Md`, `NotStr` or `innerHTML`). Each finding gets a fix and a test in the task's own test file, in its own commit.

- [ ] **Step 4: Write the docs** in STE grade 9 (the room section above), and run everything:

Run: `uv run nbdev-prepare && uv run pytest -q && uv run --all-extras python tools/talk_look.py --shots`
Expected: PASS; six new screens.

- [ ] **Step 5: Commit**

```bash
git add tools/talk_look.py nbs/index.ipynb README.md CHANGELOG.md design/screens/talk-*.png
git commit -m "Document the room for phones, and add a browser check and screens with a phone"
```

- [ ] **Step 6: Trial on real phones** (the owner, with the controller; not an agent step). On the owner's Wi-Fi, with two or more real phones (one iPhone, one Android): scan the QR code, join, answer, vote twice, send a question, read the recap, end the talk, and check that the phones can no longer load the room. Note the macOS prompt for incoming connections, the time to join, and any phone that refused a step. The controller writes `design/screens/trial/talk-phones.md`. Each problem gets a small fix with its own test.

---

## Leela handoff

Leela builds its own talk mode on these contracts, with no copy of abhyasa's code. The spec (section 17) has each contract in full.

| part | home | what Leela uses | what Leela adds |
|---|---|---|---|
| deck shape, `check_talk`, `TALK_CASES` | `abhyasa.talk` | the shape and the checks; `TALK_CASES` in its contract test | `talk_from_notebook(nb, path)`; `src={'notebook': path}`; the image scheme `ws:`; `code` slides with `lines:a-b` and `out` beats |
| public deck | `abhyasa.talk.public_deck` | the same, with its own `resolve` for workspace paths | none |
| run log and recap data | `abhyasa.talk` (`new_run`, `log_*`, `weak`, `recap`, `recap_html`) | the same; "After the talk" in Leela | none |
| question from a gate | `abhyasa.talk.ask_from_gate`, later `rupaka.poll.of_gate` | ask the room at a demo gate in a lesson | "What does this print?" from a code cell; the right answer comes from the kernel after the vote |
| stage bundle | `abhyasa/core/stage.js`, `stage.css`, `stage.py` | the channel, the checks, the laser, the blank screen, the audience style, `STAGE_KEYS` | its own `draw` for notebook slides; the place in `localStorage`; a cell output message `{t: 'out'}` after the owner agrees to `v: 2` or a Leela list |
| mirrored demo | rupaka (`Rupaka.set`, `settle`, `state`, `mount(..., {save})`), after the ask of Task 4 | the same, in a lesson notebook demo | none |
| room server | `abhyasa/sabha/`, later the `sabha` package | `Room`, `addresses`, `HOSTILE`, the phone page, through the same calls; its hub guard does not change | its smoke test: open a room on a fixture deck, join, answer, close |
| pane beside a slide | `abhyasa/core/pane.py` contract, plus the `pane` stage message and `talk=1` | the same contract | a kosha lookup page with `pane=1` |
| talk keys | `STAGE_KEYS` | the same keys, after Leela's keymap audit | none |

What Leela builds on top:

1. `talk_from_notebook(nb, path)`: each H2 in a markdown cell starts a slide; a markdown cell is the passage; a code cell is a `code` slide with beats that light line ranges; a rupaka fence is a demo slide; a lesson notebook made from a walk keeps its `step` and its tutor note as the speaker note.
2. Live code on a `code` slide: the presenter runs the cell in the live kernel; the output goes to the audience window after Leela cleans it (text and images only).
3. "What does this print?": the vote, a talk, the second vote, then the run. The room never runs code.
4. A code walkthrough: a file as a talk, with line ranges as beats and a kosha lookup beside the code.
5. Speaker notes from the ramabana agent with the owner's tutor prompt. Notes never go into the public deck.
6. The audience window as a second kavacha window or a browser window on the Leela URL.

Leela does not build a second room server, a second channel, a second deck shape or its own poll logic. When `sabha` moves to its own repo, Leela pins `sabha==Y` and `rupaka==X`, and `test_abhyasa_contract.py` adds `TALK_SCHEMA`, `TALK_CASES`, `check_talk`, `public_deck`, the run log keys and `STAGE_CASES`.
