# Teach a topic to a group: a walk as a talk, then a live room

Date: 29 October 2026. Status: approved by the owner. Build Option A ("Walk as talk") first, then Option B ("Live room"),
in one plan. Option C (a board-first workshop) is not its own mode. By the owner's ruling, its board and timeline are slide
kinds inside a talk (plan Tasks 14 to 17, `plan-c.md`).
Design sources: `abhyasa-designs/presentation/design.md` (sections 1 to 4, 7 and 8), `abhyasa-designs/presentation/leela-reuse.md`,
the mockups `presentation/mock/a1-a5` and `b1-b5`, and the screens `presentation/shots/a1-deck.png` to `b5-recap.png`. The
walk spec (`docs/superpowers/specs/2026-10-28-guided-walk-design.md`) gives the walk, the side pane and the keys that this
spec uses. Paths without a folder are in the abhyasa repo. Facts about the code are from abhyasa 0.0.11 (commit `faf7858`)
and rupaka 0.0.3. Option A, as built (Tasks 1 to 8, abhyasa 0.0.13), uses rupaka 0.0.4. "As built" notes below give the
rulings that changed this spec while the plan was built.

## 1. Intent

abhyasa teaches one person. The owner also teaches groups: a team, a class or a reading group. Today the owner must copy
a walk into slides by hand. Then the slides lose what makes the walk good: the passage word for word, the figure from the
vault, the live demo with its gate, and the check that shows who understood.

This feature makes a talk from a walk. Each idea of the walk is one slide. The passage and the figure show to the room,
the tutor note is the speaker note, and a demo plays live. A check or a demo gate becomes a question for the room. The
presenter has a presenter window and an audience window on the projector. They stay in step. After the talk, a recap
shows where the room was unsure, and the presenter can send one HTML file to the room.

Option A works with one laptop and no phones: the room answers with hands. Option B adds phones on the same Wi-Fi: each
person answers on a phone, the room can vote twice with a talk between the votes, and people can send questions. The
room server of Option B is a small separate package, `sabha`, that runs only during a talk.

## 2. Goals

1. Make a talk from a walk in one step ("Present this walk").
2. Each idea is one slide: the passage and the figure show to the room, the tutor note is the speaker note, and a demo
   plays live with its gate.
3. Two browser windows, the presenter window and the audience window, stay in step over a `BroadcastChannel`. Every
   control has a left-hand key.
4. Ask the room: a check or a demo gate becomes a question for the whole room. With no phones, the presenter keys in the
   choice that most hands chose. With phones, the result shows as a calm chart.
5. A missing idea opens beside the slide in the side pane, for the room to see, and closes again.
6. After the talk: what the room got wrong, the questions from the room, a recap file for the room, and a follow-up walk
   for the presenter.
7. Local first: no cloud service, no account, no service on the internet.
8. Option B: phones join with a QR code and a join code, answer, vote twice, and send questions. The room server runs only
   during a talk and gives no access to the owner's data.
9. The data, the stage and the room are reusable: Leela builds its own talk mode on the same contracts (section 17).

## 3. Non-goals

- A general slide editor: fonts, colours, free layout, animations. A talk has the shape of a walk.
- Import or export of PowerPoint or Keynote files. The only export is one HTML recap file.
- Talks across the internet: a room over a call, a hosted page. The room is one local network, or no network.
- Video or audio recording, captions or a transcript.
- Names, grades, scores or attendance for the people in the room.
- More than one presenter at a time, or a phone as a remote. A presentation clicker works (section 11).
- A second native window in Abhyasa.app. Talks run in the browser (decision 2).
- HTTPS for the room (decision 4).
- Option C as its own mode. The board and timeline slide kinds are not a non-goal now: by ruling, plan Tasks 14 to 17
  draw them inside a talk (section 19). The `code` kind is for Leela; no task in this plan draws it.
- "Present it" on `/walk/new` (make a walk and a talk in one form). The way in is "Present this walk" on a walk.

## 4. Anti-goals (things a talk must never do)

- **Never expose the owner's data.** A phone sees only the public deck of one talk: no notes, no vault, no learning
  store, no other page of abhyasa. The main app stays on loopback only (`LocalOnly`, `abhyasa/app.py`).
- **Never show an answer before the room answers.** The right option of a question does not go into the audience window,
  the audience HTML or a phone before the presenter shows the result. This is the walk's rule "no silent answer leaks".
- **No quiz show.** No leaderboard, no points, no timer on the audience screen, no names on answers. The clock is for the
  presenter only.
- **The room is not the owner.** The room's answers are counts. They never go into `Learning.record`, so they never
  change the owner's learner model. The presenter's own pick at a demo gate in a talk is not logged either.
- **No dashboard look.** The audience view is the page surface with big type. The presenter view has one raised card.
- **Never lose the talk.** A reload of either window comes back to the same slide and beat. Esc never ends a talk. A
  stray ⌥ key never leaves the talk page.

## 5. Constraints

- Repo rules (`CLAUDE.md`): the engine is the notebooks in `nbs/`. The new engine module `abhyasa/talk.py` is generated
  from `nbs/17_talk.ipynb` by `uv run nbdev-prepare`. The web app is blocks written by hand. Blocks never import each
  other and talk through hooks (`abhyasa/core/hooks.py`).
- `abhyasa/sabha/` is written by hand and tested with `uv run pytest`. It imports only the standard library, Starlette
  and uvicorn (both come with `python-fasthtml`). It never imports `abhyasa`, so it can move to its own repo.
- `abhyasa.talk` imports no web code, so Leela can import it (`tests/test_import_weight.py` checks it).
- Prose (UI text, prompts, notebooks, docs, commit messages) is ASD-STE100 Simplified Technical English, US grade 9.
- Notebooks read as documents: an intro, short sections, a one-line lead before each code cell, small tests.
- Tests never open the real vault or `~/.config/abhyasa`. They use `temp_learning()` and `abhyasa.llm.Fake`.
- Browser checks use Playwright's bundled Chromium, headless, one browser at a time, closed in a `finally`.
- New prompt text is registered with `prompts.register`. New values that a person can change go into the settings table
  (`nbs/16_settings.ipynb`). Security limits stay fixed and go into `FIXED`.
- Keys: left hand only. Before a key is chosen, read `abhyasa/core/keys.py`. The task that binds a key adds it to `KEYS`.
- No new runtime dependency. **Ruling: the rule "no new vendored script" is lifted for one file only**, a small MIT QR
  code encoder in `abhyasa/core/vendor/` (decision 5).

## 6. Decisions (owner and controller rulings, 29 October 2026)

1. **A first, then B, in one plan.** A's tasks come first, then B's tasks. B only adds to A. The deck shape and the
   channel messages are made for B from the start: A already has the public deck, the `ask` message without the answer,
   and the message types `join`, `room` and `question`, which A accepts and B draws.
2. **The browser, two windows.** The presenter window opens the audience window with `window.open`. The two windows
   stay in step over a `BroadcastChannel` (same origin). Abhyasa.app needs no second native window now. In Abhyasa.app,
   the presenter page shows the loopback URL to open in a browser (section 9.4).
3. **The room is not the owner.** Room answers stay out of the presenter's learner model. They feed only the run log and
   the recap.
4. **Plain HTTP on the local Wi-Fi**, with a clear warning on the join screen and in the presenter view. Phones refuse a
   self-signed certificate.
5. **The room server is `sabha`**, a new small package. It goes to its own repo later. In this plan it is the subpackage
   `abhyasa/sabha/`, which can move out. It runs only during a talk, on its own port. It serves only the public deck and
   the phone page. It uses a 6-symbol join code, is read-only for the audience (an audience member can send an answer
   or a question, and nothing else), gives no access to the owner's data, limits the rate of requests, and stops at the
   end of the talk.
6. **QR code:** a small vendored JS encoder (MIT, one file) in `abhyasa/core/vendor/`, so no new Python dependency. The
   audience window draws the QR code. `sabha` does not make it.
7. **The second vote starts only when the presenter presses its key.** There is no automatic start. A split first vote
   (30% to 70% right) only makes "Talk, then vote again" the main button.
8. **Keys: left hand only.** The talk keys of the mock (D or space next, A back, Q ask the room, R show the answer, E into
   the demo, X laser, B blank, G go to an idea) work only inside a talk window (section 11).
9. **Homes of the reusable parts** (section 17): the deck shape and the run log in `abhyasa.talk`; the stage bundle
   (channel, laser, blank, audience style, keys) in `abhyasa/core/`; a mirrored demo needs `Rupaka.set` and
   `Rupaka.settle` in the rupaka repo, which this plan does not edit (one task ends in an ask to the rupaka owner); room
   parts in `abhyasa/sabha/`.
10. **Security review focus:** the room server (bind address, join code, rate limits, no vault access, no path traversal,
    input size limits, anonymous answers, CSRF and origin for presenter controls), the `BroadcastChannel` messages (the
    shape is checked), and the way text from the room is cleaned and drawn.

## 7. Data model

### 7.1 A talk

A talk is a document on the learning shelf (kind `talk`), next to the journeys. It points at its walk and copies what it
shows, so a change to the talk never changes the walk. The editor says so.

```python
talk = dict(id='attention-is-all-you-need-talk-3f2a', kind='talk', schema=1, title='Attention Is All You Need',
            src={'walk': 'attention-ab12'}, made=1761730000., minutes=40, phones=False, live=None,
            slides=[slide, ...])
```

- `id` matches `^[a-z0-9-]{1,48}$`. `minutes` is the presenter's slot. Its default is the estimate (7.6) rounded up to
  a multiple of 5. `phones` is the editor's choice "Room phones" (Option B). `live` is the id of the run that is open now,
  or None.
- `src` names where the talk came from: `{'walk': jid}` in abhyasa; `{'notebook': path}` or `{'file': path}` in Leela.
- Store calls (engine, `abhyasa.talk`): `Learning.put_talk(t)`, `Learning.talk(tid)`, `Learning.talks()`,
  `Learning.drop_talk(tid)`, `Learning.put_run(r)`, `Learning.run(rid)`, `Learning.runs(tid)`. A run is a document of kind
  `talk-run`.

### 7.2 Slides

```python
slide = dict(id='s3', kind='idea', step=2, title='Scaling by the root of dk', section='3.2.1 Scaled Dot-Product Attention',
             show=dict(passage='the dot products grow large in magnitude ...', figure='asset:attention/images/fig2.png',
                       demo='softmax-temperature'),
             beats=['passage', 'lit:extremely small gradients', 'demo'],
             notes='The authors add one small step ...', ask=ask, mins=5)
```

| field | meaning |
|---|---|
| `id` | `s1`, `s2` ...; unique in the talk; a new slide takes the next free number |
| `kind` | one of `SLIDE_KINDS = ('idea', 'pause', 'questions', 'recap', 'primer', 'board', 'timeline', 'code')` |
| `step` | the walk step for `idea`; else absent |
| `concept` | the concept slug for `idea` and `primer` |
| `show.passage` | the passage text, word for word from the walk step (`read.text`), or `''` |
| `show.figure` | an image id (7.3), or None |
| `show.demo` | a demo slug in the learning store, or None |
| `beats` | what each press of D reveals (7.4) |
| `notes` | the speaker note: the walk step's `note`, which the presenter can change; markdown |
| `ask` | the question for the room (7.5), or None |
| `mins` | the minutes of the slide |
| `prompt`, `secs` | for `pause`: the prompt ("Talk to your neighbour: ...") and the time |

`board`, `timeline` and `code` are in `SLIDE_KINDS` so that a talk with them passes `check_talk`. Plan Tasks 14 to 17
(Option C) draw `board` and `timeline` inside a talk, with their own fields. No task draws `code` (Leela draws it). A view
that does not know a kind shows the title and "This slide kind shows in a later version."

### 7.3 Image ids

`show` holds ids, never paths or URLs. A figure is `asset:<path relative to lr.vault.assets()>`, for example
`asset:attention/images/fig2.png`. The host gives a `resolve(image_id) -> Path | None`. abhyasa's resolver
(`asset_resolver(lr)`) returns the path only when it is inside the assets root, exists, and has a suffix in
`.png .jpg .jpeg .gif .webp`. Leela uses its own scheme (`ws:`). `check_talk(t, schemes=('asset',))` refuses an image id
with another scheme, a `..` part, a leading `/`, a backslash, a second `:` or a control character.

### 7.4 Beats

`beats` is a list. The slide shows its crumb and title, then one beat more for each press of D. `beat` in a message and
in the run log is 1-based: `1 <= beat <= max(1, len(beats))`. Going forward to a slide shows beat 1. Going back to a
slide shows its last beat.

| beat | what it reveals |
|---|---|
| `passage` | the passage |
| `figure` | the figure |
| `lit:<text>` | lights `<text>` in the passage; `<text>` must be in `show.passage` |
| `lit:#<id>` | lights the element with `data-rk-id="<id>"` in the figure or the demo |
| `demo` | the demo |
| `ask` | opens the question (the same as Q) |

`talk_from_walk` makes `'passage'` when the passage has text, then `'figure'` when there is a figure, then `'demo'` when
there is a demo. (As built, Task 1 ruling: a step with no passage text gets no `passage` beat, because `check_talk` refuses
a beat whose part is empty.) The
presenter adds `lit:` beats in the editor. Leela adds `lines:a-b` and `out` for its `code` slides.

### 7.5 Questions for the room

```python
ask = dict(kind='choice', q='T goes from 1 to 2. What happens to the share of Paris?',
           options=['It rises', 'It falls', 'It stays the same'], answer=1, src=dict(demo='softmax-temperature', gate='hot'))
```

| kind | `options` | `answer` | made from |
|---|---|---|---|
| `choice` | 2 to 6 texts | the index of the right option | a demo gate with fixed options; a short check through the prompt `talk.choice` |
| `order` | 3 to 6 texts, in the order that the room sees | the indexes in the right order | the editor: the presenter writes the cards in the right order, and the talk mixes them |
| `words` | none (`most=80`) | none | a short check, when `talks.choice` is off or the model fails |
| `scale` | 5 labels | none | a pause ("How sure are you?") |
| `none` | | | a slide with no question |

- `ask.answer` stays in the talk. It never goes into the public deck, the audience HTML or an `ask` message.
- For `order`, the options are stored in a mixed order that is never the right order.
- There is no `twice` field. A second vote is always the presenter's choice (decision 7).

### 7.6 Minutes

`slide_minutes(step, ask) = journey.minutes(step) + val('talks.ask_min')` when the slide has a question, else
`journey.minutes(step)`. A `questions` slide is 5 minutes, a `recap` slide 2, a `pause` its `secs` rounded up to minutes.
`talk_minutes(t)` sums `mins`. The editor shows "About 20 min of a 20 min slot".

### 7.7 The public deck

```python
public_deck(t, resolve) -> AttrDict(title, slides=[dict(id, kind, title, section, passage, figure, ask)], images={sha256: (bytes, mime)})
```

- Built from a list of allowed fields, never by removing fields. A new field in a talk does not reach the room.
- `passage` is `show.passage` when the slide shows it. `figure` is the sha256 hex of the image bytes, or None. `ask` is the
  public part: `kind`, `q`, `options` (and `most` for `words`). No `notes`, `answer`, `src`, `step`, `concept`, demo slug
  or demo spec, and no path.
- Images: only png, jpeg, gif and webp, found from their first bytes, each at most `talks.image_mb` MB. Other files are
  left out (the slide shows no figure).
- The audience window and `sabha` both draw from the public deck. The audience window also gets the demo spec of each
  demo slide, because it runs the live demo on the owner's laptop.

### 7.8 The run log

One document for each time the talk is given:

```python
run = dict(id='run-7d1e2a3b', talk='attention-...-3f2a', key='9c1e5f7a2b3d4e6f', started=..., ended=None, people=None,
           at=dict(slide='s1', beat=1, blank=False, pane=None, ask=None),
           shown=[dict(slide='s1', at=..., secs=420), ...],
           asks={'s3': dict(kind='choice', rounds=[dict(counts=[11, 10, 4], n=25), dict(counts=[3, 21, 1], n=25)], main=None, shown=[])},
           questions=[dict(id='q1', text='Is √dk the best number?', at=..., shown=True, note='It keeps the variance near 1.')],
           beside=[dict(slug='softmax', slide='s3', at=..., secs=120)])
```

- `key` is a random 64-bit hex value for this run. The channel name has it (9.2).
- `at` is the place: the slide, the beat, the blank screen, the open pane URL and the open question. A reload of either
  window reads it. A move to a new slide clears `blank`, `pane` and `ask` (as built, Task 6 ruling); a field that the
  same request sends wins over that.
- `stage = dict(result, pair, revealed)` keeps the last result and the pair prompt (a new slide, an open or a close clears
  them) and `revealed`, the slides whose answer the room saw (R). A reload of either window draws them again.
- A `beside` entry is `dict(slug, slide, at, secs, ask, main)`, plus `rounds` when the room answered a question on the
  primer. `weak` and `recap` add each unsure primer question after its slide.
- `asks[...].rounds` has one or two rounds. For `order`, `counts` is `[right, not right]` and the round has `swap` (the
  pair of options most often swapped, or None). For `words`, a round is `dict(n=...)`, and `shown` keeps only the answers
  that the presenter showed. For hands (Option A), `rounds` is empty and `main` is the option that most hands chose.
- `people` is the most phones that joined (Option B), else None.
- The run log keeps counts, the questions that the presenter kept, and the words answers that the presenter showed. It
  keeps no device token, no address and no other words answer.

### 7.9 The recap

`weak(t, run, below=None)`: each slide whose last round has a share right below `below` (default `talks.weak`, 0.7),
or whose hands `main` is not the answer. Each item: `dict(slide, title, share, top_wrong, n, main)`; `share` is None for
hands. `recap(t, run) -> AttrDict(unsure, slides, questions, beside, follow)`: `unsure` is `weak`, `slides` is each shown
slide with its time and share, `follow` is the concept slugs of the weak slides. `recap_html(t, run, resolve) -> str` is
the file for the room (section 13).

## 8. Making a talk from a walk

`talk_from_walk(lr, ask, jid, choice=None) -> AttrDict`:

1. One `idea` slide for each walk step whose status is not `skip`, in walk order. Title: the concept name. Section:
   `read.section`. `show.passage`: `read.text`. `show.figure`: `asset:` + `read.figure`, when the step has a figure.
   `notes`: the step's `note`, else `''` (no model call for notes).
2. A step whose check is a demo or an order check: `show.demo` is the slug from `lr.demo_for(slug, aim)` (aim `order` for
   an order check). The question comes from the first gate that can be a room question: `ask_from_gate(spec, gate)`.
   This uses no model call. A walk's order check is a gate after a ranklist, so it gives a `choice` too. When the step
   has no demo yet, or no gate can be a room question, the slide has no demo and the question comes as in item 3.
3. A step with a short check: with `choice` (default `val('talks.choice')`, True), one model call through the registered
   prompt `talk.choice` makes a choice of 4 options with the right answer kept in the talk (`ask_from_check`). The call
   uses the model task `talk`, which borrows the model of `question`. When the call fails, or `choice` is False, the
   question is `words`: "Say in one or two sentences: what is <name>?".
4. A step with a code check: the question is `words` on the same idea. A talk never runs code.
5. Then a `questions` slide ("Questions") and a `recap` slide ("What we covered").
6. The talk is saved at once (`put_talk`) and shows in "Your talks".

`ask_from_gate(spec, gate) -> dict | None` has the contract of the future `rupaka.poll.of_gate` (section 17.4):

- A gate with a fixed list of options and an answer `{"is": value}` that is one of the options gives a `choice`.
- A gate with options or an answer from a state path gives a `choice` only when the path is in `spec.state` itself.
  It runs no `derive`. A path that needs `derive` gives None.
- It gives only `choice` questions. A slider gate (4 ranges around the answer) comes with `rupaka.poll`.
- More than 6 options, or fewer than 2, gives None. The prompt is drawn with the values of `spec.state`.

## 9. The stage: two windows in step

### 9.1 The windows

- **The presenter window** (`/t/{tid}/present`) is a normal tab. It has the slide now (with its beat), the rail of
  slides (done, shaky, now, to come), the notes, the next slide, the question for the room as the one raised card, the
  clock (time used of the slot, and the minutes of slides left), and a foot line with the keys (`shots/a2-presenter.png`).
- **The audience window** (`/t/{tid}/audience?k=<run key>`) shows the slide only, full screen: the crumb (section), the
  title, the passage, the figure and a quiet foot line (`shots/a3-audience.png`). Titles are 46 px and passages 28 px at
  1280 by 720, and they scale with the window. It takes only the F key (fill the screen) and shows "Keys work in the
  presenter window" for 3 s when another key is pressed.
- Both pages have no top bar, no crumbs and no search box. Both have the class `talk` on `html`.
- The audience HTML is drawn from the public deck (7.7) plus the demo specs. It has no notes and no answers.

### 9.2 The channel

The windows talk over `BroadcastChannel('abhyasa-stage:' + tid + ':' + run.key)`. No server is needed for this. A message
is small data, with `v: 1`. The full list for version 1 is below. A sends all but `join`, `room` and `question`. B sends
those too. (As built: `answers` and the `pick` field of `demo` were added under `v: 1` in Task 7b; Option C adds its own
types with `abhyasaStage.add`.)

| `t` | fields | from | what the audience does |
|---|---|---|---|
| `go` | `slide` (`^s[0-9]{1,4}$`), `beat` (0 to 50) | presenter | shows the slide up to the beat |
| `point` | `x`, `y` (0 to 1, in the slide box), or `id` (`^[A-Za-z0-9_-]{1,64}$`), or `off: true` | presenter | the laser dot, or lights an id for 3 s |
| `demo` | `slug` (`^[a-z0-9-]{1,80}$`), `state` (an object), `gates` (`{id: 'done'}`), optional `pick` (`{id: index}` or a list of indexes, 0 to 63, only for a done gate) | presenter | sets the mirrored demo (section 10) |
| `ask` | `slide`, `ask` (`kind`, `q` up to 500 chars, `options` up to 6 of up to 200 chars, `most`), or `ask: null` | presenter | shows the question, or closes it |
| `result` | `slide`, `kind`, `rounds` (up to 2 of `counts`, `n`), `right` (an index, a list or null), `main` | presenter | shows the result and the right answer |
| `pair` | `on` (bool), `prompt` (up to 200 chars) | presenter | "Talk to your neighbour", with no clock |
| `pane` | `url` (a local path, or null) | presenter | opens the page beside the slide, or closes it |
| `blank` | `on` (bool) | presenter | the page colour and the talk title only |
| `end` | none | presenter | "Thank you" and the talk title |
| `answers` | `slide`, `slug`, `gates` (up to 16 of gate id -> the gate's `answer`: `{is: value}` or a state path) | presenter | after R only: puts the answers into the done gates of that demo, so its copy shows the verdict of the presenter's pick |
| `hello` | none | audience | asks for the place; the presenter answers with `go`, `blank`, `pane`, `ask`, `result`, `pair`, `demo` and, after R, `answers` |
| `here` | none | audience | sent every 2 s; with none for 5 s, the presenter shows "The audience window is closed. Open it again." |
| `join` | `url` (`http://<private IPv4 or 127.0.0.1>:<port>/j/<code>`, or null), `code` | presenter (B) | the join screen with the QR code |
| `room` | `joined`, `answered` (whole numbers) | presenter (B) | "27 of 34 answered", never the counts of each option |
| `question` | `text` (up to 280 chars, or null) | presenter (B) | shows one question from the room as text |

Rules for each message (`abhyasaStage.valid`, in `core/stage.js`):

- A message must be a plain object of at most 64 kB as JSON, with `v === 1` and a `t` from the list. Each field must have
  its type and range. A field that is not in the list for its `t` makes the message invalid. An `ask` with an `answer`
  key is invalid.
- A `pane` URL must pass `isLocal` (the same rule as `is_local` in `core/pane.py`). The talk block adds a stricter rule:
  the path must be a walk step, `^/w/[a-z0-9-]{1,48}/[0-9]{1,3}$`.
- The receiver drops an invalid message with no error. The sender refuses to send one (it throws), so a bug shows in
  tests.
- The channel carries data only. Each app draws its own slides. Text from a message is set with `textContent`, never as
  HTML.

### 9.3 The place on the server

- Each move posts the place to `POST /t/{tid}/at` (`slide`, `beat`, `blank`, `pane`). The server keeps it in `run.at` and
  updates `run.shown`. A reload of the presenter window or the audience window draws the place from `run.at`.
- The audience window sends `hello` when it loads. The presenter answers with the place.
- `POST /t/{tid}/at` with an unknown slide, or a beat out of range, gives 400 and changes nothing.
- A move to a new slide clears the blank screen, the pane and the question (7.8). The reply has the stage messages for
  each change, and the presenter sends them.

### 9.4 Opening the audience window

- ⌥S on the editor ("Present") starts a run and opens the presenter window. The presenter window opens the audience window
  with `window.open(url, 'abhyasa-audience-' + tid, 'popup,width=1280,height=720')` on the first key press or click (a
  user act). The presenter drags it to the projector and presses F in it.
- When `window.open` gives null, the presenter view shows "Open the audience window" as a link with the same URL.
- In Abhyasa.app, a second window of a server page opens in the same view. So when the page runs in the app, the presenter
  view shows "Present in your browser" with the loopback URL of the presenter window and a copy button. As built, the app
  puts the token `Abhyasa/<version>` in its user agent (`applicationNameForUserAgent` in `WebController.swift`), and
  `talk.js` looks for that token. An older app (WebKit with no `Safari/`) is the fallback.
- On a call, the presenter shares only the audience window.
- The Window Management API (to put the window on the second screen) is left to the builder: use it only when the
  browser has it and the presenter allows it.

## 10. Live demos and the mirrored demo

- The demo runs in the presenter window. The audience window mounts the same spec and follows the presenter's state.
- E moves the focus into the demo, so its own keys work (A and D for frames, 1 to 9 for options). Esc leaves the demo.
- At a gate, the presenter asks the room (Q). After the result (R), the presenter picks the room's answer in the gate.
  The talk page catches the gate's `rk-predict` event, calls `preventDefault()`, then `detail.settle(true)`. It never
  posts a prediction, so nothing goes into `Learning.record`.
- The mirror is `abhyasaStage.mirror(host)` in `core/stage.js`. As built, it needs rupaka 0.0.4 (`Rupaka.state`, `set`
  and `settle`) and throws an error that names the version when they are not there.
  - `snapshot()` gives `{state: Rupaka.state(host), gates, pick}`: the input keys, the gates that are done, and the
    presenter's pick at each done gate as the index of the option.
  - `apply(state, gates, pick)` calls `Rupaka.set` with only the changed input keys, then `Rupaka.settle` one time for
    each new pick at a done gate, so the blocks after the gate show.
  - The audience copy has no gate answers (`room_spec` takes them out), so before R a closed gate shows no verdict.
    On R the presenter sends `answers` for the done gates of each demo of the slide (`answers()`), and the audience
    copy puts them in (`reveal`) and shows the verdict of the pick. A move to a new slide takes them out again
    (`forget`). A reload after R gets them again on `hello`.
  - The pick goes only over the channel. No window logs it or files it.
  - The gates in the audience copy are `inert`. They never take input.
- The rupaka ask (Task 4) gave rupaka 0.0.4: `Rupaka.set`, `Rupaka.settle`, `Rupaka.state(el)`, a `save(state)` option for
  `Rupaka.mount`, and `rupaka.poll` (section 17.4). Still open with the rupaka owner: `Rupaka.options(el, gate)` or a
  `settle` by index, and a `Rupaka.reveal` (or `settle` with an answer), so the mirror reads no part of the store.

## 11. Keys

The talk windows are their own key scope, as the Graph is: plain keys work there because the windows have no text box
outside the editor dialogs. The new group "Talk" goes into `KEYS`, so the Keyboard shortcuts page and the Sanketa pack
show it.

| key | action | option |
|---|---|---|
| D or space | next beat; after the last beat, the next slide | A |
| A | back one beat | A |
| Q | ask the room; Q again closes the question | A |
| R | show the result and the right answer | A |
| ⌥S | the main button: start the talk, ask the room, vote again, end the talk | A |
| E | move the focus into the demo; Esc leaves it | A |
| X | laser on or off | A |
| B | blank the audience screen, and back | A |
| G, then 1 to 9 | go to a slide by its number (two digits within 1 s, for example G 1 2) | A |
| 1 to 6 | with no phones and a question open: the option that most hands chose | A |
| F | in the audience window: fill the screen | A |
| ⌥B | learn beside: open a missing idea in the side pane | A |
| ⌥Z | back to the slide: close the side pane | A |
| Esc | close the open thing (a question, the demo focus, the pane); never ends the talk | A |
| W | show the next question from the room | B |
| C | show the join code on the audience screen, and back | B |
| ⇧C | make a new join code | B |
| T | lock the room: no new phones; T again opens it | B |
| V | vote again on the question that is closed | B |

The editor ("Talk plan" group): W and S move the focus, ⇧W and ⇧S move the slide, E opens the slide to change it, X takes
it out, Q adds a pause after it, ⌥S presents.

How the talk keys avoid clashes with the app keys:

1. The plain keys have no modifier. Every ⌥ key keeps the meaning that it has everywhere: ⌥S is the main button (as Send,
   then "Next idea", in a walk), ⌥B is learn beside, ⌥Z is back, ⌥F shows the shortcuts. ⌥W (hint) and ⌥V (keep the demo)
   are not bound in a talk window, so they do nothing there. No new ⌥ key is used. ⌥Q and ⌥R stay free.
2. The plain keys work only when `html` has the class `talk` (the presenter window and the editor list), only when the
   focus is not in a text box, and only when the focus is not in the demo. In the demo, the demo's own keys (A, D, 1 to 9)
   win. Esc leaves the demo first.
3. In a talk window, ⌥T, ⌥C, ⌥G, ⌥D and / do nothing, so a stray key never leaves a live talk. The talk pages have no top
   bar, so `core.js` finds no target for them; `talk.js` also stops them.
4. Esc in a talk window is caught by `talk.js` before `core.js`. It closes one open thing and never goes up a level.
5. 1 to 6 count as hand picks only when a question is open. After G, they choose a slide.
6. Presentation clickers send Page Down, Page Up and the arrow keys. The presenter window takes them as D and A. A
   clicker is an extra, not a left-hand control.
7. `tests/test_keys.py` checks the plain letters of the groups "Talk" and "Talk plan" against the js, as it does for the
   Graph.

## 12. The side pane in a talk

The room is lost on idea 3. The presenter presses ⌥B. A small offer opens in the presenter window only, with the needs
of the slide's concept (`journey.needs`, `pick_way_down`). The presenter picks the quick primer (1) or a short side walk (2). The
talk block makes it with `journey.detour(lr, ask, slug, parent={'talk': tid, 'slide': sid}, how='primer')`. The presenter
window opens it in the side pane, and the audience window gets `{t: 'pane', url: '/w/<side walk id>/0?pane=1&talk=1'}`.
The audience window opens only a URL that matches `^/w/[a-z0-9-]{1,48}/[0-9]{1,3}\?pane=1&talk=1$`. It shows the primer beside the
slide (`shots/a5-beside.png`): the slide gets narrow at the left, and the primer shows in big type at the right.

- The pane URL has `talk=1` (`pane_url(url, talk=True)` in `core/pane.py`). A page with `pane=1&talk=1` draws in talk
  type, and the walk step page draws no check card, so no question opens and nothing is logged.
- Q while the pane is open asks the room about the primer's concept, with `ask_for_concept(lr, ask, slug)` (the same path
  as `ask_from_check`).
- ⌥Z closes the pane and the slide grows back. Nesting stays at depth 1. "Its own session" is not offered.
- The run log keeps it (`beside`), with the question on the primer and its hands. After the talk, the recap offers
  "Next time: put the Softmax primer before idea 3".
- A side walk of a talk is not the presenter's own learning (as built, Task 7 ruling). `for_talk(j)` in `abhyasa.journey`
  is true when its `parent` has `talk`. Such a walk does not show in Continue, Journeys or "In your journeys" on a concept
  page, and its steps set no read time and start no demo job.

## 13. After the talk

⌥S on the last slide, or "End the talk", ends the run (`POST /t/{tid}/end`), sends `end`, and opens "After the talk"
(`/t/{tid}/after`, `shots/b5-recap.png`):

- **Where the room was unsure.** Each question with the share right in each round, the wrong answer that most people
  chose, and a plain line. For hands: "Most hands: A (right: B)". A slide with no question shows only its time.
- **Questions from the room**, each with the presenter's note. A question with no note has a box for one.
- **For the room.** "Save the recap as one file" (`/t/{tid}/recap.html?run=<rid>`, a download): one HTML file with the
  slides, the passages and figures (inline as `data:` URLs), each question with its right answer and the room's result,
  and the questions with their notes. It has no script, no speaker notes and no names. It needs no server.
- **For you.** "Make a follow-up walk" on the weak ideas (`walk_from_topic` with the goal "Review: <names>"), and "Add it
  to the talk" for each primer that was opened beside a slide (a `primer` slide before that slide).
- The page says: "The answers of the room do not change your own learning."

## 14. Option B: the live room

### 14.1 The flow

1. In the editor, "Room phones: Phones on this Wi-Fi" sets `phones=True`.
2. When the talk starts, the presenter view asks: "Open the room on 192.168.1.23 (en0)? People on this Wi-Fi can join.
   The room uses plain HTTP, so other people on this Wi-Fi can read the answers." On a network where the owner has not
   opened a room before, it adds: "You have not opened a room on this network before." On the first time, macOS asks to
   allow incoming connections.
3. The audience view shows the join screen (`shots/b1-join.png`): the QR code, the address, the code in two groups of
   three (`K7P Q2M`), how many phones joined, and the plain HTTP line.
4. A phone opens the address. The QR code holds `/j/<code>`, so the code is filled in. The phone taps "Join". It needs no
   name.
5. At a question, the phones show the question and the options. The presenter view shows the counts as they come in.
   Only the presenter sees the right answer (`shots/b2-presenter-poll.png`). The audience shows only "27 of 34 answered".
6. When the first vote is split (`talks.split_lo` 30% to `talks.split_hi` 70% right), the main button is "Talk, then vote
   again ⌥S". The press closes vote 1 and sends `pair` to the audience. The presenter sees a 2-minute count
   (`talks.pair_min`). Then the main button is "Start the second vote ⌥S". Nothing starts by itself. R shows both votes
   (`shots/b3-result.png`). V starts a second vote on any closed question.
7. People send questions. They wait in the presenter view. W shows the next one on the audience screen. A question shows
   only when the presenter picks it.
8. At the end, the presenter can share the recap with the phones ("Recap" on the phone page) while the room is open. Then
   the room closes.

### 14.2 The phone page

| kind | the phone shows | the result |
|---|---|---|
| choice | 2 to 6 options | bars, one or two votes |
| order | the cards, to move in order (buttons up and down, no drag library) | the share in the right order; the pair swapped most |
| words | one text box, 80 characters | for the presenter only: the answers in a list; the presenter shows some |
| scale | 5 steps | one row of bars |

The phone never gets a demo spec, only the question and its options. A later answer from the same phone replaces the
earlier one until the vote closes.

**The chart.** One row for each option, with the option text at the left. Two thin bars in each row: the first vote as an
outline, the second vote filled. The right option gets a "✓ Right" label in text and the `--ok` colour, so the answer is
never shown by colour alone. The percentages are in the text ink at the right. A legend shows when there are two votes.

### 14.3 The room server (`abhyasa/sabha/`)

- **A separate app on a separate port.** `sabha.Room` starts its own Starlette app with uvicorn on a thread. abhyasa's
  main app keeps `LocalOnly` on loopback and does not change. The room gets a frozen public deck only.
- **Bound to one address.** The room listens only on the address that the presenter chose: a private IPv4 address
  (10/8, 172.16/12, 192.168/16) or `127.0.0.1` (tests). `0.0.0.0`, `::`, and public addresses raise `ValueError`. The port
  is `talks.port` (5180); when it is busy, the next free port up to 5189.
- **It stops** when the talk ends, when abhyasa quits (an `atexit` call and the app's shutdown), or after `talks.room_hours`
  (3) hours.
- **The join code.** 6 symbols from `CODE_ABC = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'` (31 symbols, no 0, O, 1, I or L), so
  about 887 million codes, made with `secrets`. Input is changed to upper case, and spaces and dashes are removed. 5 wrong
  codes from one address in 60 s block that address for 60 s. 50 wrong codes in total lock the joins until the presenter
  makes a new code (⇧C). The presenter can also lock the room (T): no new phones.
- **A device cookie.** A right code gives the phone a random 128-bit token (`secrets.token_urlsafe(16)`) in the cookie
  `sabha` (`HttpOnly`, `SameSite=Strict`, `Path=/`, `Max-Age` = the time left in the room). Each answer and question needs
  it. Tokens are in memory only. A new code does not drop the phones that joined.
- **The routes.** Nothing else answers (404):

| route | what it does |
|---|---|
| `GET /` and `GET /j/{code}` | the join page; `/j/{code}` fills in the code; a GET never joins |
| `POST /join` | check the code; set the cookie; redirect (303) to `/now` |
| `GET /now` | the phone page: the slide title and the open question |
| `GET /events` | server-sent events: the state changed (one stream for each token; a new one closes the old) |
| `POST /a` | one answer to the open question: an option index, an order, a scale step, or up to 80 characters |
| `POST /q` | one question to the speaker: up to 280 characters; 3 a minute for each phone |
| `GET /img/{hash}` | a figure of the public deck; `hash` must be 64 hex characters and a key of `deck.images` |
| `GET /recap` | the recap file, only after the presenter shares it; else 404 |
| `GET /static/{name}` | `phone.js` or `phone.css` only, from a fixed table loaded at import |

- **Headers.** The `Host` header must be the room's own address and port (no DNS rebinding). A `POST` needs an `Origin`
  equal to the room's own origin, and the cookie (except `/join`, which needs the origin only). A request with
  `Sec-Fetch-Site: cross-site` is refused. Every reply has `Content-Security-Policy: default-src 'none'; script-src 'self';
  style-src 'self'; img-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'`,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` and `Cache-Control: no-store`. The recap reply has
  `default-src 'none'; img-src data:; style-src 'unsafe-inline'`. No inline script anywhere.
- **Limits.** At most `talks.phones` phones (300, the top of its range). A body of at most 2048 bytes (checked on the
  length header and while reading). At most 20 events a second to each phone (the stream sends the newest state, at most
  once each 50 ms). At most 200 questions held. These limits are fixed, except the number of phones.
- **The presenter controls the room in the same process.** The talk block calls the room object. No control route is on
  the network port. The presenter's own requests go to the abhyasa app on loopback, where `LocalOnly` refuses a foreign
  `Host`, a cross-site request and a foreign `Origin`.

### 14.4 Text from phones

- `sabha.clean_text(s, most)`: NFC, control characters removed, white space made single, cut to `most` characters. An
  empty result is refused (400).
- Text from a phone is never markdown and never HTML. The phone page, the presenter view and the audience window set it
  as text (`textContent`, or an FT text node, which escapes it). It never goes through `Md`, `NotStr` or `innerHTML`.
- The recap file escapes every text with `html.escape`. The presenter's note on a question is plain text too.

## 15. Security model

### 15.1 Option A

No new network surface. Both windows are pages of the local app on loopback. `LocalOnly` does not change. The audience
window has the full demo specs, which is fine, because it runs on the owner's laptop. The `BroadcastChannel` is same-origin
by the browser's rule. Its name has the run key, so two talks or two runs do not mix. Every message is checked (9.2),
because any page of the app (for example a page in the pane) could post to a channel.

### 15.2 Option B threats

| threat | what stops it |
|---|---|
| a person on the Wi-Fi with no code | only the join page answers; code guesses are rate limited; joins lock after 50 wrong codes |
| a person who gets the code from a friend | the person sees the talk, which is public to the room anyway; the presenter can lock the room or make a new code |
| a phone that tries to read the owner's data | the room has no store, no vault and no route to abhyasa; it gets only the public deck; abhyasa answers only on loopback |
| a path such as `/img/../vault.db` or `/static/../room.py` | fixed routes; `/img/` takes only a hash that is a key of the deck; `/static/` only two names; no file path is made from input |
| a page on the internet that uses DNS rebinding | the `Host` check; the room has no data that is not on the screen |
| a page on another site that posts to the room (CSRF) | the `Origin` check, the `SameSite=Strict` cookie, `Sec-Fetch-Site` |
| a page on another site that drives the presenter controls | the controls are not on the room port; on loopback, `LocalOnly` refuses a foreign `Origin` |
| a hostile question (HTML, a script, a long text, a flood) | text only, 280 characters, 3 a minute, 2048-byte bodies, held for the presenter |
| a phone that reads the answer early | the public deck has no answers; the result reaches the phones only after `room.reveal` |
| a phone that votes many times | one answer for each token in each round; a later answer replaces the earlier one |
| someone reads the traffic on the Wi-Fi | it is the public talk and anonymous answers only; the warning on the join page and in the presenter view |
| a room left open | it closes at the end of the talk, when abhyasa quits, or after 3 hours |

`sabha.HOSTILE` lists these cases as requests with the reply that each must get. The `sabha` tests run them against a live
room on `127.0.0.1`.

## 16. Settings

New group `talks` ("Talks", "Set how a talk runs and how the room works.") in `nbs/16_settings.ipynb`, after `walks`:

| name | label | default | range | more |
|---|---|---|---|---|
| `talks.choice` | Choice questions from short checks | True | | |
| `talks.ask_min` | Minutes for each question | 1 | 0 to 5 | |
| `talks.pair_min` | Time to talk to a neighbour | 2 | 1 to 10 (min) | |
| `talks.weak` | Unsure below | 0.7 | 0.3 to 0.95 (%) | yes |
| `talks.split_lo` | A split vote starts at | 0.3 | 0 to 1 (%) | yes |
| `talks.split_hi` | A split vote ends at | 0.7 | 0 to 1 (%) | yes |
| `talks.laser_ms` | Laser fade | 1500 | 500 to 5000 (ms) | yes |
| `talks.image_mb` | Largest figure for the room | 5 | 1 to 20 (MB) | yes |
| `talks.port` | Room port | 5180 | 1024 to 65000 | yes |
| `talks.room_hours` | Room closes after | 3 | 1 to 8 (hours) | yes |
| `talks.phones` | Most phones | 300 | 10 to 300 | yes |
| `talks.nets` | the networks where the owner opened a room | `''` (a comma list) | | `ui=False` |

The model task `talk` ("Talk questions", "Writes a choice question for a talk from a short check.") borrows `question`.

Fixed, with no setting (`FIXED` gets `bind`, `join_code`, `rate`, `body`, `room_headers`): the bind rule, the join code
alphabet and length, the code limits (5 a minute, 50 in total), the question limits (280 characters, 3 a minute), the
words answer limit (80), the 2048-byte body, the 20 events a second, the headers, and the message checks.

## 17. Host contracts, for Leela

Each reusable part has one home and one contract. Leela builds its own talk mode on them, with no copy.

### 17.1 Deck shape and checks (`abhyasa.talk`)

```python
TALK_SCHEMA = 1
SLIDE_KINDS = ('idea', 'pause', 'questions', 'recap', 'primer', 'board', 'timeline', 'code')
ASK_KINDS = ('choice', 'order', 'words', 'scale', 'none')
check_talk(t:dict, schemes=('asset',)) -> list[str]   # the problems; [] when the talk is good; never raises
TALK_CASES: list[tuple[dict, list[str]]]              # good and bad talks, with the problems each must give
```

- abhyasa provides: the shape, `check_talk`, `TALK_CASES`, the store calls, `talk_from_walk`.
- Leela provides: `talk_from_notebook(nb, path)`, which returns the same shape with `src={'notebook': path}` and its own
  image scheme. It saves a talk with `put_talk` or as `<notebook>.talk.json` (the owner's choice, later).
- Test in both suites: `check_talk` on each case of `TALK_CASES` gives exactly its problems.

### 17.2 Public deck (`abhyasa.talk`)

`public_deck(t, resolve)` as in 7.7. The host gives `resolve`. Test: a talk with notes, an answer and a figure gives a
public deck with no notes, no answer, no path, and one image by hash; `json.dumps` of the slides has no `/Users/` and no
`/tmp/`.

### 17.3 Run log and recap data (`abhyasa.talk`)

`new_run`, `log_go`, `log_round`, `log_main`, `log_question`, `log_beside`, `end_run`, `weak`, `recap`, `recap_html`
(plan Task 2). Neither app calls `Learning.record` for the room. Test: a run with rounds leaves `lr.attempts()` the same.

### 17.4 Question from a gate (`abhyasa.talk` now, `rupaka.poll` later)

`ask_from_gate(spec, gate) -> dict | None` and `public_ask(ask) -> dict` (without `answer` and `src`). As built (Task 7b),
rupaka 0.0.4 ships `rupaka.poll.of_gate` and `poll.public`; `abhyasa.talk` calls them and keeps `ask_from_gate` and
`public_ask` as thin wrappers. The options are strings in the number format of the demo (2.0 shows as 2). abhyasa adds `ask_from_check` (a model call). Leela adds "What does this print?" for a code cell: the right
answer comes from the kernel after the vote, so no answer is stored before the run.

### 17.5 Stage bundle (`abhyasa/core/stage.js`, `stage.css`, `stage.py`)

```js
abhyasaStage.valid(msg) -> bool                      // the checks of 9.2; pure, so node can test it
abhyasaStage.isLocal(url) -> bool
const ch = abhyasaStage.channel(name)                // BroadcastChannel 'abhyasa-stage:' + name
ch.send(msg); ch.on(t, fn); ch.close()               // send throws on an invalid message; on drops one
abhyasaStage.audience(el, {ch, draw, fade})          // blank, laser, pointing, pane, end, hello and here; draw(msg) for the rest
abhyasaStage.presenter(el, ch, {keys})               // the key scope (html.talk, no box, not in the demo) and the laser source
abhyasaStage.mirror(host) -> {snapshot(), apply(state, gates, pick), watch(fn), answers(), reveal(gates), forget()}
abhyasaStage.add(t, fields, need, ok)                // a later task adds a message type under v: 1; it never changes one
```

- `stage.py` has `STAGE_V = 1`, `STAGE_TYPES`, `STAGE_CASES` (messages with `True` or `False`), `STAGE_KEYS` (the rows of
  the "Talk" and "Talk plan" groups, as four lists that `keys.py` adds to `KEYS`: `PLAN_KEYS`, `TALK_KEYS`, `ROOM_KEYS`,
  `VOTE_KEYS`) and `stage_assets()`.
- `stage.css` has the audience frame: the page surface, 46 px titles and 28 px passages at 1280 by 720, the laser dot, the
  blank screen, the slide beside the pane. It uses the token names of `themes.css` (`--bg --fg --ink2 --mute --line
  --rule --acc --ok --no`, `--serif --head --mono`), so Leela's tokens fit.
- The host provides `draw` for its own slide markup, and the place (abhyasa: `POST /t/{tid}/at`; Leela: `localStorage`).
- Leela adds `{t: 'out', cell, html}` for a cell output in its own version of the list, after it cleans the output. That is
  a new type, so it needs `v: 2` or a list that Leela extends; the owner decides when Leela builds it.
- Test: `STAGE_CASES` through `valid` in node; the two-window check in `tools/talk_look.py`, with a `pane` message to
  `https://evil.example/` that is dropped.
- When rupaka grows a `stage` bundle, these files can move there with the same names under `RupakaStage`.

### 17.6 Mirrored demo (rupaka)

`Rupaka.set(el, state)`, `Rupaka.settle(el, gate, pick)`, `Rupaka.state(el)` and `Rupaka.mount(el, spec, {save})` belong
to rupaka (section 10). They shipped in rupaka 0.0.4, and abhyasa needs `rupaka>=0.0.4`. The one read of the store left
is the options of a gate (for the index of a pick) and the answer that `reveal` puts into the gate block.

### 17.7 Room server (`abhyasa/sabha/`, later the `sabha` package)

```python
room = sabha.Room(deck, host, port=5180, most=300, hours=3, theme=None)   # `deck` is a public deck (7.7); `theme`: colour tokens
info = room.open()                 # AttrDict(url, code, port); starts the server on a thread
room.show(slide_id, beat=1)
room.ask(public_ask, round=1); t = room.close_ask()   # the tally of this round
room.reveal(result)                # the chart data with the right answer; only now does it reach the phones
room.questions() -> list; room.pick(qid) -> dict
room.lock(on=True); room.new_code() -> str
room.share_recap(html:str)
room.stats() -> AttrDict(joined, answered, most)
log = room.close()                 # AttrDict(people, rounds, questions); tokens are dropped
room.on('join' | 'answer' | 'question', fn)
sabha.addresses() -> list[AttrDict(name, ip)]   # private IPv4 addresses of this computer
sabha.clean_text(s, most) -> str
sabha.HOSTILE                      # the cases that the room must refuse, with the reply for each
```

- The host passes a public deck only. `Room` refuses a deck that has a `notes`, `answer` or `src` key anywhere.
- The host calls `Room` in its own process. No control route is on the network.
- The host shows the plain HTTP warning, and asks again on a network where the owner has not opened a room before.
- Test: `sabha` runs `HOSTILE` against a live room on `127.0.0.1`. Each host runs one smoke test: open a room on a
  fixture deck, join, answer, close.

### 17.8 Talk keys and the pane

- `STAGE_KEYS` is the one list of talk keys. abhyasa adds it to `KEYS`. Leela adds it to its keymap after its keymap
  audit. Both use the same keys.
- The pane in a talk uses the pane contract of `core/pane.py` as it is, plus `talk=1` and the `pane` stage message.
  abhyasa opens a primer. Leela opens a kosha lookup page with `pane=1`.

## 18. Left to the builder

- The exact wording of UI text and the `talk.choice` prompt (STE, grade 9), inside the rules above.
- Markup and CSS of the editor, the presenter view and the audience view, close to the mockups `a1-a5` and `b1-b5`.
- The QR encoder file: Nayuki's `qrcodegen` (MIT) or Kazuhiko Arase's `qrcode-generator` (MIT), one file, with its
  license header kept. The QR code is drawn as SVG in the audience window.
- The laser trail and its look, inside the fade time.
- The Window Management API, when the browser has it.
- How the phone page moves cards for an order question (buttons up and down, keyboard too).
- Passing the talk's theme colours to the phones (`Room(theme=...)`). The phones use the Paper light colours until then.
- How `sabha` wakes the event streams from the presenter's thread (for example `loop.call_soon_threadsafe`).

## 19. Later phases this design leaves room for

- **Option C:** by the owner's ruling it is done as slide kinds inside a talk, not as its own mode and not after the
  modality views: `board` and `timeline` slides (plan Tasks 14 to 17, `plan-c.md`). The board is the talk block's own
  columns, not the rupaka `canvas` renderer. With phones, the room sends cards (`POST /c`).
- **Leela's talk mode**: the section "Leela handoff" in the plan, and section 17 here.
- **A second native window in Abhyasa.app**, when the owner wants to present from the app.
- **Your own answer:** a talk that the owner gives to learn the topic could log the owner's own answer. Not in this plan.
- **`sabha` in its own repo**, with its own release; abhyasa and Leela then pin it.

## 20. Decisions made while writing this spec (the owner can change them)

1. `ask_from_gate` lives in `abhyasa.talk` now, with the contract of the future `rupaka.poll.of_gate`, because this plan
   does not edit rupaka.
2. A ships with a mirror on the rupaka 0.0.4 host API (`Rupaka.state`, `set`, `settle`). As built: the audience copy
   shows the gate's verdict of the presenter's pick only after R, when the presenter sends the gate answers (`answers`).
3. The presenter's own pick at a demo gate in a talk is not logged (the talk page settles the gate itself).
4. `recap_html` is in `abhyasa.talk`, not in `sabha`, because A needs it and it has no network part. `sabha` only serves
   the HTML that the host gives it.
5. The audience route is `/t/{tid}/audience`, not `/t/{tid}/room` (the design's name), so "room" means only the phones.
6. The audience window is drawn from the public deck plus the demo specs, so its HTML has no notes and no answers.
7. The channel name has a random run key, so two talks or two runs never mix, and an old audience window does not drive a
   new run.
8. The talk windows add the messages `hello`, `here`, `end` and `pair` to the design's list.
9. Image ids are `asset:<path in the vault assets>`. A plain path in `show` is a problem for `check_talk`.
10. Beats are 1-based, and going back to a slide shows its last beat.
11. A short check becomes a choice by default (`talks.choice`), one model call for each short step, made as a job with a
    pending card. A code check becomes a `words` question.
12. B keys: ⇧C makes a new join code, T locks the room, V votes again. They are plain left-hand keys in the talk scope.
13. Esc never ends a talk; ⌥T, ⌥C, ⌥G, ⌥D and / do nothing in a talk window.
14. `sabha` does not make the QR code and does not import abhyasa. The audience window draws the QR code with the vendored
    encoder.
15. The network name is the interface and its address (`en0`, `192.168.1.23`). macOS needs a location grant to read the
    Wi-Fi name, so the room does not show it. "A network where the owner opened a room before" is a subnet in
    `talks.nets`.
16. A GET to `/j/{code}` never joins. The phone taps "Join", so a link preview cannot join.
17. A later answer from the same phone replaces the earlier one until the vote closes.
18. In Abhyasa.app, the presenter view shows the loopback URL to open in a browser, because the app opens a second window
    of a server page in the same view.
19. A primer opened beside a slide is a walk with `parent={'talk': tid, 'slide': sid}`. As built (Task 7 ruling), it is
    kept out of the presenter's own learning: `for_talk(j)` keeps it out of Continue and Journeys, and its steps set no
    read time. "After the talk" offers a follow-up walk for the presenter instead.
20. "Your talks" shows at the end of Your learning (the hook `learning_end`), and "Present this walk" shows through a new
    hook `walk_actions(j)` on the walk plan and the journey page.
