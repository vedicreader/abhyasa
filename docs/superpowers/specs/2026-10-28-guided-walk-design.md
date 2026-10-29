# The guided walk: learn a paper or a topic, one idea and one check at a time

Date: 28 October 2026. Status: approved by the owner (Option A, on the shared core).
Amended 28 October 2026, approved by the owner: rabbit holes (6.10), a walk from a link (6.11), tool walks (6.12) and a
trial on real material (6.13). Amended again on 28 October 2026 by the owner's decision: 6.12 is now "Open in Leela" (a
link), and code with a library runs in Leela, not in abhyasa.
Design sources: `abhyasa-designs/paper/options.md` ("The shared core", "Option A", "Comparison", "Recommendation"),
mockups `abhyasa-designs/paper/mock/a1-a3` and `paper/shots/a1-add.png`, `a2-walk-code.png`, `a3-walk-demo.png`,
background `abhyasa-designs/research.md`, the modality design `abhyasa-designs/modalities/options.md` (part 4A and
its engine changes), and the rabbit-hole design `abhyasa-designs/rabbit-hole/design.md` with mockups `rabbit-hole/mock/r1-r3`
and `rabbit-hole/shots/r1-offer.png`, `r2-pane.png`, `r3-return.png`. Paths without a folder are in the abhyasa repo.

## 1. Intent

The owner's words: "abhyasa should also allow me to just learn about a topic interactively and after every concept
explained in the paper, it can give me coding tasks or interactive demos to test my understanding and log." It must
work for a paper (a PDF or notes in the vault) and for a plain topic.

Today a source gives only a flat list of concepts (`sources.extract`). The paper's order, its sections, its passages
and its figures are lost. Checks come only as tutor questions, and a demo comes only after a miss. So a paper does not
become a lesson.

The guided walk makes a source into a journey in reading order. Each step shows the passage, the figure if there is
one, two or three plain lines from the tutor, and then one check: a short answer, a predict-first demo, or a code task
that runs in the browser. Every check goes into the log and the learner model, as every question does today. Due ideas
come back on Today with a new kind of check and a link back to the passage.

Why this option: it gives the whole loop (idea, check, log, review) for papers and topics with the least new code and
no rupaka change. It looks like the app the owner knows. The step is data (`read`, `check`), so the two-pane step of
Option B and the map of Option C can come later as views of the same journey.

## 2. Goals

1. A vault document, a pasted text or a topic becomes a walk: a journey whose steps are the ideas in reading order.
2. Each step shows the passage (word for word from the source), the figure (from vault assets), a short tutor note and
   one check card.
3. Three check kinds in this plan: short answer (through `Tutor.ask_on`), predict-first demo (rupaka), and code task
   (run in an isolated process, closed through `Tutor._close`). An order check ("put the steps in order") is a demo
   with a ranklist gate.
4. The way system picks the check: the concept's `ways`, the learner's record per way, and exploration, as today.
5. One log: every check goes through `Learning.record`, with no schema change.
6. Review: due walk ideas come back on Today. The review uses a different way from last time and links to the passage.
7. The shared core (extract fields and the new ways) also holds what the later modality views need, so they do not
   redo it.
8. Rabbit holes: when a step needs an idea that the learner does not have, the learner can learn it beside the step
   (a primer or a short side walk in a side pane) or in its own session, and then come back to the same place with the
   open check and the draft kept.
9. A walk from a link: a paper (a PDF URL or an arXiv id), a docs site (crawled, with a page cap) or a GitHub repo is
   filed in the vault, and one walk is made across the filed pages in reading order.
10. Open in Leela: a walk on a library or a command-line tool (a tool walk) has short-answer and order checks in
    abhyasa, and its code steps link to Leela, which runs code with the library. abhyasa installs no libraries.
11. A trial on real material (a paper, a topic, two docs sites) measures the walk before the owner uses it every day.

## 3. Non-goals (this plan)

- The two-pane step of Option B ("your code drives the demo"), term lighting, and live footnotes.
- The map view of Option C.
- The modality views: playground frames, seeded board, timeline lanes, lenses (`modalities/options.md` 1A, 2A, 3A, 4B).
- New rupaka blocks (an `image` block, `frames`, `diagram`, `code`).
- A code editor library. The editor is a plain text area.
- Sync or sharing. The app stays local and offline, except for the fetches in 6.11, which run only when the learner
  asks.
- Rabbit hole moment 4 (a question typed in the answer box is caught before the grade). Hover cards on terms, notes
  in the pane bar, a "Highlight" tool, and tiles (more than one pane).
- Installing a command-line tool or running it. A walk on a command-line tool never runs a command.
- Installing a library for the learner, tool environments, code with a library, code lookup and an agent tutor. These
  are Leela's (6.12). abhyasa runs only short stdlib exercises.
- A crawl past the page cap, or to pages outside the folder of the given URL.

## 4. Anti-goals (things the walk must never do)

- **No quiz grind.** One check for each idea, never a run of questions on one step. No score, no streak counter, no
  timer on screen. The rail shows done, shaky and now, and nothing more.
- **Never block reading on a check.** The passage, figure and note show at once. The check card loads after them.
  "Next idea" always works: with no check done, it counts as a skip. The rail lets you open any step.
- **No silent answer leaks.** No model answer, rubric, correct option, hidden test or code solution goes into the HTML
  before the learner tries. The tutor note must not answer the check. A demo shows nothing that the gate needs before
  the prediction (rupaka's think rule).
- **No made-up passages.** A passage shows only if it is found word for word in the source. Else the step shows the
  concept statement, marked as the tutor's words.
- **No hot links.** Figures come only from vault assets.
- **No dashboard look.** Calm surfaces: page, raised, sunken (`docs/design-layers.md`).

## 5. Constraints

- Repo rules (`CLAUDE.md`): the engine is the notebooks in `nbs/`; `abhyasa/*.py` engine files (this includes
  `check.py`, `nb.py`, `demo.py` and the new `walk.py`) are generated by `uv run nbdev-prepare`. The web app is blocks
  written by hand (`cfg.py`, `ui.py`, `app.py`, `.css`, `.js`); blocks never import each other and talk through hooks.
- Prose (UI text, prompts, notebooks, docs, commit messages) is ASD-STE100 Simplified Technical English, US grade 9.
- Notebooks read as documents: an intro, short sections, a one-line lead before each code cell, small tests.
- Tests never open the real vault (`~/.vishalakshi/vault.db`) or `~/.config/abhyasa`. Use `temp_learning()` and
  `abhyasa.llm.Fake`.
- Browser checks use Playwright's bundled Chromium, headless, one browser at a time, closed in a `finally`.
- New prompt text is registered in the prompt registry (`prompts.register`), so the owner can change it on Settings.
- Every control has a left-hand key: ⌥S start and "Next idea" (it is the app's "Press the main button" key), ⌥W hint,
  ⌘↵ send or run, 1-9 options, K keep. The side pane: ⌥B open beside, ⌥Z back to the paper, Esc close the pane.
  ⌥F (show the keyboard shortcuts), ⌥D (dictate), ⌥G (strengths) and ⌥E (show me a demo) are taken and the walk never
  binds them. Before a key is chosen, read `abhyasa/core/keys.py`; the task that binds a new key adds it to `KEYS`.
- No new runtime dependency and no new vendored script. abhyasa installs no libraries for learners and runs only
  stdlib exercises (6.12).

## 6. Decided design

### 6.1 Extract keeps the reading order (shared core 1, modality 4A)

`sources.extract` asks for and keeps these fields for each concept, beside the fields of today
(`name, statement, aliases, prereqs`):

| field | where it is kept | meaning |
|---|---|---|
| `section` | provenance entry of this source | the section number and title, such as "3.2.1 Scaled Dot-Product Attention" |
| `order` | provenance entry | the place of the idea in this source (0, 1, 2 ...) |
| `page`, `span` | provenance entry | the page (or None) and `[start, end]` char offsets of the passage in that page's text |
| `passage` | provenance entry | the passage text, at most 600 chars, found word for word in the source |
| `figure` | provenance entry | a path under `vault.assets()` of a figure that the source links near the idea, or None |
| `ways` | concept (union merge) | the ways that fit the idea, names from `METHODS` |
| `moves` | concept (union merge) | the parts that move or change in the idea ("tokens", "weights") |
| `when` | concept | `{start, end, label, era}` for a dated idea, else None |
| `who` | concept (union merge) | the people or characters in the idea |
| `image` | concept | the first figure found for the idea (the picture a timeline card uses later) |
| `visual` | concept | true when `moves` is not empty, so `want_demo` (`demo.py`) at last has a source |

Rules:
- Placement (section, order, page, span, passage, figure) belongs to one source, so it lives in that source's
  provenance entry. Two papers that share a concept do not overwrite each other.
- The concept-level `order` field keeps its meaning of today (a sequence, as in vedicreader lessons). Extract never
  writes paper positions into it.
- The model returns a short `quote` from the text. The code finds it in the page text (white space and case folded).
  If it is not there, `passage` and `span` are empty. The model never supplies offsets.
- The model returns a `figure` link only as it appears in the text (vishalakshi files a PDF as markdown pages with
  image links, `vishalakshi/acquire.py:121`). The code keeps it only when the file exists under `vault.assets()`.
- A source document is read page by page from the vault chunk store, with no 40 000-char cap
  (`Vault.document` cuts at 40 000 by default).
- `EXTRACT_SP` is registered in the prompt registry as `extract`.

### 6.2 The ways (shared core 3, modality 4A)

- `METHODS` gains five ways: `demo` (a predict-first rupaka demo, split off from `diagram`), `order` (put steps in
  order), `playground`, `board`, `timeline`. Each gets a label and a prompt line, registered as `way.<name>` by the
  loop that exists.
- `TEXT_WAYS = ('code', 'maths', 'analogy', 'example', 'diagram', 'words')`: the ways a written question can use.
- `WALK_WAYS = TEXT_WAYS + ('demo', 'order')`: the ways the walk can run now. `playground`, `board` and `timeline`
  are in `METHODS` (so credit, counts and prompts exist), but no check offers them until their views exist.
- `choose(st, subject='', weak=False, rng=None, explore='sometimes', prior=(), allowed=None)`: `allowed` limits the
  candidates. `None` means `TEXT_WAYS`, so a normal session never gets a way it cannot show. An `allowed` with no known
  way falls back to `TEXT_WAYS`. Credit and Beta logic do not change.
- `check_for(c, st, rng=None, explore='sometimes', prior=(), last='') -> AttrDict(way, kind, depth, why)`:
  - candidates: `c.ways ∩ WALK_WAYS`, else `TEXT_WAYS`; `last` (the way of the last check) is left out when another
    candidate is left.
  - A hands-on way of the idea (demo, order or code) comes before its text ways. An idea with no way that a walk can
    show gets a short answer. At most a third of the checks of a walk are hands-on (`MAX_HANDS_ON`); later steps get a
    check in their text ways.
  - kind from way: `demo` → `demo`; `order` → `order`; `code` → `code`; else `short`.
  - depth: `code` is 4 (apply); a short answer is 2 (recall) for a concept with floor below 2, else 3 (explain); a
    demo or order check is 2, and 3 when the learner writes a why (as `record_prediction` does today).
- A demo prediction credits `demo` (today it credits `diagram`). Old attempts keep `diagram`. `playground` gets its
  credit when frames exist.
- `Tutor.teach(another=True)` picks only from `TEXT_WAYS`.
- The Strengths page lists only ways with counts or ways in `WALK_WAYS`.

### 6.3 A walk is a journey (shared core 2)

A walk is a journey with `mode='walk'`. `progress` does not change. Journey fields added:

```python
dict(id, title, goal, subject, steps, created, updated,          # as today
     mode='walk', source=dict(shelf='store', doc_id='…', title='Attention Is All You Need') or None,
     started=None or float, sitting=None or 'session id')
```

A step keeps `slug, status, why` and adds:

```python
read  = dict(shelf='store', doc_id='…', title='…', section='3.2.1 Scaled Dot-Product Attention',
             page=4, span=[812, 1004], text='We compute the dot products …', figure='attention/images/fig2.png')
         # topic walk: dict(src='vault:notes', ref='…', title='…', url='', text='…', section='', figure=None)
check = dict(way='code', kind='code', depth=4, why='your best way here: code, 7 of 9')
read_at = None or float          # the first view; reading is not an attempt
done = None or dict(outcome='solid'|'fragile'|'gap'|'misconception'|'skipped', aid='…', at=float)
qid = None or 'open question id'  # the open check, so a reload does not make a new one
note = None or 'two or three lines from the tutor'
```

A view reads extra keys with `.get`, so later fields (`layout='pair'` for B, `x`, `y` for C) need no migration.

- `journey_from_source(lr, ask, ref, shelf='store', subject='') -> AttrDict`: extract (6.1), then one step for each
  concept of this source, sorted by provenance `order`. A concept you know at depth 4 or more gets `status='known'`.
  It saves the journey at once (not started).
- `journey_from_text(lr, ask, text, title, subject='')`: the same for pasted text, with `read.text` from the text.
- `walk_from_topic(lr, ask, goal, who='', sources=None)`: `plan` (which now also returns `ways` per step), then each
  step gets `read` from the first grounded passage that names the idea (`ground.ground` with `must=`), or no `read`,
  and its `check` from `check_for`.
- `walk_state(j) -> AttrDict(steps, current, done, total, sections)`: rail data from `done` and `read_at`. `current` is
  the first step with no `done` and a status of `todo`.

### 6.4 The step runtime (engine module `walk.py`, notebook `15_walk.ipynb`)

- `tutor_note(lr, ask, j, i) -> str`: two or three sentences (at most 60 words) on the idea, from the passage and the
  statement, kept on the step. Prompt `walk.note`, registered. The prompt says: do not state the answer to a question
  on this idea; end with what to look for next.
- `Tutor.ask_on(..., method=None, meta=None)`: `method` skips `choose` and uses that way; `meta` (walk, step, section,
  page) goes into every `record` of that question (each try and the close). The review rule: when not a drill and the
  last final attempt on the concept has a `walk` field, `choose` gets `allowed=TEXT_WAYS` without the last way.
- Short answer: `ask_on(c, depth, why, session=sitting, method=way, meta=meta)`, the question prompt also gets the
  note as "the learner just read this; ask past it".
- Code task: `code_task(tutor, c, session, meta) -> AttrDict(q, stub, fname, tests)` builds the exercise with
  `nb.new_exercise` (the model call and `validate_exercise` with one retry, split out of `Exercise.__init__`), opens
  the question with `kind='code'`, `depth=4`, `method='code'`. `tests` lists the visible test text only.
- `run_code(tutor, qid, source, confidence=70) -> AttrDict`: see 6.6.
- `Session.code(source)` and `Session.noted(a, floor0)`: the sitting log gets code closes and demo predictions, so
  the section summary (`moved`) counts them.

### 6.5 Demo and order checks (shared core 3, Option A)

- The demo is made before the step, not after a miss: when step `i` opens, a background job makes the demo for step
  `i + 1` if its check kind is `demo` or `order` (`make_demo`, which calls `rupaka.agent.author`).
- `make_demo(..., aim='')`: `aim='order'` asks for one gate with a ranklist of 3 to 6 steps and gives the author a
  ranklist example. The aim is kept in the demo meta. `demo_for(concept, aim=None)` can filter by aim.
- If the demo is not ready, the card says so and polls. If the job fails, the step falls back to a short answer in
  the next best text way. The walk never waits on a demo to show the passage.
- `record_prediction(..., kind='demo', method='demo', **meta)`: an order check logs `kind='order'`, `method='order'`.
  The `meta` carries `walk`, `step`, `section`, `page`, `gate`. "Keep this state" saves the demo state on that attempt
  as `keep` (`mark_attempt`).
- The first prediction on any gate makes the step done. Later gates still log.

### 6.6 The code check in the browser (shared core 4)

- Route `POST /w/{jid}/{i}/run` with the editor text. The engine:
  1. `ast.parse` the text. A syntax error returns its line and message and uses no try (a typo is not a miss).
  2. `check.run_isolated('assert', fname, source, tests, total=10., sandbox=True)` returns `public(report)`.
  3. Pass: close through `Tutor._close` as `Exercise.check` does. Fail with tries left: a try is kept, and the reply
     has the counts and the first error. The last failing try closes with a lesson. `MAX_TRIES` is 3, as today.
  4. A timeout or a missing result is a failing try with the first error "The code ran longer than 10 s" or "The code
     stopped before the tests ran".
- The first error is mechanical (the first failing test and its error), not a model call. Hint uses `Tutor.hint`.
- The reply holds only `public(report)` fields: no hidden test text, no expected value of a hidden test, no solution.

### 6.7 Security of learner code

- Learner code runs only in `run_isolated`: a new `python -I -B` process, cwd a new temp folder, an environment with
  only `PATH` and `HOME` (the temp folder), and the time limits in Settings: `runner.per_test` for each test (2 s by default, 1 to
  10 s) and `runner.total` for all the tests (10 s by default, 5 to 60 s). The kill comes at the total + 2 s.
- `sandbox=True` adds, before the learner code, an audit hook (`sys.addaudithook`, which cannot be removed) that
  raises on `socket.*` (connect, bind, getaddrinfo), `subprocess.Popen`, `os.system`, `os.exec*`, `os.posix_spawn`,
  `os.fork`, `os.kill`, `os.killpg`, `signal.pthread_kill`, frame walks, and `open` for write outside the temp folder.
  The first lines of the script set `RLIMIT_CPU` to the total + 1 s and `RLIMIT_FSIZE` to `runner.file_mb` (10 MB by default).
- `sandbox` is on by default. The report goes to a private pipe, not to stdout, with a random nonce for each run. The
  nonce comes in on a second pipe, so it is not in the source. If the pipe has no report with the nonce, the result is
  an error. Learner code that only prints a fake result does not pass. But learner code can still fool its own checks
  (for example through `ctypes`, or by a change to the `json` module). The checks are for learning. They are not a proof.
- Tests from the model pass `validate_exercise` (one plain `assert` each). The solution never leaves the server.
- No network in the check. The app stays loopback only (`LocalOnly`).
- On macOS, the child also runs under `/usr/bin/sandbox-exec` (when it exists) with a profile that denies the network,
  signals to other processes, and file writes outside the temp folder. On other systems, the guard is best-effort. The docs say "a closed process with no network". They never say "a
  security sandbox".
- Learner code always runs with the app's own Python, and an exercise uses only the standard library. abhyasa
  installs no package. Code with a library runs in Leela (6.12); its limits are Leela's (`leela-reuse.md`, section 6).
- The app itself uses the network in one case only, outside the closed process, and only when the learner asks:
  **fetching a link (6.11).** Only the URL that the learner gives, and only pages in the folder of that URL. At most
  the pages in Settings: `links.pages` (8 by default), never more than the page cap `links.cap` (20 by default, 1 to
  50). The fetched text is data: it goes into the vault and to the model as
  passage text, and it never runs.
- The Leela link (6.12): abhyasa reads Leela's address file and never connects to Leela. It makes a link only to a
  loopback `http` URL whose process is alive. The values in the link are a journey id, a step number and a concept
  name, made with `urlencode`.
- The side pane (6.10) shows only a page of the app: the `rh` value must be a local path (one `/` at the start, no
  `//`, no `\`, no scheme). The page takes pane messages only from its own origin and from its own pane frame.

### 6.8 The walk block (Option A)

Block `abhyasa/blocks/walk/` (`cfg.py`, `ui.py`, `app.py`, `walk.css`, `walk.js`), `CAPS = ('learning', 'tutor',
'ask', 'pool', 'sessions', 'sources')`, in `NAMES` after `demo` and before `today`.

| route | method | what it does |
|---|---|---|
| `/walk/new` | POST | make a walk from `ref` (vault doc), `text`, `topic` or `url` (6.11), with `tool` (a tool walk, 6.12); redirect to `/w/{jid}` |
| `/walk/job` | GET | the state of a link walk that is still being made: a pending card, or a redirect to `/w/{jid}`, or a message (6.11) |
| `/w/{jid}` | GET | not started: the plan (A1); started: redirect to the current step |
| `/w/{jid}/plan` | POST | change one step of the plan: `act` = `check` (with a `way` in `WALK_WAYS`; `why` = "you chose it") or `drop` |
| `/w/{jid}/start` | POST | set `started`, open a sitting, redirect to step 0 or the current step |
| `/w/{jid}/{i}` | GET | the step page: rail, section, title, passage, figure, note, and the check slot; sets `read_at` |
| `/w/{jid}/{i}/check` | GET | the check card (loads after the page); reuses the open question in `qid` |
| `/w/{jid}/{i}/answer` | POST | a short answer: `answer`, `thinking`, `confidence` |
| `/w/{jid}/{i}/hint` | POST | the next hint |
| `/w/{jid}/{i}/giveup` | POST | "I don't know" before a try, "Teach me" after |
| `/w/{jid}/{i}/run` | POST | the code check (6.6) |
| `/w/{jid}/{i}/predict` | POST | a demo or order prediction (6.5) |
| `/w/{jid}/{i}/keep` | POST | keep the demo state on the last prediction attempt |
| `/w/{jid}/{i}/next` | POST | mark the step skipped when it has no `done`; go to the next step, or to `done` at a section end; a second press changes nothing |
| `/w/{jid}/{i}/done` | GET | the section summary (what moved), the end of the sitting, and "Go on" |
| `/w/{jid}/{i}/img` | GET | the figure of step `i` from vault assets (png, jpg, jpeg, gif, webp only) |

- A sitting is a `Session` with `journey=jid`, kept in `j.sitting`. The walk sets `s.q` itself; it never calls
  `Session.next`. At a section end the walk shows its own summary (`moved` over the section's log rows), ends the
  sitting, and the next section opens a new sitting.
- Check kinds render through one table in the block, `CHECKS = dict(short=…, demo=…, order=…, code=…)`, so later
  kinds (timeline, board, playground) add one entry.
- Hooks: `today_next` (continue the walk: title and "idea 5 of 11"); `concept_more` (the passage of the concept and a
  link to its step); `lesson_extra` (after a review close on a walk idea: "Read the passage again: p. 4").
- Small changes outside the block, by link only: the journeys page shows "Continue the walk" (`/w/{jid}`) for a walk;
  the history block's Continue goes to `/w/{jid}` for a walk sitting; Add gets a tab "As a walk, in reading order"
  with a vault document, a text or a topic; the vault page gets "Learn as a walk" beside "Learn from this".

### 6.9 Logging kinds

All through `Learning.record`, no schema change:

| check | `kind` | `method` | extra meta |
|---|---|---|---|
| short answer | `choice`, `recall` or `explain` (from `KIND_AT`) | the chosen text way | `walk`, `step`, `section`, `page` |
| code | `code` | `code` | the same |
| demo | `demo` | `demo` | the same, `demo`, `gate`, `expected`, optional `keep` |
| order | `order` | `order` | the same as demo |
| skip | nothing logged | | the step stores `done.outcome='skipped'` |
| any check in a side walk | as above | as above | the same, plus `from = "<walk id>/<step>"` (6.10) |

The learner model, floor, ceiling and next review update as today.

### 6.10 Rabbit holes: learn a missing idea, then come back

From `abhyasa-designs/rabbit-hole/design.md`, with new keys (the design's ⌥D, ⌥G and ⌥E are taken in
`core/keys.py`). The owner's case: "I'm reading the attention paper and I don't understand calculus. I should be able
to quickly pick up a course on calculus from that page on a split pane or a separate session, and get back to this."

**The moments that open one.** This plan builds 1, 2 and 3.

1. **A missing prerequisite on a step.** Under the title: "This needs: Softmax · learned · Derivatives and gradients ·
   you have not learned it · open beside ⌥B" (R1). The data: the concept's `prereqs`, and ready means floor 3 or more.
2. **A miss that points at a gap.** After a nudge or a close, when the grade names `gaps` (filed by `name_gaps`), the
   card adds "Your answer points at: gradients. Learn it beside ⌥B".
3. **A selected term in the passage.** Select "extremely small gradients" and a small tool shows "I don't know this
   ⌥B". `look_up` finds the term on the shelf by name or alias, or adds it with `name_gaps`.
4. Later (not this plan): a question typed in the answer box is caught before the grade.

**What opens.** The offer shows three ways down. The tutor picks one (`pick_way_down`) and says why in one line, as
`check_for` does. Keys 1, 2, 3 choose; Esc closes the offer.

| way down | what it is | where | picked when |
|---|---|---|---|
| A quick primer | a one-step walk: the statement, a figure if the vault has one, one short check at depth 2 | side pane | the concept has floor 1 or 2, or it has no prereqs of its own |
| A short side walk | a walk of 2 to 4 ideas: the unready prereqs of the concept, deepest first, then the concept. With no chain on the shelf: `walk_from_topic(goal="<name>: the basics, enough to read <idea>")`, cut to 4 steps | side pane | no record, and the chain has 4 ideas or fewer |
| Its own session | the same walk, or a full topic walk, as a page in a new tab | new tab | the chain has more than 4 unready ideas, or the depth limit is reached |

A side walk is a normal walk journey. "Own session ↗" in the pane bar opens the same walk as a page, at the same
step. Nothing is made twice.

**The pane and its URL state.**
- At 1100 px or more, the pane is fixed at the right, at the top of the window (`top: 0`), with width `clamp(440px, 42vw, 680px)`. The
  walk hides its rail and keeps one column. A grip on the left edge resizes it: drag, arrow keys (24 px, Shift 96
  px), a double-click resets. The width is kept in `localStorage` (`rh-w`).
- The pane shows a full step page of the side walk in an `iframe`, at the step URL with `pane=1`. A page with
  `pane=1` has no nav and no crumbs. Each document keeps its own ids, forms and keys.
- The main URL gets `?rh=/w/{sid}/{k}` (`history.pushState` when the pane opens, so browser Back closes it). Moves
  inside the pane tell the main page the new step (`rh:at`), and it updates `rh` with `replaceState`. On a reload,
  the server reads `rh` and draws the pane open. An `rh` that is not a local path draws no pane (6.7).
- The main step keeps its place. The main document is not drawn again, so its scroll, its open question (`qid`) and
  the answer box stay. The card says "Held while you learn derivatives and gradients. Your draft is kept." The draft
  is also kept in `sessionStorage` by `qid`.
- Return (R3). When the side walk ends, its done page sends `rh:done`. The main page calls `/rh/back/{sid}`, closes
  the pane and puts the focus in the answer box. The step shows the strip "Back on the paper. You learned
  derivatives and gradients on the way · 3 ideas · 2 solid, 1 shaky". The needs line says "learned on the way
  today".
- Keys. ⌥B opens the offer for the first unmet need, or for the selected term; in the pane, it opens a nested rabbit
  hole. ⌥Z goes back to the paper: it closes one level of the pane and puts the focus on the check. Esc closes the
  offer, else the pane, when the focus is not in a text box. In a pane page, Esc closes the pane, not the crumb
  above. The walk keys (⌥S, ⌥W, K, ⌘↵) act in the document that has the focus.

**Nesting.** A rabbit hole in the pane opens in the same pane, not a second one. The bar shows the trail
("Attention · idea 5 › Gradients › Derivatives"), each part a link. The limit is depth 2 (the paper plus two side
walks, `MAX_DEPTH = 2`). At the limit, the offer gives only "Its own session ↗". ⌥Z goes back one level.

**Narrow screens.** Under 1100 px there is no split. The side walk opens as a page in the same tab, with "← Back to
the paper: idea 5 of 11" at the top. The main step comes back with its open question and the draft from
`sessionStorage`.

**What is logged.**
- Side walk checks are normal attempts through `Learning.record`, with one more meta field:
  `from = "<walk id>/<step>"`, the step that opened it. No schema change.
- The side walk journey has `parent = {walk, step}` and `depth` (the parent's depth plus 1). "Its own session" has
  `parent` and `depth = 0`, so it can open its own rabbit holes. The parent step gets `detours = [{walk, slug,
  outcome, at}]` once, when the learner comes back (`back_from`).
- Journeys lists a side walk under its parent, not as its own line. Today shows an unfinished side walk:
  "Unfinished side walk: Derivatives (for Attention, idea 5)".
- Review does not change. Under a lesson on the new idea, `lesson_extra` adds "You first met this on the way to: Why
  divide by √dk", with a link to that step.

**A reusable host, for Leela.**
- The split-pane host is core, not a block, because many blocks open it: `abhyasa/core/pane.py` (`is_local`,
  `pane_url`, `pane_link`, `PaneHost`), `core/pane.js`, `core/pane.css`.
- The contract a host implements: `open(url, title)` shows `url` with `pane=1` beside the page; `close()`; the state is
  one local URL in the query (`rh`). Messages from the pane: `rh:at {url, title, trail}`, `rh:open {url}` (nest),
  `rh:done {slug, outcome}`, `rh:close`. Leela implements `open` with its second editor slot (`mountSecondary`) and
  `close` with `leeCloseSplit`.
- The engine functions take plain data: `needs`, `pick_way_down`, `detour(lr, ask, slug, parent, how)`, `back_from`,
  `trail`, `look_up`. Leela passes its own `parent` (`{notebook, cell}`); `from` is the parent values joined by `/`.
- New hooks in `core/hooks.py`: `step_needs(j, i, c)` (the needs line and the return strip), `check_after(j, i, q)`
  (the gap line after a miss), `walk_end(j)` (the end of a side walk), `term_lookup(term, at)` (a selected term).

### 6.11 A walk from a link

Today Add takes pasted text or a vault document only. A link adds a third way in.

- Add (in the "As a walk, in reading order" form) and `/walk/new` take `url` and `pages` (the page cap: 1 to 20,
  default 8).
- `file_link(lr, url, max_pages=8)` files the target in the vault with the reader that fits it (the same test as
  `Vault.grab`, `fossick.what_is`):

  | target | reader | what is filed |
  |---|---|---|
  | an arXiv id or URL | `Vault.arxiv` (the `papers` shelf) | one paper, with its figures |
  | a PDF URL | `Vault.pdf` | one paper, with its figures |
  | a GitHub repo | `Vault.github` | its prose files; the first `max_pages`, README first, are used |
  | a GitHub file | `Vault.gh_file` | one document |
  | any other web page | `Vault.crawl(url, max_pages, follow_sel=…)`, or `Vault.url` when the cap is 1 | the start page and pages linked from it |

- The crawl stays in the folder of the URL. For `https://docs.claude.com/en/docs/claude-code/overview` the folder is
  `/en/docs/claude-code/`. The crawl follows only links into that folder (`follow_sel`), and `in_scope` drops from the
  walk any filed page outside it. The walk uses at most `max_pages` pages.
- Reading order: the start page first, then pages in the order of their first link on the start page (a docs site
  lists its pages in its side menu), then the rest in crawl order.
- `journey_from_sources(lr, ask, docs, title='', subject='', **extra)` makes one walk across the filed pages: extract
  each page, then the steps in page order, and in each page in placement order. A concept named in two pages gets one
  step, in the first page where its passage is found (else its first page). Each step's `read` names its own
  document. The journey keeps `source = dict(url=…, docs=[…])`.
- Fetching and extracting a site can take minutes, so a link walk is made as a job on the pool. `/walk/new` returns a
  pending card that polls `/walk/job` every 2 s. When the walk is ready, the card goes to `/w/{jid}`. A link that
  gives no pages says "abhyasa could not read this link."
- Fetching is network access outside the closed process (6.7): only when the learner sends the form, only the URL
  given and the pages in its folder, at most the page cap.

### 6.12 Open in Leela: the handoff for code and tools

The owner's decision of 28 October 2026, in the owner's words: "let's have the parts to teach tools and code in
abhyasa, but the implementation can rest within leela. also, leela comes with kosha tools which can make code lookup
easy for everyone. comes with uv, ramabana. makes sense to be there. abhyasa can just have minimal code footprint and
we can have a link to open leela for full fledged in depth learning."

So abhyasa keeps walks from papers, topics and docs links (6.11), and the small code check of 6.6 (a closed process,
short stdlib exercises, no library installs). Code with a library, tool environments, code lookup (kosha) and the agent
tutor (ramabana) are in Leela. abhyasa gives a link. The Leela side is in `abhyasa-designs/leela-reuse.md`, section 6.

**A tool walk.** A walk has `kind`: `''` (a walk to read, as today) or `'tool'` (a walk on a Python library or a
command-line tool, for example PydanticAI or Claude Code). The learner sets it with a tick box in the walk form on Add:
"It is a library or a command-line tool. Code and tools open in Leela."
- A tool walk gets no `code` check in abhyasa. Its checks come from `TOOL_WAYS` (`WALK_WAYS` without `code`): short
  answers (which call, command or flag does X) and order checks (the steps of a workflow). The plan view refuses a
  `code` check on a tool walk (400).
- A step whose concept has `code` in its ways gets `leela=True`. That step shows the Leela line under its check.

**Where the Leela line shows.**

| place | the line | with no Leela running |
|---|---|---|
| the plan page of a tool walk | "Open in Leela for code and tools ↗" (the walk) | the muted line and "Get Leela" |
| a step with `leela` | "Open in Leela for code and tools ↗" (this step) | the muted line and "Get Leela" |
| under any code card (a stdlib check) | "Go further with real code in Leela ↗" (this step) | nothing |
| the concept page, for a concept with the `code` way | "Learn Softmax with code in Leela ↗" (the topic) | nothing |

The muted line is "Open this in Leela for code and tools." with a link to the install page
(`https://github.com/vedicreader/leela#install`). abhyasa never shows a link to a Leela that is not running.

**How abhyasa finds Leela.** A running Leela writes `~/.config/leela/serving.json` (`$XDG_CONFIG_HOME/leela/...`) with
`host`, `port`, `pid` and `url`, and removes it when it stops (`leela/core/projects.py`). Leela's default port is 5010,
but Leela.app takes the first free port in 5010-5019, so abhyasa reads the file and does not guess a port.
- `leela_base()`: the `url` of the file when its `pid` is alive (the same test as Leela's `serving()`), else the setting
  `ABHYASA_LEELA` when the owner sets it, else none. A URL that is not `http://` on `127.0.0.1`, `localhost` or `[::1]`
  is refused. This is one small file read for each page, with no network call, so there is no cache.
- abhyasa never calls Leela. The learner's browser opens the link in a new tab (`target="_blank"`,
  `rel="noopener"`).
- Leela.app does not register a URL scheme today (it answers only the Apple Event that opens files and folders). So
  there is no `leela://` link in this plan (section 8).

**The handoff contract** (both sides implement it; the functions are in the engine, `abhyasa.journey`, so Leela
imports them with no web code):
- The link is `<Leela base URL>` + `handoff(jid, i, topic)`: `GET /learn?walk=<journey id>&step=<step index>&topic=<concept
  name>`. Each key is there only when it has a value. With no `step`, Leela opens the current step (`walk_state`). With
  only `topic`, Leela opens a lesson on that concept.
- `read_handoff(query)` gives `AttrDict(walk, step, topic)`, and refuses a `walk` that is not a journey id
  (`^[a-z0-9-]{1,48}$`), a `step` that is not a whole number from 0, a `topic` over 200 chars, or a link with neither
  `walk` nor `topic`. Other keys are ignored, so either side can add its own.
- Leela reads the walk from the shared learning store (`Learning(vault).journey(jid)`, after `import abhyasa.journey`).
  Both apps use `$VISHALAKSHI_VAULT`, else `~/.vishalakshi/vault.db`, and the `learning` shelf.
- What Leela writes back: attempts through `Learning.record`, with `walk`, `step`, `section` (when there is one),
  `from = "<journey id>/<step>"` and `app = "leela"` in the meta. So abhyasa's review rule (6.4), `lesson_extra` and the
  learner model see the work. Leela does not change the journey itself.
- `HANDOFF_CASES` is one list of `(arguments, path)` pairs. abhyasa's notebook test and Leela's contract test both run
  it: each case makes its path with `handoff`, and the path reads back to the same values with `read_handoff`.

**A command-line tool** (for example Claude Code) is a tool walk too. abhyasa still asks short-answer and order checks
on it, and never runs a command. Its code steps (a hook script, a settings file) link to Leela.

### 6.13 A trial on real material

`tools/walk_trial.py` is a script, not a test. The controller runs it with the real model. It makes walks in a
temporary vault (never the real one) for: the paper "Attention Is All You Need" (arXiv 1706.03762); the topic "how
gradient descent works"; the PydanticAI docs (`https://ai.pydantic.dev`, cap 8, a tool walk); and the Claude Code
docs (`https://docs.claude.com/en/docs/claude-code/overview`, cap 8, a tool walk). For each walk it reports: the
number of steps, the share of steps with a found passage, the figures found, the checks of each kind, the one-ask
rule on each question it makes (the question checks of `tools/grade_eval.py`), a short-answer grade round trip on one
step, a code round trip on the attention walk (a stdlib task, a naive and a good solution), the Leela handoff on the two
tool walks (no `code` check, and each step with `leela` has the right link, made with a fake address file; no Leela
runs and no library code runs), the time for each step, and screenshots of 3 steps. It prints a table and writes `design/screens/trial/report.md`. The owner reads the report. Each problem
it finds gets a small fix with its own test.

## 7. Left to the builder

- The exact wording of UI text and prompts (STE, grade 9), inside the rules above.
- Markup and CSS of the rail, the passage and the check card, close to the mockups a1-a3.
- How the folded-quote search is written, and how the image link is found next to a passage.
- The minutes estimate in the plan view (a guide: 200 words a minute for reading; short 2, order 2, demo 3, code 6).
- How the editor handles Tab and indents in `walk.js`.

## 8. Later phases this design leaves room for

- **B, the two-pane step** ("your code drives the demo"): a step can carry `layout='pair'`; the code check already
  runs in `run_isolated`, so a later route can run the passing function on demo inputs and set rupaka state.
- **C, the map view**: a second view over the same journey steps, with `x`, `y` on each step and the due marks.
- **Modality views** (`abhyasa-designs/modalities/options.md`): playground frames (1A), seeded board (2A), timeline
  lanes with an order-first string check (3A, 3B), and lenses (4B). Extract already keeps `ways`, `moves`, `when`,
  `order`, `who` and `image`, and `METHODS` already has `playground`, `board` and `timeline`. A new view adds its
  way to `WALK_WAYS` and one entry to `CHECKS`.
- Other check kinds from that design (timeline/order with polaroid cards, board) log with their own `kind` through
  `record`, as above.
- **Rabbit hole moment 4**: a question in the answer box is caught before the grade, uses no try, and gets a short
  answer with cites (`vr/core/ask.py`) and the same offer.
- **Leela as a pane host**: Leela implements `open` and `close` of the pane contract (6.10) and calls the same engine
  functions on a selection in a markdown cell.
- **A `leela://` link**: when Leela.app registers the scheme (`CFBundleURLTypes`) and answers the URL Apple Event, a
  link can also start Leela when it is not running. The path and query stay as in 6.12.
- **Leela work on the rail**: a step could show "Worked on in Leela" from the attempts with `app = "leela"` and its
  `walk` and `step`. In this plan, the rail shows only checks done in abhyasa.

## 9. Decisions made while writing this spec (the owner can change them)

1. `ways` (way names, from the modality design) replaces the `fits` tags (`visual`, `code`, `steps`, `dated`) of
   `paper/options.md`. `visual` is set from `moves`.
2. Placement (order, section, page, passage, figure) lives in the provenance entry of each source. The concept-level
   `order` keeps its meaning of a sequence (vedicreader lessons, epics). It is not the paper position.
3. `choose` with no `allowed` uses only the six text ways, so a normal session never picks `demo`, `order`,
   `playground`, `board` or `timeline`.
4. A demo prediction credits `demo`, not `playground`. `playground` gets credit when frames exist.
5. The review rule (leave out the last way) applies only to concepts whose last check was in a walk.
6. An order check is a rupaka demo with a ranklist gate (`make_demo(aim='order')`), not a new view.
7. A walk is filed when its plan is made. It shows in Journeys before "Start the walk".
8. "Next idea" always works; with no check done it is a skip, and a skip logs no attempt.
9. The code check: the first error is mechanical (no model call); a syntax error uses no try; `MAX_TRIES` stays 3.
10. `run_isolated` runs with `sandbox=True` by default (today only tests call it).
11. The section summary is a walk page, not the session end page, so "Go on" stays in the walk.
12. The Sources page lists shelves, not documents, so it gets no entry point. The entry points are Add and the vault
    document page.
13. Rabbit hole keys: ⌥B open beside, ⌥Z back to the paper, Esc close the pane. The design's ⌥D, ⌥G and ⌥E are taken
    (dictate, strengths, show me a demo). There is no key to move the focus between the paper and the pane: a click
    moves it, and ⌥Z puts it back on the check.
14. The selection tool shows only "I don't know this ⌥B". "Ask the tutor" and "Highlight" from mockup R1 come later.
15. "Its own session" is a walk with `parent` and `depth = 0`. It logs `from` and comes back like a side walk, and it
    can open its own rabbit holes.
16. The return strip shows on the parent step while its newest detour is less than 10 minutes old.
17. A crawl follows only links into the folder of the given URL, and the walk uses only pages in that folder.
18. A concept found in two pages of a link walk gets one step, at the first page where its passage is found.
19. Replaced by the owner's decision of 28 Oct (6.12). It was: a library walk runs learner code with a 20 s total. Now
    this is a Leela-side note (`leela-reuse.md`, section 6).
20. Replaced by the owner's decision of 28 Oct (6.12). It was: the audit hook allows a local socket pair (`AF_UNIX`)
    for asyncio. abhyasa's hook does not change; the allowance is a Leela-side note.
21. Replaced by the owner's decision of 28 Oct (6.12). It was: a library environment installs wheels only. Leela makes
    tool environments, wheels only.
22. Replaced by the owner's decision of 28 Oct (6.12). It was: a library walk needs `uv` on the PATH. abhyasa needs no
    `uv` for learners; Leela comes with `uv`.
23. A tool walk is marked by the learner with a tick box on Add. The model does not tag it in this plan, because that
    would change the `extract` prompt of 6.1.
24. abhyasa finds Leela only through Leela's address file (or the `ABHYASA_LEELA` setting). It never guesses port 5010
    and never connects to Leela, so a link never points at a Leela that is not running.
25. The handoff is an `http` link to `/learn` on Leela. There is no `leela://` link, because Leela.app does not register
    a URL scheme today.
26. On a tool walk, an idea with the `code` way gets a short or order check in abhyasa and a link to Leela. abhyasa does
    not hold that step open for Leela.
27. Leela logs back with `walk`, `step`, `from` and `app = "leela"` and does not change the journey. The rail in abhyasa
    does not mark a step done from work in Leela (section 8).
