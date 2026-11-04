# Plan: talks from sources

Status: built, 4 Nov 2026. Steps 1 to 8 and 7a are built. The owner decided the open questions on 4 Nov 2026; the decisions are at the end. A review on 4 Nov 2026 found problems in the first build; "Fixes after the review" says what changed. Not built: "only sections 1 to 4" in What to change does not remove slides, because the slide writer writes one slide at a time.

Today a talk comes only from a walk. "Present this walk" calls `talk_from_walk` (`nbs/05_show.ipynb`). It makes one `idea` slide for each step that is not skipped, then the `questions` and `recap` slides. The talk keeps the walk id in `t['src']['walk']`. "Make it again", "From scratch" and `walk_changes` read that walk again.

This plan adds two ways to make a talk with no walk of your own first, and a handout that you can send after the talk.

## The two uses

**Use 1: a deck on topics that you want to learn.** You type a goal or a list of topics, and you can add sources. abhyasa plans the ideas, finds passages in your sources and on the web, and makes a deck. You read it or present it. Later you can make a walk from it, to learn the ideas with checks.

**Use 2: a workshop starter from your own notebook.** You have the content already, for example `karma/agentic_engineering.ipynb`. You need a short interactive talk before you take the room into the notebook. The deck follows the sections of the notebook in order. It explains what each section does, in words that the room knows. It asks the room questions to get them thinking: a poll at the start, a prediction before a result, and "What does this print?" for a small piece of code. The last slide tells the room to open the notebook, with its link. The deck is not a walk for you, and it makes no checks for you.

## Design

A talk keeps a hidden walk under it. The walk has `parent={'for': 'talk'}`. `for_talk` (`nbs/04_path.ipynb`) already hides such a walk from Home, the walk lists, Sources, Leela and research. The talk builder and every rebuild stay as they are, because they all read `src.walk`. A new builder that plans slides with no walk would have to copy the planner, the passage search, the checks, `minutes` and the rebuild logic.

| Part | Use 1: topics | Use 2: my notebook |
|---|---|---|
| Start | The Start box, with a goal, and with sources or none. A new button "Make a talk" sits beside Start. | The Start box, with one notebook as a `file:` chip and no goal. "Make a talk" sits beside Start. |
| Hidden walk | `walk_from_topic`, as a goal walk is made today, with research. | One step for each section of the notebook, in order, as `notebook_walk` makes it today. No concept extraction, so no idea is renamed or moved. |
| Who it is for | "Who is it for" and "No code" go to the planner, as they do for a walk. | The same fields go to the slide writer. With "No code", a slide shows no code; it says what the code does. |
| Opening | A title slide. | A title slide with what the room will build, and a `poll` slide. abhyasa writes the poll question and its options. A poll has no right answer, for example "Have you used an agent that runs tools?" You change the question and the options in the talk editor before the talk. |
| Idea slides | Passage or points, a figure, and a choice question. | Points from the section, a short code piece when "No code" is off, and one question: a prediction, a choice, or "What does this print?" (the `run` question kind, which exists). |
| End | Questions, then What we covered. | Questions, then a new `next` slide: "Now open the notebook", with a link to the notebook on your Mac. You click the link and the notebook opens. |
| Speaker notes | What to say, a question, a confusion to watch for (`fill_slide`). | The same, and which cell of the notebook each slide comes from. |

The slide writer (`SLIDE_SP`, `talk.slide`) today assumes "people of mixed levels". The talk keeps `audience` and `no_code`, and `fill_slide` puts them in the prompt in a `<source>` marker, as the planner does.

## The poll

A `poll` is a new slide kind. Its question is a `choice` ask with options and no right answer. The stage shows the count for each option, and no option is marked right. `check_talk` accepts a `choice` with no answer only on a `poll` slide.

abhyasa writes the poll when it makes the talk. The poll asks about the room, not about the content: what the room has used, or what the room expects. The talk editor already changes the question and the options of a slide (`edit` in `abhyasa/blocks/talk/app.py`), but only for the kinds in `ASKS`. `poll` goes into `ASKS`, so you edit the poll as you edit any other question. Each change goes into the talk history and has Undo.

## The handout: PDF

You send the handout after the talk. So the handout can give the right answers. They go at the end of the PDF, under "Answers", so that a reader can try each question before they see its answer.

`recap_html` (`nbs/05_show.ipynb`) already writes one HTML file after a run: each slide that the room saw, its points, its figure inline, the questions with the room's answers, and the sources. The handout reuses it.

1. A "Handout" item in the talk menu writes the deck as one HTML file with print styles. Each slide is on its own page, with its points, its figure and its question. A question shows no answer on its page. The sources and the notebook link come after the slides.
2. The last section is "Answers". It gives the number of each question, the question, and its right answer. A `run` question gives what the code prints. A poll has no right answer; after a run, the handout gives the count for each option of the poll.
3. You save the file as a PDF with Print in your browser. This needs no new library and no browser that abhyasa starts.

## Links in the handout

The handout has links to the notebook and to the sources. You can change each link before you make the PDF, for example to a OneDrive link that the room can open.

Today `_sources_html` (`nbs/05_show.ipynb`) gives a link only for a web page. For a file or a page of your vault, it writes "in your vault". The handout changes this.

1. A "Links" panel in the talk editor lists each link that the handout will have: the notebook first, then each source. For each link it shows the local path and a field for the shared link.
2. A shared link that you type is kept on the talk, in `t['links']`, by local path. It is in the talk history and has Undo. "Make it again" and "From scratch" keep it.
3. A folder row in the panel takes one shared link for every source in that folder. Use this when you copy a folder to OneDrive and share the folder. A file link that you type wins over the link of its folder.
4. The handout uses the shared link when there is one. A source with no shared link keeps its web link, or else its `file://` link on your Mac.
5. The stage keeps the `file://` link on the `next` slide, so that the notebook opens on your Mac during the talk.

A OneDrive share link does not show the path of the file, so abhyasa cannot make the link of a file from the link of its folder. A file in a shared folder gets the folder link. To link one file, you type its own share link.

A link with no shared link is a `file://` link. It opens on your Mac only. A person who gets the PDF sees the path on your Mac, and the path includes your user name. Before the PDF, the panel marks each link that is still local.

## Steps

Each step has its own test and can ship alone. Engine steps change the notebooks under `nbs/`; web steps change `abhyasa/blocks/`.

| # | Step | Where | Test |
|---|---|---|---|
| 1 | The talk keeps `audience` and `no_code` from its walk. `fill_slide` puts them in the slide prompt. `talk_again` and `talk_fresh` keep them. | `nbs/05_show.ipynb` | A fake model sees the audience in the slide prompt; with `no_code`, no slide shows code. |
| 2 | `talk_from_sources(lr, ask, chips, goal='', audience='', no_code=False)`: file the chips, make the hidden walk (a goal walk, or one step for each notebook section when the only source is one notebook), then `talk_from_walk`. | `nbs/04_path.ipynb`, `nbs/05_show.ipynb` | A notebook with three sections gives three idea slides in section order, and the walk is hidden from `journeys` lists. |
| 3 | The `poll` slide that abhyasa writes, and the `next` slide with the `file://` link to the notebook. `check_talk` accepts both kinds, and a `choice` with no answer only on a `poll`. `poll` goes into `ASKS`, so the editor changes its question and options. The stage and the audience window draw both kinds. | `nbs/05_show.ipynb`, `abhyasa/blocks/talk/app.py`, `abhyasa/core/stage.js` | `check_talk` passes a deck with a poll and a `next` slide, refuses a `next` slide with no link, and refuses an idea slide whose `choice` has no answer. Posting a new poll question in the editor saves it, and Undo gives the old one back. |
| 4 | Questions for a workshop: a prediction or "What does this print?" for a section with a small code cell, a choice question otherwise. | `nbs/05_show.ipynb` | A section whose code prints a value gets a `run` question with no answer before the run. |
| 5 | "Make a talk" in the Start box. The job files the sources, makes the talk, and opens the talk editor. | `abhyasa/blocks/add/`, `abhyasa/blocks/walk/app.py`, `abhyasa/blocks/talk/app.py` | Posting the form with a notebook chip opens `/t/<id>`; the hidden walk is not on Home. |
| 6 | The talk editor says "Made from your sources" for a talk with a hidden walk, and links to the sources, not to a walk page. Deleting the talk deletes its hidden walk. | `abhyasa/blocks/talk/`, `drop_talk` | Deleting the talk leaves no journey with `parent.for == 'talk'` for it. |
| 7 | The handout HTML, with print styles, and the "Answers" section at the end. | `nbs/05_show.ipynb`, `abhyasa/blocks/talk/` | The file has one section for each slide on stage, no answer on a slide page, every right answer under "Answers", the poll counts after a run, and the notebook link. |
| 7a | The "Links" panel, `t['links']`, folder links, and the handout using them. | `nbs/05_show.ipynb`, `abhyasa/blocks/talk/` | A shared link that you type for a file replaces its `file://` link in the handout. A folder link applies to every file in the folder. A file link wins over its folder link. Undo gives the old link back. |
| 8 | "Make a walk from this talk": copy the hidden walk's steps in slide order into a walk of your own. | `nbs/04_path.ipynb`, talk menu | The new walk has the slides' ideas in deck order, and no `parent`. |

Steps 1 to 3, 5, 7 and 7a give Use 2 for the workshop. Step 4 makes its questions better. Use 1 works after step 5. Step 8 is for Use 1.

## Fixes after the review

These are built, uncommitted, on 4 Nov 2026.

| Problem | Fix |
|---|---|
| A notebook slide showed the whole section, with headings and tables. | The section goes to the slide writer in `_read`. The slide shows 2 to 4 points, at most one short code piece (`code_piece`, none with No code) and the question. |
| The handout showed raw markdown and the title three times. | The handout draws markdown (`md_part`, with `mdhtml` and `nh3`). A section line or a first heading that is the title does not show. |
| Make it again took no instruction. | "Make it again" in the ⋯ menu has What to change. It goes to the slide prompt and the poll prompt in an `<owner>` marker. The talk keeps it in `change`, and Undo gives back the old one. |
| The ⋯ menu items had different looks. A second press made a second walk. | Each item has the class `mi`. The walk keeps `from_talk`, so a second press opens the same walk. |
| A notebook talk had a path as its title. | `nb_title`: the first `#` heading, else the file name in words. |
| Some words were not true. | "Made from your goal", the Start line for a file, no web chip for one notebook, Teach names Make a talk, and the pending card shows the stage of the job. |
| A disabled Make a talk gave no reason. | It says "To make a talk, write a goal or add a source." Only a busy or held button has the progress cursor. |
| Web and vault sources had no link. Undo of Make this walk again kept the new sources. | A GitHub repo, a link and a vault page get a row and a handout line. `edit_walk` keeps the old fields, so Undo gives them back. |

## Decisions

The owner decided these on 4 Nov 2026.

| Question | Decision |
|---|---|
| The notebook link | A `file://` link to the notebook on the owner's Mac. No QR code. |
| Links in the handout | The owner can change each link, and give one link for a folder, before the PDF, for example to OneDrive. |
| Answers in the handout | Yes. The handout goes out after the talk, so the right answers are at the end of the PDF, under "Answers". |
| PowerPoint | No. The PDF only, so no `python-pptx`. |
| The opening poll | abhyasa writes it. The owner edits it in the talk editor before the talk. |
