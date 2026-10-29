# Release notes

<!-- do not remove -->

## 0.0.12

- Demo ladder: when you miss an idea after its demo, the tutor teaches it in another way, then shows a simpler demo, then steps back to a prereq (setting: More help after a demo).
- Feedback: under each demo and each lesson, a quiet row asks "Too simple · Just right · Not clear". "Not clear" opens a short box that you can speak into. The tutor uses your choice and your note for the next demo or lesson of the idea, on the demo ladder, in the ways that work for you and in your profile (setting: Feedback under a demo or a lesson).
- Code runner: learner code cannot send a signal to another process.
- Code runner: the report goes to a private pipe, not to stdout. On macOS, `sandbox-exec` stops the network and writes outside the temp folder. On other systems, the guard does its best, but it is not a full block.
- Code runner: learner code can still fool its own checks (for example through `ctypes`). The checks are for learning. They are not a proof.
- Code runner: `logging`, `inspect.stack` and `traceback` do not work in learner code in the closed process.
- Side pane: a page in the pane can ask to open an http or https link in a new tab (`rh:link`). Other schemes are refused.
- When the tutor cannot make a walk, a side walk or a term, the page shows a plain line. The log keeps the error.
- A code check refuses more than 100 000 characters of code.
- Code runner: the app keeps at most 64 KB of the output of learner code and reads at most 1 MB of the report. A larger report is an error.
- Your journeys: a side walk opens in the pane beside the step that opened it.
- Search gives the number of hits that you ask for when the shelf has them.
- Walks from links: a folder such as `go` or `ui` is not a language folder.
- Walks from links: a redirect to a folder higher on the same host keeps the folder of the link.
- Sources under a lesson: a link to a vault document opens the document in the side pane. A cmd-click still opens a new tab.

## 0.0.11

- Guided walk: make a walk from a paper, a text or a topic. Each idea is a step with one check.
- Rabbit holes: learn a missing idea in a side pane (⌥B opens, ⌥Z or Esc closes).
- Walks from links: a web page, docs site, PDF, arXiv link or GitHub repository.
- Open in Leela: a tool walk asks short-answer and order checks here, and a step that needs code links to Leela.
- The code runner can use another Python and allow a local socket pair, for Leela.
- Settings has every value in 11 groups, with the range and the default of each. The number of ideas in a walk is 12 by default.
- A new look for the walk, Add, Graph, Today and Profile pages.
- Fix: ⌥F opens the keyboard shortcuts again.
- Needs fossick 0.1.22, which checks each redirect and verifies TLS.

## 0.0.10

- Settings: choose the model for each tutor task from a list of known names, in groups by provider. A saved choice stays. "Type another model id…" gives a text box.
- The app, the docs and the help text say "your vault" and "the model", in place of package names.
- The Mac app: the Settings page in the app chooses the speech model. Before, the Mac app always set the speech engine to gemma, so a choice on the Settings page had no effect.
- The Mac app opens `abhyasa://vault/<shelf>/<id>` links in the vault viewer. Sanketa uses them to open vault results.
- The Mac app: choose the default model from a list.
- The README has a Download for macOS button and Homebrew steps. All docs use plain English.

## 0.0.9

- Keyboard shortcuts page (⌥F, or ? outside a text box). It lists every key, by where it works.
- Sanketa shows abhyasa's keys when abhyasa is in front: abhyasa writes `~/.config/sanketa/packs/abhyasa.toml` when it starts. It does not write over a pack that you made.
- A page that is drawn again shows a lesson that you asked for one time, with no old button.

## 0.0.8

- Strengths and weak spots (⌥G): each subject, your weak concepts with the reasons, your strong concepts, and the ways you learn. "Practice my weak spots" starts a drill session.
- Ways to learn: each question uses code, maths, an analogy, a worked example, a picture or plain words, and the outcome counts for it. A weak concept gets your best way. Sometimes a concept gets a new way, first a way that you got better at. You set how often.
- Say "show me with code" or "with an equation", and the tutor switches. "Another way" (⌥A) under a lesson teaches the same idea in a different way.
- A gap that you name ("I don't know what the loop means") becomes a concept, linked to the one you learn. It comes first next time, and it does not block.
- The graph can colour each concept by how well you know it, and its tip gives the reasons.
- The profile reads the whole conversation of each question, the lessons you asked for, your method counts and your calibration.
- A session gets easier after two misses and harder after three clean passes, and it retests each miss before the end.
- About you shows how often you are right when you feel sure.
- A transfer question can connect to an idea that you know well from another subject.

## 0.0.7

- After a shaky pass, "Teach me this" (⌥X) gives a short lesson from your first error. Your outcome does not change.
- When you say you do not know a term, the next nudge explains it first.
- The grader reads past speech-to-text noise, and judges a restated point with the earlier one.
- The close says your level in plain words: "Not at a level yet. Next review in 12 h."
- The index tick needs pobblebonk 0.0.6, so a quiet tick leaves no empty note.

## 0.0.6

- The app answers only this Mac. It refuses a request with a foreign Host, a cross-site request, and a change from a foreign Origin, so a web page cannot start a session or set your key.
- Exercises that a model writes are checked first. Their tests run with safe builtins and a time limit.
- If the lesson model fails, the question still closes, the miss counts one time, and you see the model answer.
- "Sure?" starts with no step picked. With no confidence given, a clean pass is solid and a wrong answer is a gap, so a spoken answer can count as solid.
- Slugs read Indic scripts: `संधि` gives `samdhi`. C, C++ and C# get different slugs. `Learning.reslug` moves concepts with old slugs, and every link to them.
- A JSON reply with a code fence inside a string no longer fails.
- Settings refuses an API key with a newline or a space, and says why.
- The index tick works with no ramabana history yet, and reads only notebooks that changed.
- `/a` and `/ans` answer in ramabana, and `/learn` stays on the newest agent.

## 0.0.5

- Journeys. Say a goal, such as "learn LLMs", and the tutor plans a path of topics from your graph, with new concepts for the gaps. You can move, skip, mark known, split, add or remove a step. A journey session asks about the current step, and the path fills in as you learn.
- Your learning: a week view, what moved each week, and each session with what moved and the misconceptions found. You can continue a session, review its misses, or read its questions again.
- Sessions are kept as you go, so a restart continues the same question.
- About you: a short first conversation, your own edits, and changes from the tutor, each with its reason and an Undo. The tutor uses it in questions, lessons and plans.
- Never stuck: a line above each title shows where you are, Esc goes up one level, ⌥T goes to Today, and "Continue" (⌥C) is always in the top bar.
- Voice everywhere: each answer box has a Speak button, and ⌥D dictates into the box that has focus, on any page.
- Five themes (Paper, Ink, Manuscript, Clear, Sage), each with light and dark, set in Settings.

## 0.0.4

- A session shows one question at a time. The earlier questions are a quiet list at the left, with the outcome of each. A click, or ⌥↑ and ⌥↓, opens one to read. On a narrow window the list folds.
- A session on one concept stays in its subject, and goes next to the concepts linked to it.
- Vault text shows raw HTML as text. A saved web page can no longer play a video or run code in the app.
- The app icon, the favicon and the docs icon.

## 0.0.3

- The session is a chat. Each question is one conversation: you send only your follow-up, and the tutor grades the whole conversation and answers your last point. Hints and the lesson sit in the conversation, and the composer stays at the bottom.
- Waits are clear: a progress bar, the task and its seconds on the button you pressed, and placeholders. Text boxes grow with their text.
- A model for each tutor task (question, grade, hint, lesson, extract), set in Settings from ramabana's catalogue: Claude, Codex, OpenAI, Copilot, Gemini and local models. A test times one call. Install the catalogue with `abhyasa[models]`.
- Speech: dictation stays on and cuts your speech at pauses, and the text comes in as you talk. Gemma 4 E4B is the default; Whisper, Parakeet, Qwen3-ASR and OpenAI are options. Settings finds, gets and switches speech models.
- The graph has levers: four layouts (free, path, rings, groups), spacing, size, colour, filters, find and focus. It keeps your arrangement.
- A vault viewer shows any vault document, with the resume command for a session and "Learn from this".
- Interactive demos from rupaka. A demo asks you to predict first, and it shows the result only after you lock in. The tutor makes one after two misses with a saved misconception, or for a concept with `visual: true`, and "Show me a demo" (⌥E) makes one on request.
- A prediction in a demo counts in the learner model: at depth 2, or at depth 3 when you write why.
- `/due.json` gives the count of due reviews, for the Mac app's Dock badge.
- The session key is kept in the config folder, so the app starts from any folder.

## 0.0.2

- A ramabana tick indexes your sessions on its own. `abhyasa-index schedule` adds the `abhyasa-index` schedule to pobblebonk, and ramabana's beat runs it every 15 minutes.
- The index also takes ramabana's memory: each project's `MEMORY.md`, and the learned `AGENTS.md` and skills, with kind `memory`.
- `abhyasa-index` exits with code 0.
- Tests set the vault to a temporary file, so no test can open your real vault.

## 0.0.1

- First release. abhyasa asks you questions, grades your reasoning and never gives the answer before you try.
- A learner model keeps a depth from 0 to 5 for each concept, a floor and a ceiling, and an FSRS-style review date.
- Code, not the model, picks the next question: due reviews first, then the frontier of concepts whose prereqs you know.
- A wrong answer gets the first error and a nudge. Hints come in six steps. After three tries, the tutor teaches the smallest step and asks its check next.
- All data is on the `learning` shelf of the vishalakshi vault, so other tools can search it.
- Concepts come from pasted text, a vault document, or the vedicreader repo (Sanskrit lessons and terms, jyotiṣa grahas, rāśis and nakṣatras).
- A web app built from blocks: today, session, graph, concepts, search, add and voice. Speech to text runs on this machine with Gemma 4 E2B.
- `/learn` for ramabana, and question cards and checked code exercises for notebooks.
- The tutor grounds questions, grades and lessons in your own sources: the shelves of your vault and the vedicreader library. It shows the citations after the question closes.
- Each concept links to the places in your work that name it. `abhyasa-index ramabana` and `abhyasa-index notebooks` put your sessions on vault shelves, so every tool can search them.
- The app works offline: fonts, htmx, marked, KaTeX and d3 come with the package.
