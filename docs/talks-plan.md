# Plan: talks from sources

Status: proposed, 4 Nov 2026. Nothing in this plan is built yet. The owner asked for it. It changes when the owner decides the open questions at the end.

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
| Opening | A title slide. | A title slide with what the room will build, and one poll (no right answer), for example "Have you used an agent that runs tools?" |
| Idea slides | Passage or points, a figure, and a choice question. | Points from the section, a short code piece when "No code" is off, and one question: a prediction, a choice, or "What does this print?" (the `run` question kind, which exists). |
| End | Questions, then What we covered. | Questions, then a new `next` slide: "Now open the notebook", with its link and a QR code. |
| Speaker notes | What to say, a question, a confusion to watch for (`fill_slide`). | The same, and which cell of the notebook each slide comes from. |

The slide writer (`SLIDE_SP`, `talk.slide`) today assumes "people of mixed levels". The talk keeps `audience` and `no_code`, and `fill_slide` puts them in the prompt in a `<source>` marker, as the planner does.

## The handout: PDF, and PowerPoint as an option

`recap_html` (`nbs/05_show.ipynb`) already writes one HTML file after a run: each slide that the room saw, its points, its figure inline, the questions with the room's answers, and the sources. The handout reuses it.

1. A "Handout" item in the talk menu writes the deck as one HTML file with print styles: one slide on each page, the points, the figure, each question with its right answer, the sources, and the notebook link. It works before a run, and after a run it adds the room's answers.
2. You save it as a PDF with Print in your browser. This needs no new library and no browser that abhyasa starts.
3. A PowerPoint file (`.pptx`) needs the library `python-pptx`, which abhyasa does not have. It is a separate step, only if you want to edit the deck in Keynote or PowerPoint.

## Steps

Each step has its own test and can ship alone. Engine steps change the notebooks under `nbs/`; web steps change `abhyasa/blocks/`.

| # | Step | Where | Test |
|---|---|---|---|
| 1 | The talk keeps `audience` and `no_code` from its walk. `fill_slide` puts them in the slide prompt. `talk_again` and `talk_fresh` keep them. | `nbs/05_show.ipynb` | A fake model sees the audience in the slide prompt; with `no_code`, no slide shows code. |
| 2 | `talk_from_sources(lr, ask, chips, goal='', audience='', no_code=False)`: file the chips, make the hidden walk (a goal walk, or one step for each notebook section when the only source is one notebook), then `talk_from_walk`. | `nbs/04_path.ipynb`, `nbs/05_show.ipynb` | A notebook with three sections gives three idea slides in section order, and the walk is hidden from `journeys` lists. |
| 3 | The opening poll and the `next` slide with the notebook link. `check_talk` accepts the new slide kind. The stage and the audience window draw it. | `nbs/05_show.ipynb`, `abhyasa/core/stage.js` | `check_talk` passes a deck with a `next` slide and refuses one with no link. |
| 4 | Questions for a workshop: a prediction or "What does this print?" for a section with a small code cell, a choice question otherwise. | `nbs/05_show.ipynb` | A section whose code prints a value gets a `run` question with no answer before the run. |
| 5 | "Make a talk" in the Start box. The job files the sources, makes the talk, and opens the talk editor. | `abhyasa/blocks/add/`, `abhyasa/blocks/walk/app.py`, `abhyasa/blocks/talk/app.py` | Posting the form with a notebook chip opens `/t/<id>`; the hidden walk is not on Home. |
| 6 | The talk editor says "Made from your sources" for a talk with a hidden walk, and links to the sources, not to a walk page. Deleting the talk deletes its hidden walk. | `abhyasa/blocks/talk/`, `drop_talk` | Deleting the talk leaves no journey with `parent.for == 'talk'` for it. |
| 7 | The handout HTML, with print styles. | `nbs/05_show.ipynb`, `abhyasa/blocks/talk/` | The file has one section for each slide on stage, the right answers, and the notebook link. |
| 8 | "Make a walk from this talk": copy the hidden walk's steps in slide order into a walk of your own. | `nbs/04_path.ipynb`, talk menu | The new walk has the slides' ideas in deck order, and no `parent`. |
| 9 | Optional: a `.pptx` file from the handout data. | new dependency `python-pptx` | Only if the owner adds the dependency. |

Steps 1 to 3, 5 and 7 give Use 2 for the workshop. Step 4 makes its questions better. Use 1 works after step 5. Step 8 is for Use 1.

## Open questions for the owner

1. The notebook link on the `next` slide: the local path, the GitHub link of the repo when it has one, or a link that opens the notebook in Colab.
2. The handout: with the right answers, or with blank questions so that people can try them later.
3. PowerPoint: add `python-pptx` now, or start with the PDF only.
4. The opening poll: one question that abhyasa writes, or one that you type in the Start box.
