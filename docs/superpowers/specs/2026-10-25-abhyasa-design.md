# abhyasa: a learning harness that makes you think

Date: 25 October 2026. Status: written overnight from one conversation. The user asked for a build while they sleep.
The text "(my call)" marks a decision that I made. Check these decisions first.

## Why

The user learns many subjects: jyotiṣa, Sanskrit, math papers, LLMs and transformers, sales, philosophy and spirituality.
The material exists (vedicreader, papers, vishalakshi vaults, ramabana sessions). But the tools only show it.
No tool knows how deep the knowledge of the user is. No tool makes the user work to get to the answer.
The user gets flow only when they write code.

The user wants to get better and to keep their ability to think. The tool must make the user think harder. It must not think for
the user.

Prior art: [learnharness](https://github.com/amosblomqvist/learnharness). The user liked two things in it: answers spoken aloud
(think-aloud), and the connected graph of ideas.

## Goals

1. An active loop: the tool asks, and the user answers by text or by voice. The tool grades the answer and decides what comes next.
2. A learner model: for each concept, how deep the user knows it and when to review it.
3. A concept graph: ideas and their links, across all subjects and sources, with the mastery on each node.
4. Difficulty at the edge of what the user knows: hard enough to struggle, but not so hard that they stop. The target is about 85% success.
5. Hints in steps, from the least to the most revealing. The tool never gives the answer before the user tries.
6. Voice input on the machine, for think-aloud answers.
7. All learning data in the shared vishalakshi vault, on its own shelf, so that any tool (Sanketa, leela, ramabana) can search it.
8. Learn by code: a concept can become a code exercise in a notebook (leela). The tool runs the code to check it.
9. Seed concepts from vedicreader (Sanskrit lessons, terms, jyotiṣa glossary) and from any document in the vault.

## Non-goals (for this first build)

- No new leela cell type and no change to leela. Leela already keeps cell metadata that it does not know, and it shows ipywidgets.
- No change to the ramabana core. A ramabana extension file gives `/learn`.
- No network calls to vedicreader.com. Read the files of the vedicreader repo.
- No video generation in this build. "UI blocks for learning videos" is a later step.
- No writes to the real vault of the user in tests. Tests use a temporary vault.

## Anti-goals (failure, even if it works)

- The tool gives answers. A hint that names the answer before the user tries is a bug.
- The tool is boring: easy questions on things that the user knows.
- The tool is a recall quiz only. Questions must ask for explanation, application and transfer.
- The tool hides its state. The user must see why a question comes next.

## Constraints

- Python, nbdev 3 on hatchling, fastcore style, `uv`. The notebooks under `nbs/` are the source.
- Use the stack that the user already has: vishalakshi (vault), rishi (models, local audio), FastHTML (web), ipywidgets (notebooks), ramabana
  (agent, extensions).
- The web app listens on loopback only. Port 5077 (my call). Never touch :5001, :5010, :5055 or :9000.
- Prose in ASD-STE100, grade 9.

## The design

### Name and shape (my call)

A new package, `abhyasa` (अभ्यास, steady practice; Yoga Sūtra 1.12). The engine is plain Python with no UI. Four surfaces use it:

| surface | what it is for |
|---|---|
| `abhyasa` web app (FastHTML) | the main place to learn: the queue for today, the session, the graph, voice |
| ramabana extension | `/learn` in the terminal, beside coding |
| notebook widget (leela, Jupyter) | learn by code: question cards and checked code exercises in a kernel |
| Sanketa (later phase) | search learnings beside vaults and ramabana sessions |

Why a new package, and not a part of ramabana or leela? The user does not want to put more load on leela.
The ramabana study showed that an extension (`setup(reg)` with commands and tools) is the clean seam.
It also showed that a real "learn mode" can copy plan mode later.
All four surfaces must use the engine, so the engine must not be inside one of them.

### Storage: the `learning` shelf

One shelf, `learning`, in the vishalakshi vault (default `~/.vishalakshi/vault.db`, or `$VISHALAKSHI_VAULT`).
Each item is a vault document. Thus keyword search and vector search find it, as they find all other documents.

| kind | source | text (searchable) | meta (state) |
|---|---|---|---|
| `concept` | `learning://concept/<slug>` | name, statement, aliases | subject, prereqs, related, depth, stability, due, floor, ceiling, misconceptions, provenance |
| `attempt` | `learning://attempt/<id>` | question, the answer and think-aloud of the user, feedback | concept, depth asked, correct, confidence, hints used, grade, time |
| `session` | `learning://session/<id>` | a short summary of the session | concepts, counts, start, end |

State changes use `Vault.set_meta`, which does not embed the text again. Edges are lists in the concept meta (`prereqs`, `related`).
This needs no new tables and no change to vishalakshi (my call).

### Learner model

For each concept:

- Depth, 0 to 5: 0 unseen, 1 recognise, 2 recall, 3 explain, 4 apply, 5 transfer (use it in a new case or another subject).
- Floor and ceiling: the floor is the highest depth that the user passes reliably. The ceiling is the lowest depth that they fail.
  The probe finds these two edges, as learnharness does.
- Stability and due date: an FSRS-style memory model. A pass at the depth of the concept grows stability, and a fail shrinks it.
  The due date is the time when the recall probability falls to 90%.
- Misconceptions: short text, kept from wrong answers that the user gave with high confidence.

The update uses correctness × confidence:

| | high confidence | low confidence |
|---|---|---|
| correct | solid: raise the floor, grow stability, go deeper next time | fragile: keep the depth, small growth, ask again soon |
| wrong | misconception: lower the ceiling, keep the misconception, teach again | gap: lower the ceiling, small correction |
| "I don't know" | (not used) | a real gap, not a wrong answer: the ceiling goes to this depth |

The number of hints also counts. A pass with hints counts as a weaker pass.

### Choose the next question (an algorithm, not only the LLM)

1. Due reviews first (concepts after their due date), with the lowest recall probability first.
2. Then the frontier: concepts with all prereqs at floor 3 or more, and with their own floor below the goal depth.
3. Ask at depth `floor + 1`. After two clean passes in a row, go up by 2. After a miss, go down by 1.
   After two misses in a row on one concept, change to its weakest prereq.
4. Mix subjects only when the user asks for it. Interleaving is an option, and it is off by default (my call).

The LLM writes the question for the concept and the depth that the algorithm chose. The algorithm owns the choice, so the user can see why.

### Question kinds

- `predict`: guess before the lesson. The guess does not have to be correct.
- `explain`: say it in your own words (good for think-aloud by voice).
- `apply`: a worked problem.
- `transfer`: a new case, or a link to another subject.
- `code`: write a function, and tests check it (notebook surface).
- `choice`: multiple choice. Each wrong option matches one named misconception.

### Grading

An LLM grader gets the concept, the depth, the question and the reference answer. The tool writes the reference answer with the
question, and never shows it to the user. The grader also gets the answer and the think-aloud of the user.
It returns structured JSON: `correct` (bool), `grade` 0–10, `first_error`, `misconception` (or empty) and `feedback`.
`first_error` tells where the reasoning first goes wrong, without the fix.
For code exercises, the tests grade the code first. The LLM only adds comments.

### Hint ladder

Six levels, one for each request: point attention → describe the pattern → name the category → name the idea → outline the move →
one worked step. The tool never gives the full answer. The user can ask to "show the answer" only after a real attempt.
A shown answer counts as a fail.

### Teaching

When the user fails, the tool teaches the smallest step that fixes the first error. Then it asks a new check question on that
step. It does not give a lecture.

### Concept extraction (the graph grows from sources)

- `extract(text, subject)`: the LLM lists the core ideas as concepts (name, aliases, and a true statement that is complete by
  itself). It also lists the prereq links between them.
- Dedupe: for each new concept, search the `learning` shelf for near matches. The same slug or a very close match is "the same
  concept". Merge its aliases and provenance. Plain code does the merge (my call).
- Sources: any text, any vault document (by doc id), and vedicreader (below).

### vedicreader import

Read only the repo files. `$VEDICREADER_ROOT` gives the path, and the default is `~/code/personal/orgs/vedicreader`.

- Sanskrit lessons: `static/learn/order.json` gives the lesson order. In each unit, each lesson is a prereq of the next lesson.
  Each lesson becomes a concept. Its `check` blocks become ready questions with reference answers.
- Sanskrit terms: `static/grammar/terms/*.json` become concepts. `related[]` becomes `related` edges.
- jyotiṣa: `vr/jyotisha/explain/*.json` becomes concepts (graha, rāśi, nakṣatra). The Python primer chapters need an import of
  vedicreader. That is a later step.

### Voice

The browser records audio (MediaRecorder) and sends it to the app. The app transcribes the audio on the machine:

1. Default: Gemma 4 E2B on LiteRT through rishi (`Chat(gemma4_e2b)(['Transcribe this clip.', wav])`). The model is already in
   the Hugging Face cache (my call).
2. Option: mlx-audio Whisper, with `ABHYASA_STT=whisper`.

The transcript goes into the think-aloud box. The user can edit it before they send it.

### Models

`abhyasa.llm` uses one call shape: `ask(prompt, sp) -> str` and `ask_json(prompt, sp) -> dict`. The default is the rishi `Chat`
with the model in `$ABHYASA_MODEL` (default `claude/sonnet`) (my call). In ramabana, the extension uses `agent.oneshot`, so
the routing of ramabana applies. Tests use a fake.

### Web app

FastHTML + HTMX, on 127.0.0.1:5077 (my call). Muted and easy to read, with no boxes inside boxes (from the Sanketa feedback). Pages:

- Today: the due count, the frontier and the subjects. "Start" starts a session.
- Session: one question at a time. A big think-aloud box with a mic button, a confidence slider, "I don't know" and "Hint".
  After the grade: the feedback, the first error, and what comes next and why.
- Graph: a d3-force graph of concepts. The color shows the depth, and the size shows how soon the review is due.
  Click a node to see its state and start a session on it.
- Add: paste text or a vault doc id, select a subject, and extract concepts.

### ramabana extension

`abhyasa/rama.py` has `setup(reg)`. It adds `/learn` (`/learn`, `/learn <topic>`, `/learn due`, `/learn graph`).
It also adds tools that let the coding agent record that the user learned something.
To turn it on, link the file into `~/.config/ramabana/extensions/`.
I do not change the config of the user tonight (my call).

### Notebook widget (leela)

`from abhyasa.nb import learn; learn('rrf')` shows an ipywidgets question card in the cell.
`exercise('concept')` writes a code exercise: a markdown question, a stub cell and a test cell, tagged with `metadata.abhyasa`.
`check()` runs the tests and records the attempt.
This works in leela, because leela shows ipywidgets and keeps cell metadata that it does not know.

### Sanketa (later phase)

Sanketa does not read vaults today. The plan has three parts:

- a read-only adhara search over the shelves (`store`, `leela`, `learning`, ...),
- a new result kind,
- an open action (`abhyasa://concept/<slug>` opens the web app).

At first, use keyword search only, because Swift has no query encoder yet. This is a separate change in a Swift repo.
It is not in the build for tonight.

## Left to the builder

Module layout, prompt text, the FSRS constants, the CSS, test structure.

## Order of work

1. Engine: store, learner model, scheduler, LLM wrapper, tutor loop, grading, hints. Tests with a fake LLM and a temporary vault.
2. Sources: extraction and vedicreader import.
3. Web app with voice and graph.
4. ramabana extension.
5. Notebook widget.
6. Sanketa: plan only.
