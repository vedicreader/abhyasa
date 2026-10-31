# Release notes

<!-- do not remove -->

## 0.0.16

- abhyasa no longer indexes ramabana sessions and memory or Leela agent notebooks into your vault. What is already in your vault stays. The `abhyasa-index` command, its ramabana tick and the Index buttons on Sources are gone. A folder that you attach to a walk still files its notebooks.
- You can ask the guide a follow-up question, such as "say that more simply" or "why?". The guide sends your last 3 questions on this page and the lines of their boards with the new question. Under the box, "Follows up on: <your last question>" shows, with × to start fresh. The guide forgets the questions when you go to another page, after 10 minutes with no question, or when you push ×. It keeps them in memory only. The Mac guide does the same for each window.
- When you speak with Caps+E, the guide shows what it heard in the box and sends nothing yet. Change the words if you need to, then push Return to send them. Esc closes the box. The Mac guide does the same in its strip.
- Each page has a small Keys button at the bottom left. It opens a panel with the main keys of the page, and each key is a button that does the action. The panel says how to talk to the guide (hold Caps+E) and how to dictate (⌥D). In Abhyasa.app it also has "Use the guide over other apps…", which shows the first-use sheet of the screen guide. ⌥⇧F opens the panel. "Hide this" or Settings, Look turns it off (the setting `look.keys_float`).
- A short check on a walk has the Speak button (⌥D), and the guide box shows "Hold Caps+E to talk".
- The Sanketa pack gives each key a label of six words or fewer, in the key style of Sanketa. Sanketa's lint finds no errors and no warnings.
- The Start box has "Pick folders…" beside the field. On a Mac, it opens the folder chooser, and abhyasa adds the folder that you pick with the same checks as a typed path. While you drag files over the box, it shows a dashed outline and "Drop files to add them as sources." A dropped folder says "To add a folder, use Pick folders." abhyasa refuses a source folder that you cannot read.
- Many folders in. Two paths that you paste with a space, a new line or a comma between them now give two chips. Before, they gave one bad chip, and the line said "2 sources". A path with spaces in its name stays one chip when you put it in quotes or when the folder is on this Mac as written.
- "Pick folders…" opens the folder chooser with more than one selection. Hold ⌘ to pick more than one folder. Each folder is its own chip. When you drop several files or folders on the Start box, each one is a chip. abhyasa files each dropped PDF, `.md` or `.txt` file in your vault.
- A goal walk has "Add a source" under its plan. Type a path, a repo or a link, or use Pick folders. abhyasa files each source on its own job, and the source joins the walk when it is filed. A line shows each source that is still filing.
- Each source of a goal files on its own job, at the same time as the others. The plan waits at most 20 seconds for the sources. A source that takes longer, such as the clone of a big repo, joins the walk when it is filed. Until then, the walk says "abhyasa is still filing <name>."
- A big code repo, such as huggingface/diffusers, files what a learner needs. abhyasa files at most 400 files in this order: the top README, the notebooks, the READMEs of `examples/`, its training scripts (`train*.py`), its other scripts, the English docs, the other text and the other code. Docs in other languages come last. One top folder gives at most 160 files until each other top folder has its files. Before, a repo with a notebook lost all of its `.py` files, and `docs/` used all 400 places. A course (one file in ten is a notebook) still files no other `.py`. The research agent reads the other files when it needs them.

### Fixes from a real-vault audit

- Library, Sources no longer gives error 500. A vault also keeps stores that are not shelves of documents, such as the store of names (`entities`). abhyasa now opens only the shelves that hold documents (`Learning.doc_shelves`, `Learning.doc_shelf`). The tutor's vault search, a document on another shelf, and the arXiv repair use the same rule.
- A link or a form never adds a new shelf to your vault. Before, the vault viewer (`/v/<shelf>/<id>`) and a walk from a document made an empty shelf for any name in the link.
- When the model gives no question, or a call to the model fails, a session and a walk show a plain line and Try again. Before, the session page gave error 500. A failed grade or hint gives the line "The tutor could not grade your answer. Try again." and your answer stays in its box.
- "Add to a walk" on a concept page now gives the new step a check. Before, the walk pages gave error 500 after it. An old walk step with no check gets a short-answer check when it loads.
- `ask_json` takes `need`: a reply must be one JSON object with text in those keys, or it gets one more try.
- The log now has the error when a source, a tutor note or a code task fails. The page still shows nothing for them.
- An empty voice clip gives error 400, not 500.
- A search query is cut at 500 characters, and a long word in a hit wraps.

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
