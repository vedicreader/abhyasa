# Release notes

<!-- do not remove -->

## Unreleased

- A host app, such as Leela, can run abhyasa in its own process. The host gives the session cookie, the settings, the privacy guard and the folder for the files. A hosted abhyasa reads no key or settings file of its own and makes no agent of its own. `HOST_API` (`abhyasa.core.hostapi`) is the contract number, now 1. A host can check it before it starts.
- New module `abhyasa.agent_tools`: the learning operations of a host agent, as tools with one result contract. The agent can make a walk, change a walk, add a source, restore a version and explain the step on screen. `explain_here` makes no model call: it gives the agent the data and the rules.
- A host passes the settings rows for one call. A write to the settings is refused while it does. The host owns its settings.
- Background jobs run in the context of the call that submitted them.
- A walk goal takes web sources through the hook of the host, when the research setting allows it. A host can run the research as its own job.
- A host can take the keys and Esc of the talk stage and the detour page, open a course page itself, and open a concept from a click in the graph. The talk stage can run in an element of a host page. The page of the keys, the top bar chips (`/nav/extra`) and the graph theme listener go with their page.
- The privacy setting no longer shows as "the tutor failed" when it withholds a walk check. The page says so.
- Search takes a document only when it matches a word of your query. Labels are no concepts. Option+D types an answer without a microphone.

## 0.0.21

- A model chip shows which model runs, on the builder, the talk editor, the walk step and the guide. Click it to pick another model. The pick saves the same setting as Settings, so the two always agree.
- The builder runs on Claude Opus until you pick its model. `--model` and `$ABHYASA_MODEL` also set it.
- A new builder tool, restyle, changes only the words of a talk: titles, points, notes and questions. It keeps every passage, code piece and demo. A request to change the language or the style goes to restyle and never makes the talk again.
- A style rule such as "Simplified Technical English" no longer turns on code mode, and a sentence about language or style is no longer dropped as a rule about the shape of the talk.
- The builder knows when you press Undo, and it does not undo the same change again. Its own Undo says what it takes back.
- The builder sees more of each slide: the passage or code, the start of the notes, and which slides share the same passage or code. Each change says which parts of which slides changed.
- No two slides get the same code piece.
- The talk and walk pages take a builder change when the builder pane is closed or runs in another tab.
- An open editor row says Done, and a quiet Saved shows after each change.

Known issues:

- A restyled slide whose new words add a number keeps its old words. The result says which slide.
- The builder does not save a style request as a rule of the brief, so a later full remake does not keep the style.
- The refresh of a page from a builder in another tab is tested in Chromium only, not in the Mac app's window.

## 0.0.20

- A slide that shows only a passage can be rewritten. Before, its list of points was empty, the model kept it empty, and abhyasa took the empty list as a bad reply, so every rewrite of such a slide failed.
- A failed rewrite says why: "The tutor could not rewrite slide 3: <reason>. Nothing changed." The full error goes to the server log. Before, every failure gave the same message with no reason.
- A slide whose passage is also on another slide, or on another step of its walk, gets the best other passage of its idea from your source, with that section's heading.
- The builder's search for passages reads only the documents of the brief. Before, it searched the whole vault, kept the top hits of each shelf, and then filtered them by title, so a notebook on a full shelf could give no passage.
- The builder gets the reason of each failed change, and the other slides still change. It does not run the same failing call a third time.
- The line of a rewrite quotes a short form of the instruction.

## 0.0.19

The fixes for the known issues of 0.0.18. Needs rupaka 0.0.15.

- A 3D scene in a demo draws again when you come back to it, for example after a tab switch (rupaka 0.0.15).
- Code on a slide never runs past the right edge. abhyasa takes only code whose lines fit at the room's smallest size. It checks the code of an older slide when the talk opens, and drops code that is too wide but keeps the slide's words.
- The Lock in button, Try another and the reason box of a demo are hidden in the audience window. The presenter keeps them.
- Maths in a passage or a point is drawn with KaTeX, also when the source wrote it with no dollar signs, for example `c_n·e^{i2πnt/T}`.
- A research find has its clean page title, not "untitled" or a title with words joined to it. A kept link takes the title of the page that abhyasa filed.
- A step that the builder refuses is not shown under "What changed", and has no See it and no Undo.
- After an Undo, the builder shows only its last words for that turn, marked "Before the Undo:".
- A rule about the shape of the talk, such as "Start with a poll", goes into the rules, not the aim.
- When you ask for research, the walk is made one time, after the kept pages are filed.

## 0.0.18

Needs ramabana 0.2.108, rupaka 0.0.14 and rishi 0.1.67.

- **The builder.** Make and change a walk or a talk by talking to it, in a pane beside the walk or the talk. Start and Make a talk open it. Tell it your sources and their roles ("the notebook is the main source; where they conflict, use it"), whether to research, the aim, the audience and what to keep. The page changes as it works, one line for each step. After each turn, "What I read", "Conflicts" and "What changed" show what it did, with Undo for the whole turn.
- Research waits for you. Keep or Drop each find, or Keep all. A kept page is filed and read before the walk or the talk is made again.
- A talk fits its slot. Slides get shorter first, then neighbouring slides join. An idea is left out only at the end, and the reply names it.
- A talk from a notebook shows points from each section and one short code piece that parses, not the pasted section. Code lines never wrap; the code gets smaller to fit.
- Demos on slides: a second demo goes on a new slide. A walk step can have a demo. A demo fills the slide in the audience window. Its text follows its sliders. "Ask about this" puts a question with the demo's values in the builder. The room never sees it.
- Remake a talk for a new audience: new titles, the same poll, and no code when you say no code. The last slide names the notebook file, not its path on your Mac.
- The handout renders markdown, shows each title one time, and gives the answers at the end.
- Home shows your 5 newest walks and talks. "All walks" and "All talks" have 20 on a page, with a filter and a sort.
- A source row names its source and says "ready" or the real reason. Filing skips hidden and `_` folders.
- Lock is now Keep. Make it again is one item in the ⋯ menu.
- Known issues are in `docs/known-issues.md`.

## 0.0.17

### Talks

- Delete a talk from the ⋯ menu in its editor, from its row in Teach on Home, or from its row on the walk page. One line asks you to confirm. The talk goes with its runs, its recaps, its history of changes and the side walks that it opened beside its slides. Your walk, your answers and what you learned stay. Then the walk page opens, or Home when the walk is gone.
- You cannot delete a talk while you present it. End the talk first. You also cannot delete a talk while a job changes it. Stop the job first.
- Make a talk again from scratch: next to "Make it again" (which keeps your edits), "Make it again from scratch" writes the slides again from the walk and drops your edits. It is one change, so Undo gives your edits back. It runs as a job, with Stop and Do it again.

### Mac app

- Abhyasa.app pins abhyasa 0.0.16, and its lock file is new. `make ship` pushes the tap over HTTPS.

### Docs

- The README is short, with a tour in pictures. The details are on a reference page.
- `docs/decisions.md` keeps the decisions, and `docs/develop.md` tells how to test and release. The old plans, specs and screen mockups are removed.

## 0.0.16

Needs rupaka 0.0.12.

### Learn for understanding

- A walk from a paper or a book is a map of its main claim and 3 to 7 big ideas. Each idea has the understanding to get, a key question and the common wrong ideas. Details, such as sizes and scores, stay on the page to read, with no checks. A walk has at most 7 ideas.
- Each idea keeps `core` (the idea, with no sizes or scores) and `wrong` (the wrong ideas that learners often have). Old ideas get them when you meet them.
- A check asks you to explain, predict, compare, apply the idea to a new case, or judge a wrong idea. It does not ask you to recall a fact. Its words are plain and use the real names. An analogy shows only as "where does this analogy break?".
- The grade passes the core idea in your own words. Extra points only add. From depth 4, a pass also needs an edge case or a new case. A slip is a slip, not a misconception. A misconception stays only when it is a known wrong idea or it shows two times. A recital of the page that does not use the case of the question fails.
- Feedback names the gap in your understanding. A right pick with no reason asks for the reason, and "Correct." never follows "I don't know". A demo names the reason, not "The answer is X".
- The tutor writes for your level. A line from what abhyasa knows about you goes into each teaching prompt: new, a gap, shaky, fading or solid, the needs that are not in place, and your profile. Shaky or a gap: simple, one idea at a time, the gap first. Solid: short, with an edge case. All the teaching prompts share one set of rules (`teach.human`).
- Text that the tutor writes for you must be plain English at grade 9. A text with long sentences, a high reading grade, semicolons, vague words or nicknames is written again one time, and the new text stays only when it is better and keeps the numbers and the maths (`checks.readable`).
- Words to know names a term by its alias only in a subject of the walk, so "numbers" in a walk on neurons does not name a grammar term.
- `tools/eval_understanding.py` scores the chain from idea to feedback on a copy of the vault, before and after a change.

### The screen guide

- The board of the guide is in rupaka 0.0.12. Its side panel has one shape: a table, a list, a flow of boxes with loops and branches, a faded example, a card of a wrong idea, or three stages from a case to the symbols. When you ask for a diagram, the panel draws one.
- A follow-up builds on the board that shows: the old marks stay, the old panel stays at the top, and the new example comes under it. The guide knows what the earlier panel showed.
- A panel line that is too long is cut, not dropped. A panel with nothing in it does not show. Labels on the page never cover each other. The log says why a board line dropped.

### Walks

- Change a walk with one box at its top: write what you want, and push Return. The tutor makes the changes and shows what changed, with Undo. "Redo the rest" makes each idea that is not locked again. Locked ideas never change. Each idea has Lock and a ⋯ menu with Skip and Remove. The old Improve the walk part and the buttons of each idea are removed.
- Delete a walk from its ⋯ menu or from its row on Home. Your answers and what you learned stay. Its side walks go with it.
- Make this walk again, in the ⋯ menu, plans the walk again from its source. Locked ideas stay in their place, what you did on an idea stays, and Undo takes it back.
- A walk from one of your notebooks uses the notebook as it is: one idea for each section that teaches, in its own words and code, with a check, and a demo where its code draws. A setup section, such as the imports, is not an idea.

### Jobs

- Each job has Stop and Do it again: a demo, a 3D explainer, a walk from a link or a goal, a change from the box, Make this walk again, a notebook, a course plan, a talk, research and a model download. Stop ends the job at its next safe point, and a result that comes after Stop does not stay. The activity chip also shows stopped jobs.

### Leela

- Open in Leela is on each notebook that abhyasa shows: a source line, a notebook link, the vault page of a notebook, an idea from a notebook and a notebook check. It opens the notebook at its section. When Leela is not running, the page says how to start it.
- A notebook walk opens a learning copy in Leela, with the demos of the walk after their sections and a link back to the walk. The copy runs in the folder and the environment of your notebook. abhyasa never writes your notebook, and it keeps the changes that you make in the copy.

### Code

- The engine is six notebooks: `00_learner`, `01_models`, `02_sources`, `03_tutor`, `04_path` and `05_show`. The old module names are gone.
- The voices on this Mac are Pocket TTS and the browser, and OpenAI is hosted. A Kokoro setting from before speaks with Pocket TTS.

### Before this

- The hand font of the paper (the board panel, the Show cards and the Mac overlay) is Patrick Hand (OFL), which rupaka 0.0.9 ships. It is easier to read than Caveat. abhyasa serves rupaka's font files and its `@font-face` rules (`font_css`) at `/assets/hand.css`, so it works offline. Caveat is removed. abhyasa needs `rupaka>=0.0.9`.
- In the Start box, the line of what Start does and the Start button now come above the sources of the goal, so you see Start however many sources there are. With more than 6 sources, the first 5 show, and "Show all N sources" opens the others.
- Abhyasa.app runs until you quit it, as Leela does. When you close the window, the app, its menu bar mark and the server keep running. The Dock icon and Open Abhyasa in the menu of the mark open the window again. Quit (⌘Q, or Quit Abhyasa in the menu of the mark) stops the server. Before, the app quit when you closed the window, unless research ran.
- The other background jobs are in the activity chip too: a demo or a 3D explainer that you ask for, Improve the walk, a talk (Present, Fill the slides, Make it again), Sort my concepts and a model download in Settings. Each one has a stored row with a line of what it does now and a link to its page. The card of each job changes when its job changes (the event stream), and asks again every 30 seconds when the stream is not there. Before, each card asked the server every 1 or 2 seconds. The demo card still shows its real stage ("Writes the demo", "A try failed the checks. Writes it again"), and its seconds count on the page. The demo of a walk step, a simpler demo, the demo after a miss and the lesson of the demo ladder have quiet rows: the page shows their wait, and the chip does not list them.
- "Find concepts only" under the Start box is removed (`POST /add`). It filed concepts with no walk and no check. Start makes a walk, and the Library shows the concepts of each walk. `GET /add` still opens the Start box on Home.
- Speech to text on this Mac uses Qwen3-ASR 0.6B (8 bit, 1.0 GB) with mlx-audio by default. It reads the terms of the idea as hot words. With the hint, it wrote all 9 key terms of the test clip, and 5 seconds of speech take 0.14 s. Whisper large-v3-turbo is the second model in Settings, and the Hugging Face search and OpenAI stay. Gemma is no longer a speech engine: its model was 3.7 GB and 5 times slower. A setting or `ABHYASA_STT` of `gemma` now gives Qwen3-ASR. Nothing rewrites your settings file. The `stt` prompt is gone with it.
- The voice of the guide on this Mac is Pocket TTS by Kyutai, with the voice `caro_davy`. It comes from the pocket-tts-mlx package (MIT code, CC-BY-4.0 weights). Settings, Speaking voice lists its 21 English voices. The download is 225 MB, one time, from Settings. Until it is on this Mac, the browser speaks (the Mac guide uses the Mac voice). OpenAI and the browser voice stay. On this Mac, a line of 3 seconds takes about 0.5 s when the voice is loaded.
- Kokoro is removed, with spaCy, misaki, espeak-ng, phonemizer and num2words, and the spaCy model that abhyasa unpacked into the config folder. The `voice` extra is now `mlx-audio` and `pocket-tts-mlx`. A Kokoro or Hugging Face voice setting now gives Pocket TTS. The search for text to speech models is gone. The speed setting shows only for OpenAI, because Pocket TTS has no speed. The words light up by their length, as with OpenAI.
- Kokoro is removed again: the voices on this Mac are Pocket TTS and the browser.
- The Mac Settings list of speech engines is "On this Mac (Qwen3-ASR)" (`mlx`) and Whisper.
- The ramabana `/learn` extension (`abhyasa.rama`) is removed. Learn in the app, and code in Leela.
- Your data: under Add a source, choose "My data for the exercises" to keep a folder as the data that the exercises run on, such as a folder of Ramayana episodes. You can also add it under "Your data" on the course page, with a note, and remove it there. abhyasa does not file it and does not learn from it. The course and its walks keep it as `data`. The planner and the tutor that writes a notebook step see its name, its note and its files, and the notebook spec that Leela reads always has it.
- The vedicreader import, the vedicreader verse source and the Ramayana episodes source are removed, with the Open in vedicreader link. The Sources page has no Add more sources part now.
- The words of the web app are plainer and shorter, with one word for one thing: walk, idea, course, stage, side walk, vault. "Change the walk" is the page that changes a walk (before: "…, the plan of the walk"). "Learn it" opens a side walk (before: "Learn beside"). The research line says "1 of 5 ideas have a source" and how many quotes abhyasa left out. The Start box asks "What do you want to learn?". The tutor talks to you as a kind, clear person: one point at a time, at most 3 sentences after a wrong answer, and no report style such as "You assume that…". Today shows one top card: the course card or Continue where you stopped, whichever you used last. The stage list of a course shows one number for each stage.
- abhyasa no longer indexes ramabana sessions and memory or Leela agent notebooks into your vault. What is already in your vault stays. The `abhyasa-index` command, its ramabana tick and the Index buttons on Sources are gone. A folder that you attach to a walk still files its notebooks.
- You can ask the guide a follow-up question, such as "say that more simply" or "why?". The guide sends your last 3 questions on this page and the lines of their boards with the new question. Under the box, "Follows up on: <your last question>" shows, with × to start fresh. The guide forgets the questions when you go to another page, after 10 minutes with no question, or when you push ×. It keeps them in memory only. The Mac guide does the same for each window.
- The guide draws a picture of a structure as a **diagram**: a card with named boxes and arrows, fixed at the top right of the window, under the top bar and beside the page text. On a narrow window it stands over the strip at the full width. The strip keeps only the step line and the controls. Each box is as wide as its text needs, in at most 3 lines, and never cuts its text. A cycle is a ring with an arc between each two boxes. A process or a tree is laid out in ranks with the fewest crossings. Each arrow starts and ends on the border of its boxes, and its words sit in a pill that covers no box and no other words. A diagram that cannot be drawn clean is not drawn. The guide draws a diagram only for a process of 3 to 5 steps, a cycle or a small tree, never for a formula: for a formula it gives an example from day-to-day life (a thrown ball, a garden, a taxi fare), marks the formula on the page, and can offer "show me". A diagram has at most 5 boxes of 32 characters, and arrow words of at most 3 words. Before, the model drew such a picture by hand over the text, and its labels covered the words. A hand-drawn sketch now marks only a part of a figure.
- Ask the guide "explain the gaps" or about your answer after a check grades it. The guide gets your last graded try: your answer, the feedback, the Error line and the gaps. Its board names the problem in your answer, explains the idea that fixes it, and shows the path to a right answer, in up to 4 steps. While you have tries left, it stops before the final answer. After the check closes, or after "I don't know", it gives the full worked solution. The board counts as one hint, as before.
- Ask the guide "show me …" on the page of an idea, and it opens the demo in a small card, not a board. The demo is made from your words, as with Show me. × or Esc closes the card.
- When you speak with Caps+E, the guide shows what it heard in the box and sends nothing yet. Change the words if you need to, then push Return to send them. Esc closes the box. The Mac guide does the same in its strip.
- Each page has a small Keys button at the bottom left. It opens a panel with the main keys of the page, and each key is a button that does the action. The panel says how to talk to the guide (hold Caps+E) and how to dictate (⌥D). In Abhyasa.app it also has "Use the guide over other apps…", which shows the first-use sheet of the screen guide. ⌥⇧F opens the panel. "Hide this" or Settings, Look turns it off (the setting `look.keys_float`).
- A short check on a walk has the Speak button (⌥D), and the guide box shows "Hold Caps+E to talk".
- The Sanketa pack gives each key a label of six words or fewer, in the key style of Sanketa. Sanketa's lint finds no errors and no warnings.
- Show me (⌥E) is on each walk step, under the title, and in the composer of a session. The demo comes from the open check, or from your words, not only from the idea. You can also type "show me …" in an answer box. This opens a demo and uses no try. Your words go to the model, so two asks on one idea give two demos. The plain demo of an idea stays as it was.
- The demo of an ask says which kind it is and why, in one line. A plain "show me" gives a 2D demo with a prediction first. "3D" or a physical thing asks for a 3D explainer, and "try", "code" or a library asks for Leela. "Show it in 3D" now makes a 3D explainer: the tutor writes a rupaka scene with bodies, forces, labels and camera shots, in 3 to 6 steps with one line each, and you watch it step by step with Back and Next. rupaka checks the scene, and the model gets one try to repair it. When it cannot make a valid scene, the card says so and shows the 2D demo. An explainer for the same words comes from the vault with no new model call. The 2D demo stays one click away. abhyasa serves three.js from rupaka, with no network, and a page loads it only when a scene shows. "Try it in Leela" opens Leela when it runs. After a Leela ask, "Show a 2D demo" is one click away.
- abhyasa keeps a record of each ask: your words, the place (walk step or session), the kind, the demo, and whether your first prediction in it was right (`Learning.put_ask`, `Learning.asks`). An ask never moves your level. The demo of an ask is not the check of the step.
- The Start box has "Pick folders…" beside the field. On a Mac, it opens the folder chooser, and abhyasa adds the folder that you pick with the same checks as a typed path. While you drag files over the box, it shows a dashed outline and "Drop files to add them as sources." A dropped folder says "To add a folder, use Pick folders." abhyasa refuses a source folder that you cannot read.
- Many folders in. Two paths that you paste with a space, a new line or a comma between them now give two chips. Before, they gave one bad chip, and the line said "2 sources". A path with spaces in its name stays one chip when you put it in quotes or when the folder is on this Mac as written.
- "Pick folders…" opens the folder chooser with more than one selection. Hold ⌘ to pick more than one folder. Each folder is its own chip. When you drop several files or folders on the Start box, each one is a chip. abhyasa files each dropped PDF, `.md` or `.txt` file in your vault.
- A goal walk has "Add a source" under its plan. Type a path, a repo or a link, or use Pick folders. abhyasa files each source on its own job, and the source joins the walk when it is filed. A line shows each source that is still filing.
- Each source of a goal files on its own job, at the same time as the others. The plan waits at most 20 seconds for the sources. A source that takes longer, such as the clone of a big repo, joins the walk when it is filed. Until then, the walk says "abhyasa is still filing <name>."
- A big code repo, such as huggingface/diffusers, files what a learner needs. abhyasa files at most 400 files in this order: the top README, the notebooks, the READMEs of `examples/`, its training scripts (`train*.py`), its other scripts, the English docs, the other text and the other code. Docs in other languages come last. One top folder gives at most 160 files until each other top folder has its files. Before, a repo with a notebook lost all of its `.py` files, and `docs/` used all 400 places. A course (one file in ten is a notebook) still files no other `.py`. The research agent reads the other files when it needs them.
- The Keys panel opens closed on each new page, also when you opened it on the page before. It opens by itself only on your first visit. It does not cover the text of the walk outline: it gets narrow at the left of the outline, or it hides. Esc closes a guide demo card or the guide box first, then the panel.
- Opening the link of a skipped course stage no longer plans it. The page shows that you skipped the stage, with a quiet "Plan it anyway" button. When abhyasa cannot plan a skipped stage, the stage stays skipped. Before, it showed as planned.
- When the research agent cannot start, the walk says why in plain words and what to do. For example: "The research agent could not start: the Claude command is not signed in. Run claude in Terminal and sign in, or pick another model in Settings > Models." An error with no known cause gets a general line. The raw error stays in the log and in "Show what it did".

### A course to your goal

- A goal that you type on Start now makes a **course**: all that abhyasa has for that goal. The walk that Start makes is stage 1. A second walk with the same goal joins the same course. An older goal walk gets its course when you open Today.
- The course page (`/course/<id>`, and Course on each walk of a course) shows your goal, "You are here" (the stage and the idea), the next idea with its reason in one line and one Continue button, the stages with their progress, what stands between you and the goal, and the sources of the course.
- abhyasa picks the next idea with eight rules, in order: a failed notebook from Leela, a review that the stage needs and that you start to forget, an idea that you asked about two times, the next idea when you know what it needs, the idea that it needs first, a weak idea that a later stage needs, the next stage, and "You reached your goal." When you open another idea by hand, it wins one time, and the reason says "You chose it."
- "What stands between you and the goal" lists the ideas still to learn, a weak idea that a later stage needs, the notebooks to run in Leela, setup steps (Leela is not running, a notebook has no data folder), and sources that failed, still file, or give no passage.
- "Ask me where I start" asks a few short questions about what you know, such as "Do you know how a neural network learns?". Answer each one with Yes, A little or No, by a tap or by voice. abhyasa does not ask about an idea that you learned. With the last answer, abhyasa plans the stages: a stage of basics that you know is skipped, one that you know a little is short, and one that you do not know comes first. The model gets the questions through the guard of ramabana.
- abhyasa builds the walk of a stage when you open it, or when you finish 60% of the stage before it. A stage never asks an idea of an earlier stage again. A planned stage whose ideas you learned in the meantime shows as known.
- Today's top line is the course that you used last: what comes next, why, and Continue.
- An idea that you learned in a session or in another walk now shows as "known (learned elsewhere)" in a walk. It counts as done and asks nothing. Its review comes when it is due. A new goal walk marks an idea that you learned as known.

### Fixes from a real-vault audit

- Library, Sources no longer gives error 500. A vault also keeps stores that are not shelves of documents, such as the store of names (`entities`). abhyasa now opens only the shelves that hold documents (`Learning.doc_shelves`, `Learning.doc_shelf`). The tutor's vault search, a document on another shelf, and the arXiv repair use the same rule.
- A link or a form never adds a new shelf to your vault. Before, the vault viewer (`/v/<shelf>/<id>`) and a walk from a document made an empty shelf for any name in the link.
- When the model gives no question, or a call to the model fails, a session and a walk show a plain line and Try again. Before, the session page gave error 500. A failed grade or hint gives the line "The tutor could not grade your answer. Try again." and your answer stays in its box.
- "Add to a walk" on a concept page now gives the new step a check. Before, the walk pages gave error 500 after it. An old walk step with no check gets a short-answer check when it loads.
- `ask_json` takes `need`: a reply must be one JSON object with text in those keys, or it gets one more try.
- The log now has the error when a source, a tutor note or a code task fails. The page still shows nothing for them.
- An empty voice clip gives error 400, not 500.
- A search query is cut at 500 characters, and a long word in a hit wraps.
- A long run of text with no space in a vault document, such as a transliterated Sanskrit line with dots between the words, now wraps. Before, the page had a side scroll.
- A diagram card of the guide never goes under the strip of the board. Before, on a walk step it could stand low on the page, behind the strip.
- abhyasa reads the names of the shelves without a count of the documents in each store. SQLite no longer logs an error for the store of names on each page, and a walk step opens faster on a big vault.
- The course card says the idea of "You are here" one time. On Your learning, "Review the misses" lines up with the title of each row.
### You always know what research does

- The plan and each step show one line of research: what it reads now ("Reads train_dreambooth_lora.py for idea 3"), "Sources for 4 of 11 ideas", the time left from the rate so far, and "Last step 12 s ago". It has Stop, "Show what it did" and "See the build".
- The plan says that you can start now: an idea with no source shows the tutor's note, and it fills in when its source comes. The plan marks an idea that waits for a source, and the outline marks an idea that has one.
- When a source comes while you read a step, the step shows "A source is ready — show it". The page does not change until you click.
- "Sources" in the outline and "See the build" open the plan and the line of research also after the walk started (`/w/<walk>?plan=1`). Continue still goes to your step.
- After research ends, the line says how and when: "Research ended at 13:42", "You stopped research", "The time for research ended", or "Research stopped because abhyasa closed". It counts the quotes that abhyasa refused, and it has "Find sources again" for the ideas with no source.
- When research ends, each page shows "Sources for your walk '<title>' are ready" with a link, until you open the walk.
- Mac app: when you close the window while research runs, Abhyasa stays in the menu bar and research goes on. It says so one time. When research ends, a macOS notification tells you, and a click opens the walk. Abhyasa asks for permission to notify the first time research runs, not at launch.

### Research uses ramabana, and finds more sources

- The research of a walk is a ramabana agent with ramabana's own read and web tools and its sub-agents (`delegate_search`): the lead reads the attached folders, and sub-agents look for the other ideas at the same time. abhyasa keeps its own checks on each read and each passage.
- An attached GitHub repo is read from the clone that abhyasa made when it filed the chip. Research no longer asks GitHub for the repo again.
- A real passage on the idea is no longer refused: plural forms, "-ing", the case, markdown marks, the row numbers of a file view, and a key term such as LoRA now count. The words of your own goal ("Indian comics") do not have to be in the passage. A refusal tells the agent why and what passes.
- A site that refuses research (403, 401, 429 or a check for robots) is asked one time only for 15 minutes. A page and a search are kept for 15 minutes, so a retry and another idea do not fetch them again. One fetch waits at most 15 seconds, and research asks one site for one page at a time.
- Measured on a walk of 4 ideas with one attached folder (real web, real model): the first source came at 18 to 21 s (before: 32 s with the old agent, 36 s with the search of each idea). The whole run took 79 to 124 s (before: 46 s with the old agent, 117 s with the search of each idea). On a small walk the time of each model step is most of the time. A walk with many ideas gets more from the sub-agents. We did not measure that yet.
- Fixed: one search result with a very long link stopped the whole search with "File name too long" (fossick tests a link as a path, and Python 3.12 raises for a path of more than 1,024 characters).
- Change the walk shows the research line under the summary line: how research ended, how many ideas have a source, the quotes that abhyasa left out, "Find sources again", and Stop while research runs. Each idea with no source says "no source yet" in its row. The outline of each idea has "Sources" when an idea has no source, also when research did not run. Then the line says "Research did not look for sources yet." and gives "Find sources".
- Continue in the top bar and the Continue card on Today go to the place that you used last: an open session or a walk that is not finished. A walk counts from the time that you opened, read or closed an idea in it. Before, an older open session came first, so on a walk the top bar could say "Continue" with another, older topic.

## 0.0.15

### The screen guide shows what it does

- The guide line says what the guide does now: it reads the page, it asks a model, it searches the web, or it saves to your vault. It names the model and shows "on this Mac" or "hosted · <provider>". A web search shows its query word for word.
- When the guide saves a web page to your vault, the end line says "Saved to your vault: <title>." with Undo.
- The guide sends a figure picture to the vision model only when your question is about that figure, and it says so before it sends it.
- The mic shows its level and where speech to text runs. The board has Stop and Voice off. The new setting `guide.voice` keeps your choice.
- A board on an open check counts as one hint, and the check says so.
- Settings, Models has the rows "Screen guide" and "Figure labels". Each row shows "on this Mac" or "hosted · <provider>". The default is the model for hints. A model that comes through two providers shows one time.
- A point mark is now weaker than a circle, so the part that you asked about stands out. The new setting `guide.point` picks the look: Tick (a short arrow, the default), Dot (a small dot that pulses one time) or Ring (a thin, small ring). Step 1 marks the asked part with a circle or a box and uses at most one point.

### Faster boards

- Step 1 of a sure tutor board draws while the model writes the rest. In tests, step 1 showed at about 5.5 s, before the whole board (about 8.7 s).
- The app starts the guide model at launch and again when Caps+E goes down. Nothing is sent to the model.

### Show while you talk

- Circle a part with the pointer, or hold the pointer still on it, while you ask. The guide explains that part first. A faint trail and a ring show what the guide saw. Nothing is kept after you send the question.

### A natural voice

- The guide can read its steps in a natural voice. Settings, Speaking voice has four engines: the browser, Kokoro (on this Mac), OpenAI (hosted) and a Hugging Face model (on this Mac). Each engine shows where it runs.
- Kokoro 82M (`mlx-community/Kokoro-82M-bf16`, voice `af_heart`) runs with mlx-audio and gives the time of each word, so the words light up as it says them. On an M-series Mac, a line takes about 0.1 to 0.2 s when the model is loaded, and 3.5 s for the first line after a start. Install it with `pip install abhyasa[voice]`.
- OpenAI uses `gpt-4o-mini-tts` (voice `marin`) with your key. Each line passes the privacy guard before it goes. A line took about 2.9 s to its audio in a test.
- Look up a text to speech model on Hugging Face, download it, and use it. Pick the voice and the speed, and click "Play a sample".
- The board asks for each line as soon as its step comes, and the server keeps the lines of the run, so a step that you see again speaks at once. When the natural voice fails, the browser voice speaks, and the strip says so one time.
- The browser voice stays the default. The first board with the browser voice says one time that a natural voice is ready, with a link to Settings.
- The Mac overlay uses the same voice from the server, and the voice of the Mac when the setting is the browser voice.

### The Mac app: the guide over other apps

- Caps+E over any app reads the front window with Accessibility and draws the board over it. The guide is off until you start it from a first-use sheet that says what it reads and where it sends it.
- A mark in the menu bar shows the state of the guide, with Stop, Voice off and Turn off.
- The Mac app uses abhyasa 0.0.14 and has `make ship V=<version>` for a release.

### Settings in tabs

- Settings has seven tabs: Models, Voice, Screen guide, Learning, Walks and talks, Sources and Look. One tab shows at a time. `?tab=voice` keeps the tab, and an old link such as `/settings#g-voice` opens its tab at that row. ⌥1 to ⌥7 pick a tab, and the arrow keys move along the tab row. Each row has one help line, with the other sentences under "About this". The Default model list starts where the other model lists start.
- The model list uses the names that the makers use: "GPT-4o mini", "o4-mini", "o3" and "Kimi K3". An alias such as "Claude Opus" does not show next to its version.

### Easier screens

- Each main screen has one main button. Rare actions are under a closed part, and their keys and routes stay the same.
- Today counts ideas, and says why in plain words: "Next: explain Ranking. You know the ideas that it needs." The walk rows on Today have no button. Present on a walk row shows when you point at the row.
- The walk step shows "Open the talk". "Make the talk again" and "Make a second talk" are under More. On the plan of a new walk, Present is quiet, so "Start the walk" is the one button.
- The walk editor is "the plan of the walk". Its long help is under "About this", and its list keys are under "Keys". The talk editor does the same.
- A concept page has "Learn this" as its one button. "Rename or move" and "Add an explainer video" are closed parts. The passages of the idea are under "Passages".
- A vault document has "Learn as a walk" as its main button, and "Only find its ideas" as a quiet one. Its label is "Your vault", and its date is a plain date.
- Sources puts the imports under one "Add more sources" part. The graph puts Freeze, Fit and Lay out again under "Adjust the view". Space, F and R still do them.
- Profile puts "Learn about me now" under a closed part. The help lines on the You pages and in the Library are shorter.

### Built on ramabana and rishi

- The gather agent is a plain ramabana `Agent` with `only_tools`. ramabana estimates its cost.
- Each text to a model and each web query goes through `ramabana.guard`, for the model of each route.
- ramabana sessions and memory come from `ramabana.history.History`.
- A model call that runs past its deadline gives a clear error.
- The model list names an Ollama on another computer as hosted, not "on this Mac".
- A file under a macOS `Keychains` folder counts as a secret.
- abhyasa needs ramabana 0.2.96 and rishi 0.1.64. rishi 0.1.63 runs Claude one-shots on a Mac with an enterprise MCP config. rishi 0.1.64 sends the picture of a one-shot, so figure labels work on remote and Claude models.

## 0.0.14

### The walk path editor and the talk editor

- A walk has an editor for its path. Open it with "Change the walk" on the plan page or on the rail of a step. The path page of a walk opens it too. Each change saves at once. There is no Save button.
- In the walk path editor, you can move an idea (drag its grip, or ⇧W and ⇧S), skip it and bring it back, add an idea (by name, from the concept tree, or from a source), split it into smaller ideas (P), merge it with the next idea (M) and remove it (X). You can change the tutor note, the kind of check and the check question. "Pick another passage" shows only passages that are word for word in the walk documents.
- "Rewrite" (R) asks the tutor to write the note and the check question again, with the chips Simpler, Add an example and Shorter. A text that you changed while the tutor wrote stays as you wrote it.
- The walk path editor shows how many checks are hands-on, and says when the walk has more than the setting allows. A notebook step that builds your goal does not count.
- A side walk stays with its idea when you move, merge or remove that idea, and Undo puts it back.
- Undo in the walk path editor gives back only what the editor changes: the order, the status, the note, the check and the passage. A side walk, a notebook, the Leela time and the research of a step that came after the change stay.
- The talk editor changes a slide in its row: the title, the points that the room sees, the speaker note, the passage, the figure, the beats and the question for the room. It saves at once. There is no Save button.
- The talk editor shows the figure as a small picture, with "Pick another figure" and "Remove the figure". The beats are chips that you drag or move with the keys. "Add a beat" adds a part that the slide has. Select words in the passage to light them.
- In the talk editor, D duplicates a slide, X removes it, R rewrites it, A adds a slide and Q adds a pause. Sections show as labels between the slides.
- Each editor has an Undo bar. It says what changed in one sentence. Undo (⌘Z) puts back that change exactly. In a text box, ⌘Z undoes your typing. "Earlier versions" lists the changes, and you can go back to one. That is a change too, so you can undo it.
- "Fill the slides" keeps a row in Earlier versions, so you can undo it.

### "Make it again" keeps your edits

- "Make the talk again (keeps your edits)" makes a talk again from its walk. A part of a slide that you changed stays. A slide for a new idea, or for an idea whose step changed, is made again.
- A slide whose idea left the walk goes under "Not in the walk any more". It is not in Present, in the minutes or in the room. Use "Put back" or "Remove". When the idea comes back to the walk, all its slides come back.
- The talk editor says what changed in the walk since the talk was made: ideas added, removed, moved and changed.
- "Make a second talk" is under More on the walk page. Undo after "Make it again" gives back the exact talk.

### Concepts: sort by hand

- On the Concepts page, you can rename a group, make a new group, and drag a concept by its handle onto a group. "Move to…" does the same with the keyboard.
- On a concept page, the Name field renames the concept. The old name stays as an alias, so the find box still finds it.
- Each change by hand shows an Undo bar, and ⌘Z undoes it.
- "Sort everything again" is under More. It shows the whole new tree before you accept. Each group that you made stays, unless you clear its box.

### Sources

- The Ramayana episodes of vedicreader are a source. A passage from an episode has its Valmiki cite, for example "Bāla, sarga 1, verses 1-5". When vedicreader runs, "Open in vedicreader" opens the episode. The Sources page says how many episodes it found.
- A walk to a goal is planned from the sources that the goal names, top down. Each step reads its passage from a document that the plan names. "Use sources for this walk" on a path does the same for a path that you have.
- Research looks for each idea by its name, its subject and the walk title. It never sends the text of your goal. A quote must name the idea. A link to a paper goes to the paper reader. A paper that gives no quote is not kept.
- When research finds no passage, the step says why: "The search found nothing.", "No page had a good quote." or "The page could not be read: <reason>." A step that waits too long for a source, also from before a restart, is tried again (setting: Look again after, 10 minutes).
- For a goal that names two or more sources, or a source folder with more than 40 documents, an agent gathers the passages. A band on the walk says what it reads. "Show what it did" opens its log in the side pane. "Stop" stops it. The agent has no shell. abhyasa checks each passage word for word before it keeps it. A note from the agent is marked as its own words.
- New settings for the agent: "Let an agent gather sources for a big goal" (on by default) and "Most minutes for the agent" (15). If the agent cannot start, the walk uses the simple search, and a line says why.
- A YouTube explainer video can go with a concept. "Find a video" looks on YouTube, or you paste a link. "Remove the video" takes it away. The video shows on the concept page and on the walk step, from youtube-nocookie, with no autoplay. A quiet transcript shows the times, and a time moves the video to that place.
- An arXiv paper is read from its HTML page first, so the passages keep their maths and the figures are saved. When there is no HTML page, abhyasa reads the PDF as before.
- Passages on the concept page and on talk slides show maths. A passage is never cut inside a formula.
- Lines of page data, such as "Last modified", are taken out of a web page before the word-for-word check and before abhyasa files the page.
- A GitHub repo is cloned over HTTPS with fossick. The `repos` extra is gone. The GitHub API uses your gh token when gheasy is installed.

### Leela: results and notebook steps

- What you did in Leela comes back to the walk step: your code check, your prediction and your run, with its images. A check that passes in Leela marks the step done. The step then offers "Next idea".
- The walk end page shows "What you made": the last images of your run, with the caption and the source line.
- "Open the lesson in Leela" links to the lesson of the step. A result matches its step by the concept, so a change to the walk path does not move it to another step.
- abhyasa shows only the images that an accepted run lists, and only PNG files from Leela's folder in the vault.
- A notebook step on the Ramayana episodes names the real episode files on this Mac as its data.

### Image demos

- For an idea about images or noise, the tutor can make a demo that draws an image from a formula, with seeded noise. You can change this prompt on the Settings page (Image demos). This needs rupaka 0.0.7.

### The screen guide

- Press Caps+E (⌃⌥⇧⌘E), or the Explain button in the top bar. Hold the keys to talk, or tap them to type. Then say what you do not get, for example "I don't get alpha bar".
- The tutor answers on the page, as a teacher does at a whiteboard. It circles a term in a formula, points to a label in a figure, moves a demo and speaks one short line for each step. The marks stay on their place when the page scrolls or changes size.
- A, S and D say a step again, go back and go to the next step. Esc stops the board. A key that you type in a text box or in an editor stays in that box.
- A pill says where the answer is from: the tutor, your vault or the web. A quote from a source is word for word and has its link. When the tutor is not sure, it looks in your vault, and then on the web.
- When a concept has an explainer video, the board can move the video to the right time and quote what it says there.

### Library and You

- Sources in Library is now a list of your documents. Each row shows the title, the kind, the date it was added, and the walks and talks that use it.
- A folder or a repo that Start filed is one row, with the count of its documents. For one hour it has Undo. After that, it has Remove.
- An arXiv paper is one row, also when you have its HTML copy and its PDF copy.
- The vedicreader line, the import and the index buttons are under "Add more sources".
- Your learning shows "Your strengths": your weak spots and "Practice my weak spots". An empty Concepts page says "Concepts appear here when you start a walk."

### Safety

- The text that the screen guide and the gather agent send out (prompts, web queries, links and log lines) goes through ramabana's guard. The guard always masks secrets. It masks or withholds personal data only when the ramabana setting `cli.pii` is `redact` or `refuse`. The default is `off`. When the guard withholds a text, the screen guide says so in one plain line. A figure image goes to the vision model as it is: the guard cannot read pixels.
- Every page fetch refuses a private address (`allow_private=False`), also when `FOSSICK_ALLOW_PRIVATE` is set.
- The path checks: the agent reads only files in the folders of your sources and in its own clones. It never reads through a link, and never a key file such as `.env` or a keychain file. A clone has the same rules as a folder on this Mac.
- The agent has a time limit and a spend limit for each walk.
- A folder or repo chip that the folder rules refuse (outside your home folder, hidden, or a link, for example `/etc` or `~/.config`) is not kept on the walk. The agent cannot read a file in it.
- ramabana is now a dependency of abhyasa, so the guard is always there. The `models` extra stays, so an old install command still works.
- A data path of a notebook step is good when your home folder is under a hidden folder. A hidden folder in your home folder is still refused.

## 0.0.13

- The app says "walk" for each journey: the pages, the notes, the docstrings and the vault titles. The path page moves to `/path/<id>`. An old `/j/<id>` link goes there.
- The top bar has four tabs (Today, Learn, Library, You) and a gear for Settings. A page with more parts shows them as links under the title. Left-hand keys go to the tabs: ⌥Q Learn, ⌥R Library, ⌥G You, and ⌥1 to ⌥3 for the links under the title.
- The Learn page lists your walks and talks. Each walk row has two lines and a pill that says its kind. A path row has a quiet Present.
- One Start box takes a topic, a link, a paper, a text, a vault document or a dropped file. It says what it will do before you press Start. It makes no network call to read the box.
- Each passage has one source line under it, with a label: your vault, the web, or your source. The tutor's own words have a mark. Old talk slides and concept page passages get a source line too.
- A goal that names a folder, a local repo or a GitHub repo files it as a source. The names show as chips under the box before you press Start. You can remove a chip. Undo forgets what Start filed.
- Folders and repos: abhyasa files notebooks, Markdown, text and Python files. It refuses hard links and hidden folders, caps each filing at 200 MB, and clones a public GitHub repo over HTTPS (extra: `abhyasa[repos]`). The setting "Source folders" (`sources.roots`) sets where it looks.
- A new check kind, `notebook`, for an idea that needs a library. The tutor writes the task, the tests, the data paths, the packages and the run onto the step. The card shows them, and the step runs in Leela. "Download the notebook" gives the same notebook for Jupyter.
- The notebook spec is checked: each text is one line, the patterns match in full, a data path must be in your home folder with no `..` and no hidden part, and a line that starts with `#|` is refused. The tutor gets each passage between markers.
- `abhyasa.contract` holds the names that abhyasa and Leela share: the exercise test rule, the notebook spec, the run check and the link. It uses only the standard library.
- The link to Leela has the vault key `v`, so Leela can tell when the two apps use different vaults. A link with no `v` works as before.
- "Open in Leela" on a notebook step notes the time on the step. The step then says "Opened in Leela at 14:02. The result comes back here."
- abhyasa writes its address to `~/.config/abhyasa/serving.json` (`url`, `pid`, `vault`) when it starts, and removes it when it stops. Leela uses it to link back to the walk.
- `abhyasa.stagekit` holds `room_spec` and `is_local` with only standard imports.

## 0.0.12

- Concepts: a saved sort is locked. The tutor never moves a concept that has a group, and it keeps the group list of each subject. The button says "Sort 3 new concepts" and shows only when some concepts have no group; it sends only those, and the groups you have come first. New concepts from a walk, an add or an import are placed in the groups by themselves, with a quiet mark and an Undo.
- Concepts: a name of one character, such as "x", does not make a concept from a text, a term or a ramabana note.
- Sort my concepts: the tutor asks again one time for each concept that got no group, and a short "Other" group is the last resort. For a concept with no subject, it also proposes a subject (one you have, or a new one). The proposal says how many it placed and names the ones it left for you.
- Walks from a link or a paper: new concepts get a subject (the Subject field, or one that the tutor picks), and a name that was a slug shows as words. Old concepts with a slug name get words once.
- Research: a walk step with no source passage (a walk from a topic, the walk of a talk from a journey) gets a source from the web. The tutor searches the web for the idea, reads the best 3 pages with plain HTTP, and quotes one passage of at most 600 characters. It keeps the passage only when the page has it word for word. The page goes into your vault as a web document and is linked to the concept, so lessons, slides and your sources find it (prompt: Source finder).
- Research: the walk opens at once. Each step says "Looking for a source…" while the tutor looks, then shows the quote with "From the web: <site> · <title>". The title opens the copy in your vault in the side pane, and "Open the page" opens the page in a new tab. The note of the step is written again from the passage.
- Research: when no page has a good quote, the step keeps the tutor's words and says "No source found." "Find a source" tries again on any step with no passage.
- Research: a talk from a journey looks for sources before it makes the slides, so a slide shows the quote, and the editor names the page.
- Research: the tutor reads only public hosts: never this computer or a local network, never a video or a social site, and never through a browser. It reads only HTML and plain text pages, never a file such as a PDF or a zip, and never a host in percent codes. It caps the bytes, the speed and the time of each page, reads pages only in the background on its own pool, so a demo or a note never waits for it, and writes each URL that it reads to the log. It never files over a page that is in your vault: a changed page becomes a new document, so older steps keep their links.
- Settings: a new Research group. "Find sources on the web" (on by default) turns research off: then the tutor does no web search. "Steps to research in a walk" (12) and "Search results to read" (5) set the limits. The Add page and the Journeys page say that the search sees your topic.
- An open check stays open after the app restarts.
- A walk from a paper shows the title of the paper, not its arXiv id, on Today, in Journeys, in the crumbs, in the outline and in the talk. The id is a quiet tag on the rows of Today and Journeys. An old walk or PDF with an id for a title gets the real title one time: from its vault document when that has one, and from arXiv in the background after the app starts. If arXiv cannot be reached, the app asks again at the next start.
- The Continue card on Today says what a walk did, for example "2 of 9 ideas", not "0 questions done". A session keeps its text.
- Present shows on a started walk, on its last page and in Journeys.
- Talks: when the talk is made, the tutor writes 2 to 4 points for each slide that has no passage (for example each slide of "Present this journey"), and speaker notes for each slide that has none: what to say, a question for the room and a confusion to watch for. It uses your sources when they name the idea. You can change the prompt (Talk slide) on the Settings page.
- Talks: the room sees the points of a slide, with the `body` beat, and its type gets smaller when they do not fit. The room never sees the speaker notes. The presenter window shows the notes and the line "From your sources". The editor has a Points box for each slide with no passage.
- Talks: an old talk with slides that have only a title offers a quiet "Fill the slides" button in the editor. The tutor writes the points and the notes of those slides in the background. A slide that you change at that time keeps your change.
- Talks: maths in a slide shows as maths, in the presenter window and in the audience window: the title, the section, the points, the notes, the question and its options, the Next row, the talk title and the question on the room screen. When there is no choice question, the question for the room is the one that the tutor writes with the slide. Else it reads well for any name of an idea and keeps its case: "Say in one or two sentences: Why scale by …?", or "what is "CAN bus"?" for a plain name. "Fill the slides" also gives the new words to an old question of the talk, but never changes a question that you wrote.
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
