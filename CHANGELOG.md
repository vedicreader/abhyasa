# Release notes

<!-- do not remove -->

## 0.0.12

- Sort my concepts: the tutor asks again one time for each concept that got no group, and a short "Other" group is the last resort. For a concept with no subject, it also proposes a subject (one you have, or a new one). The proposal says how many it placed and names the ones it left for you.
- Walks from a link or a paper: new concepts get a subject (the Subject field, or one that the tutor picks), and a name that was a slug shows as words. Old concepts with a slug name get words once.
- Research: a walk step with no source passage (a walk from a topic, the walk of a talk from a journey) gets a source from the web. The tutor searches the web for the idea, reads the best 3 pages with plain HTTP, and quotes one passage of at most 600 characters. It keeps the passage only when the page has it word for word. The page goes into your vault as a web document and is linked to the concept, so lessons, slides and your sources find it (prompt: Source finder).
- Research: the walk opens at once. Each step says "Looking for a source…" while the tutor looks, then shows the quote with "From the web: <site> · <title>". The title opens the copy in your vault in the side pane, and "Open the page" opens the page in a new tab. The note of the step is written again from the passage.
- Research: when no page has a good quote, the step keeps the tutor's words and says "No source found." "Find a source" tries again on any step with no passage.
- Research: a talk from a journey looks for sources before it makes the slides, so a slide shows the quote, and the editor names the page.
- Research: the tutor reads only public hosts: never this computer or a local network, never a video or a social site, and never through a browser. It reads only HTML and plain text pages, never a file such as a PDF or a zip, and never a host in percent codes. It caps the bytes, the speed and the time of each page, reads pages only in the background on its own pool, so a demo or a note never waits for it, and writes each URL that it reads to the log. It never files over a page that is in your vault: a changed page becomes a new document, so older steps keep their links.
- Settings: a new Research group. "Find sources on the web" (on by default) turns research off: then the tutor does no web search. "Steps to research in a walk" (12) and "Search results to read" (5) set the limits. The Add page and the Journeys page say that the search sees your topic.
- An open check stays open after the app restarts.
- Present shows on a started walk, on its last page and in Journeys.
- Talks: when the talk is made, the tutor writes 2 to 4 points for each slide that has no passage (for example each slide of "Present this journey"), and speaker notes for each slide that has none: what to say, a question for the room and a confusion to watch for. It uses your sources when they name the idea. You can change the prompt (Talk slide) on the Settings page.
- Talks: the room sees the points of a slide, with the `body` beat, and its type gets smaller when they do not fit. The room never sees the speaker notes. The presenter window shows the notes and the line "From your sources". The editor has a Points box for each slide with no passage.
- Talks: an old talk with slides that have only a title offers a quiet "Fill the slides" button in the editor. The tutor writes the points and the notes of those slides in the background. A slide that you change at that time keeps your change.
- Talks: maths in a slide shows as maths, in the presenter window and in the audience window: the title, the section, the points, the notes, the question and its options, the Next row and the question on the room screen. When there is no choice question, the question for the room is the one that the tutor writes with the slide. Else it reads well for any name of an idea: "Say in one or two sentences: why scale by …?" in place of "what is Why scale by …?". "Fill the slides" also changes the old question of a slide, but never a question that you wrote.
- Talks: a slide with no passage can show a figure from your vault: the first image of a vault passage that names the idea, when the folder of that document has the image file.
- Talks: the tutor gets each passage of your sources as data between `<source>` markers, so a line in a passage cannot act as an instruction. The notes of a slide have a length limit.
- Walks: a step with no passage (as in a walk from a topic) gets a note that explains the idea from its statement and your sources (prompt: Walk note with no passage). A note that says that no passage was given is not used: the statement of the idea shows in its place.
- Talks need rupaka 0.0.6.
- Demo ladder: when you miss an idea after its demo, the tutor teaches it in another way, then shows a simpler demo, then steps back to a prereq (setting: More help after a demo).
- Feedback: under each demo and each lesson, a quiet row asks "Too simple · Just right · Not clear". "Not clear" opens a short box that you can speak into. The tutor uses your choice and your note for the next demo or lesson of the idea, on the demo ladder, in the ways that work for you and in your profile (setting: Feedback under a demo or a lesson).
- Code runner: learner code cannot send a signal to another process.
- Code runner: the report goes to a private pipe, not to stdout. On macOS, `sandbox-exec` stops the network and writes outside the temp folder. On other systems, the guard does its best, but it is not a full block.
- Code runner: learner code can still fool its own checks (for example through `ctypes`). The checks are for learning. They are not a proof.
- Code runner: `inspect.stack` and `traceback` do not work in learner code in the closed process.
- Side pane: a page in the pane can ask to open an http or https link in a new tab (`rh:link`). Other schemes are refused.
- When the tutor cannot make a walk, a side walk or a term, the page shows a plain line. The log keeps the error.
- A code check refuses more than 100 000 characters of code.
- Code runner: the app keeps at most 64 KB of the output of learner code and reads at most 1 MB of the report. A larger report is an error.
- Your journeys: a side walk opens in the pane beside the step that opened it.
- Search gives the number of hits that you ask for when the shelf has them.
- Walks from links: a folder such as `go` or `ui` is not a language folder.
- Walks from links: a redirect to a folder higher on the same host keeps the folder of the link.
- Sources under a lesson: a link to a vault document opens the document in the side pane. A cmd-click still opens a new tab.
- Vault documents: the page shows the images of a PDF from the assets folder of that document. An image that is not there does not show.
- Add: a web link or an arXiv id in the vault document field makes a walk from the link. A vault name that matches no document gives a plain message.
- Add: a paper link (arXiv or PDF) is read in full. The wait line says "Reading the paper", and the page count to read does not show for a paper.
- Concepts: the page shows your concepts as a tree, with groups of two levels at most under each subject, and a count on each group. The find box finds a concept in any group and opens its branch. "Sort my concepts" asks the tutor to put your concepts in groups, and you accept or cancel the tree before it is saved (setting: Concepts in one sort). A new concept gets a group from the groups that the subject has. On a concept page, the Group field moves the concept by hand, and the tutor does not move it after that.
- Talks: present a walk to a group. Each idea is a slide, the tutor note is your speaker note, and the check is a question for the room.
- Talks: present a plain journey, too. "Present this journey" makes a talk from its steps, in their order: the first steps, up to the Ideas in a walk setting (12 by default). Skipped steps are left out. The next time, open the same talk, or make it again as a new talk with the date in its title. The editor says when the journey changed after the talk was made.
- Talk editor: change the order, the beats, the notes and the question of each slide, and set the minutes of your slot.
- Two windows: the presenter window has your notes, the next slide and a clock. The audience window goes on the projector (F fills the screen).
- Talk keys for the left hand: D next, A back, G go to a slide, Q ask, R show the answer, X laser, B blank, E into the demo.
- Ask the room with hands: press the option that most hands chose, then R shows the right answer.
- A demo on a slide shows the same state in both windows. The room sees if your pick at a gate is right only after R.
- The side pane in a talk: ⌥B opens a short primer beside the slide in both windows, in large type and with no check. D and A turn its pages. ⌥Z closes it.
- After the talk: where the room was unsure, the talk slide by slide, a recap file for the room, and a follow-up walk.
- The answers of the room and your pick at a demo gate in a talk do not change your learning.
- After a wrong try, the answer box and the think-aloud box are empty for the next try. The earlier try shows in the record of the check.
- The error line shows the reason that the app gives when it refuses a request (up to 200 characters). After a 409 it adds a link that loads the page again.
- A draft answer and its think-aloud text stay across a reload or a restart, in a walk check and in the session. They go when the answer is sent. A code editor keeps its own state.
- Graph: the page uses the whole window, and the graph fits its nodes in the canvas again when the canvas changes size.
- You can drag the edge of the side pane and of the Graph tools to resize them. The edge has a line and a small handle, and a tip shows the first time. Arrow keys move it, 1, 2 and 3 set a third, a half and two thirds of the window (the pane), and a double-click resets it.
- Graph: each cluster has a label and a soft region, and Group by can use the concept groups.
- Talks: a question can take its answer from a run (for Leela).
- Stage messages: a run question (`ask` and `result` with kind `run`) and a new `output` message, so a host can show what a run printed.
- Core: `room_spec` (a demo spec for the audience window, with no gate answer) is now in `abhyasa.core`. The talk block calls it from there.
- Code runner: `logging` now works in learner code in the closed process (`logging.info` and the like). `inspect.stack`, `traceback` and `sys._getframe` stay refused.
- Talks: a narrow presenter window (with no side pane) now stops D at the real last page of the primer. The audience window tells the page count in a `pages` stage message.
- Your learning: the page of one past session shows what you said about a question (Too simple, Just right, Not clear, and your note), in the same quiet lines as the concept page.
- Talks: when a demo shows alone on the slide and its text would be under 14 px, the demo keeps 14 px in a taller box that scrolls. The scroll of the presenter window shows in the audience window.
- Walks: the outline on a step page draws the maths in the names of the ideas, not raw TeX.
- Walks: the items of a put-in-order check use the body size of the page, not a size that grows with the card.

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
