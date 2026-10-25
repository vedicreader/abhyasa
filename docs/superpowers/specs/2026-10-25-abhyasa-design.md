# abhyasa: a learning harness that makes you think

Date: 25 October 2026. Status: written overnight from one conversation. The user asked for a build while they sleep. Items marked
**(my call)** are decisions I made. Check them first.

## Why

The user learns many subjects: jyotiṣa, Sanskrit, math papers, LLMs and transformers, sales, philosophy, spirituality. The
material exists (vedicreader, papers, vishalakshi vaults, ramabana sessions). The tools only *show* it. No tool knows how deep
the user's knowledge is, and no tool makes the user work to the answer. The only time the user gets flow is when they code.

The user wants to get better, not to lose cognitive ability. The tool must make the user think harder. It must not think for
the user.

Prior art: [learnharness](https://github.com/amosblomqvist/learnharness). The user liked two things: answers spoken aloud
(think-aloud), and the connected graph of ideas.

## Goals

1. An active loop: the tool asks, the user answers (typed or spoken), the tool grades and decides what comes next.
2. A learner model: for each concept, how deep the user knows it and when to review it.
3. A concept graph: ideas and their links, across all subjects and sources, with mastery shown on each node.
4. Difficulty that keeps the user at the edge: hard enough to struggle, not so hard that they stop. Target about 85% success.
5. Hints in steps, from the least to the most revealing. The tool never gives the answer before the user tries.
6. Local voice input for think-aloud answers.
7. All learning data in the shared vishalakshi vault, on its own shelf, so any tool (Sanketa, leela, ramabana) can search it.
8. Learn by code: a concept can become a code exercise in a notebook (leela), checked by running it.
9. Seed concepts from vedicreader (Sanskrit lessons, terms, jyotiṣa glossary) and from any document in the vault.

## Non-goals (for this first build)

- No new leela cell type and no change to leela. Leela already keeps unknown cell metadata and renders ipywidgets.
- No change to ramabana core. A ramabana extension file gives `/learn`.
- No network calls to vedicreader.com. Read the vedicreader repo files.
- No video generation in this build. "UI blocks for learning videos" is a later step.
- No writes to the user's real vault in tests. Tests use a temporary vault.

## Anti-goals (failure, even if it works)

- The tool gives answers. A hint that names the answer before the user tries is a bug.
- The tool is boring: easy questions on things the user knows.
- The tool is a quiz of recall only. Questions must ask for explanation, application and transfer.
- The tool hides its state. The user must see why a question comes next.

## Constraints

- Python, nbdev 3 on hatchling, fastcore style, `uv`. Notebooks under `nbs/` are the source.
- Stack the user already has: vishalakshi (vault), rishi (models, local audio), FastHTML (web), ipywidgets (notebooks), ramabana
  (agent, extensions).
- Loopback only for the web app. Port 5077 **(my call)**. Never touch :5001, :5010, :5055 or :9000.
- Prose in ASD-STE100, grade 9.

## The design

### Name and shape **(my call)**

A new package, `abhyasa` (अभ्यास, steady practice; Yoga Sūtra 1.12). The engine is plain Python with no UI. Four surfaces use it:

| surface | what it is for |
|---|---|
| `abhyasa` web app (FastHTML) | the main place to learn: today's queue, the session, the graph, voice |
| ramabana extension | `/learn` in the terminal, beside coding |
| notebook widget (leela, Jupyter) | learn by code: question cards and checked code exercises in a kernel |
| Sanketa (later phase) | search learnings beside vaults and ramabana sessions |

Why a new package and not inside ramabana or leela: the user does not want to overload leela. The ramabana recon showed that an
extension (`setup(reg)` with commands and tools) is the clean seam, and that a real "learn mode" can copy plan mode later. The
engine must be usable from all four surfaces, so it must not live inside one of them.

### Storage: the `learning` shelf

One shelf, `learning`, in the vishalakshi vault (default `~/.vishalakshi/vault.db`, or `$VISHALAKSHI_VAULT`). Every item is a
vault document, so it is searchable with keyword and vector search, the same as everything else.

| kind | source | text (searchable) | meta (state) |
|---|---|---|---|
| `concept` | `learning://concept/<slug>` | name, statement, aliases | subject, prereqs, related, depth, stability, due, floor, ceiling, misconceptions, provenance |
| `attempt` | `learning://attempt/<id>` | question, the user's answer and think-aloud, feedback | concept, depth asked, correct, confidence, hints used, grade, time |
| `session` | `learning://session/<id>` | a short summary of the session | concepts, counts, start, end |

State changes use `Vault.set_meta`, which does not re-embed. Edges are lists in concept meta (`prereqs`, `related`). This needs
no new tables and no change to vishalakshi **(my call)**.

### Learner model

For each concept:

- **Depth**, 0 to 5: 0 unseen, 1 recognise, 2 recall, 3 explain, 4 apply, 5 transfer (use it in a new case or another subject).
- **Floor and ceiling**: the highest depth the user reliably passes, and the lowest depth they fail. The probe brackets these,
  as learnharness does.
- **Stability and due date**: an FSRS-style memory model. A pass at the concept's depth grows stability; a fail shrinks it. Due
  date is when recall probability falls to 90%.
- **Misconceptions**: short text, kept from wrong answers given with high confidence.

The update uses correctness × confidence:

| | high confidence | low confidence |
|---|---|---|
| correct | solid: raise floor, grow stability, next time go deeper | fragile: keep depth, small growth, ask once more soon |
| wrong | misconception: lower ceiling, save the misconception, re-teach | gap: lower ceiling, small correction |
| "I don't know" | — | a real gap, not a wrong answer: ceiling at this depth |

Hint depth also counts: a pass with hints counts as a weaker pass.

### Choosing the next question (an algorithm, not only the LLM)

1. Due reviews first (concepts past their due date), lowest recall probability first.
2. Then the frontier: concepts whose prereqs have floor ≥ 3 and whose own floor is below the goal depth.
3. Ask at depth `floor + 1`. After two clean passes in a row, jump by 2. After a miss, go down 1. After two misses in a row on one
   concept, switch to its weakest prereq.
4. Mix subjects only when the user asks for it (interleaving is an option, off by default) **(my call)**.

The LLM writes the question for the concept and depth the algorithm chose. The algorithm owns the choice, so the user can see why.

### Question kinds

- `predict`: before teaching, guess. The guess does not need to be right.
- `explain`: in your own words (good for think-aloud by voice).
- `apply`: a worked problem.
- `transfer`: a new case, or a link to another subject.
- `code`: write a function; tests check it (notebook surface).
- `choice`: multiple choice where each wrong option matches one named misconception.

### Grading

An LLM grader gets the concept, the depth, the question, the reference answer (written when the question was written, never shown
to the user), and the user's answer and think-aloud. It returns structured JSON: `correct` (bool), `grade` 0–10, `first_error`
(where the reasoning first goes wrong, without the fix), `misconception` (or empty), `feedback`. Code exercises are graded by
running their tests first; the LLM only comments.

### Hint ladder

Six levels, one per request: point attention → describe the pattern → name the category → name the idea → outline the move →
one worked step. The tool never gives the full answer. The user can ask to "show the answer" only after a real attempt, and that
counts as a fail.

### Teaching

When the user fails, the tool teaches the smallest step that fixes the first error. Then it asks a new check question on that
step. It does not lecture.

### Concept extraction (the graph grows from sources)

- `extract(text, subject)`: the LLM lists the core ideas as concepts (name, a true self-contained statement, aliases) and the
  prereq links between them.
- Dedupe: for each new concept, search the `learning` shelf for near matches. Same slug or a very close match means "the same
  concept"; merge aliases and provenance. The merge is plain code **(my call)**.
- Sources: any text, any vault document (by doc id), and vedicreader (below).

### vedicreader import

Read the repo files only (path from `$VEDICREADER_ROOT`, default `~/code/personal/orgs/vedicreader`):

- Sanskrit lessons: `static/learn/order.json` gives lesson order (each lesson is a prereq of the next in its unit). Each lesson
  becomes a concept. Its `check` blocks become ready questions with reference answers.
- Sanskrit terms: `static/grammar/terms/*.json` become concepts. `related[]` becomes `related` edges.
- jyotiṣa: `vr/jyotisha/explain/*.json` becomes concepts (graha, rāśi, nakṣatra). The Python primer chapters need an import of
  vedicreader; that is a later step.

### Voice

The browser records audio (MediaRecorder) and posts it to the app. The app transcribes on the machine:

1. Default: Gemma 4 E2B on LiteRT through rishi (`Chat(gemma4_e2b)(['Transcribe this clip.', wav])`). The model is already in
   the Hugging Face cache **(my call)**.
2. Option: mlx-audio Whisper, with `ABHYASA_STT=whisper`.

The transcript goes into the think-aloud box. The user can edit it before they send.

### Models

`abhyasa.llm` makes one call shape: `ask(prompt, sp) -> str`, and `ask_json(prompt, sp) -> dict`. The default is rishi `Chat`
with the model in `$ABHYASA_MODEL` (default `claude/sonnet`) **(my call)**. In ramabana, the extension uses `agent.oneshot`, so
ramabana's routing applies. Tests use a fake.

### Web app

FastHTML + HTMX, served on 127.0.0.1:5077 **(my call)**. Muted, readable, no boxes in boxes (from the Sanketa feedback). Pages:

- **Today**: due count, frontier, subjects; "Start" begins a session.
- **Session**: one question at a time. A big think-aloud box with a mic button; a confidence slider; "I don't know"; "Hint". After
  grading: feedback, the first error, and what comes next and why.
- **Graph**: a d3-force graph of concepts, colour by depth, size by due-ness. Click a node to see its state and start a session on it.
- **Add**: paste text or a vault doc id, pick a subject, extract concepts.

### ramabana extension

`abhyasa/rama.py` has `setup(reg)`. It adds `/learn` (`/learn`, `/learn <topic>`, `/learn due`, `/learn graph`) and tools that
let the coding agent record that the user learned something. To turn it on, link the file into `~/.config/ramabana/extensions/`.
I do not change the user's config tonight **(my call)**.

### Notebook widget (leela)

`from abhyasa.nb import learn; learn('rrf')` shows an ipywidgets question card in the cell. `exercise('concept')` writes a code
exercise: a markdown question, a stub cell, and a test cell, tagged with `metadata.abhyasa`. `check()` runs the tests and records
the attempt. This works in leela because leela renders ipywidgets and keeps unknown cell metadata.

### Sanketa (later phase)

Sanketa does not read vaults today. Plan: a read-only adhara search over the shelves (`store`, `leela`, `learning`, ...), a new
result kind, and an open action (`abhyasa://concept/<slug>` opens the web app). Keyword search only at first, because Swift has
no query encoder yet. This is a separate change in a Swift repo; it is not in tonight's build.

## Left to the builder

Module layout, prompt wording, the FSRS constants, the CSS, test structure.

## Order of work

1. Engine: store, learner model, scheduler, LLM wrapper, tutor loop, grading, hints. Tests with a fake LLM and a temporary vault.
2. Sources: extraction and vedicreader import.
3. Web app with voice and graph.
4. ramabana extension.
5. Notebook widget.
6. Sanketa: plan only.
