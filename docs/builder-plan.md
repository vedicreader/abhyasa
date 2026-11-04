# Plan: the builder

Status: approved to build, 4 Nov 2026. Version 1.

## Why

Today you make a walk or a talk with a form: the Start box, its chips, "Who is it for", "No code", Start and Make a talk. Then you change it with buttons: Make it better, Make it again, lock and unlock. The owner says this feels like a black box. You press a button, you wait, and you get a result that you cannot steer. You cannot say what you want in your own words.

The builder is a conversation. You tell abhyasa what you want, you see the walk or the talk change on the same page, and you fix it by saying what is wrong. It works as a ramabana or Leela session does.

## What you can say

These are the owner's examples. The builder must handle each one.

- "Make me a walk on attention in transformers." You can add folders, files and links, or "use these links".
- "I have some material. Research more material and add it." Then: "I do not like the extra material. Use only the material that I attached."
- "The agentic_engineering notebook is the main source. Use the others to add to it. Where they conflict, use the notebook."
- "I want the people to become technical." Or: "I want them to leave with a thorough understanding of the material."
- "Make a talk from this for managers, 20 minutes." Then: "slide 3 has too much code", "leave slides 4 and 5 as they are", "make it again with less code".

## The parts

### 1. The brief

The builder keeps a brief on the walk or the talk. The brief is what you told it, in a form that the builders can use:

- The sources, each with a role: `main`, `extra` (adds to the main sources) or `dropped`. A source is a chip id as the Start box makes it (`file:`, `folder:`, `repo:`, `gh:`, `link:`, `doc:`, `vault:`).
- `rules`: your own words about the sources, for example "where they conflict, use the notebook". They go to the planner and the slide writer as an instruction from the owner (`owner_says`), never as a `<source>`.
- `research`: on or off. Off means "use only my material".
- `aim`: the tone or the goal, in your words, for example "become technical".
- `audience` and `no_code`, as today.
- `keep`: the slides or steps that you told it to leave as they are. This replaces lock and unlock.

The pane shows the brief in a short box above the conversation. You can change a field there too, but you do not have to.

### 2. The conversation pane

- A new page, "Build", opens from Home ("Make a walk or a talk by talking"). Also, "Change with the builder" opens the same pane beside a walk page or a talk editor, in the side pane that abhyasa already has.
- The page has the conversation on the left and the walk or the talk on the right. The right side updates after each change. You do not refresh.
- The conversation has text input. Use voice as the Start box does (data-mic), so that you can speak.
- The pane shows each tool call as one short line while it runs, for example "Filing agentic_engineering.ipynb" or "Writing slide 3". Long jobs show their stage, as the talk job does now. Stop works.
- The conversation of a walk or a talk is kept. When you open the pane again, it continues.

### 3. The agent

- It is one ramabana agent for each conversation. It stands on `ramabana_lead` (`abhyasa/models.py`): ramabana's own read and web tools, no Python, no write to your files, and caps for each turn. Add the builder tools below.
- It runs as a pool job. Use the job rows, Stop and the pending card that exist now.
- Its system prompt says what abhyasa is and what the brief means. It tells the agent to keep the brief true after each request, and to say in one line what it changed. The prompt is ASD-STE100 and registered with `register` as the other prompts are, so the owner can edit it in Settings.

### 4. The builder tools

Each tool is a thin wrapper over an engine function that exists. Do not write a second planner, a second slide writer or a second research step.

| Tool | What it does | Stands on |
|---|---|---|
| `add_source(ref, role)` | File a folder, a file, a repo or a link, and give it a role | `file_chip`, `detect` |
| `set_source(ref, role)` | Change a role, or drop a source | the brief |
| `set_brief(aim, audience, no_code, rules, research)` | Change the brief | the brief |
| `research(query)` | Find extra material. It gives a list that the pane shows. You keep or drop each item | the research step of a walk |
| `make_walk()` | Make the walk from the brief | `walk_from_topic`, `journey_from_sources`, `notebook_walk` |
| `make_talk(minutes)` | Make the talk from the brief | `talk_from_sources` |
| `change_walk(instruction, steps)` | Change the walk, or only some steps | `improve_walk`, `edit_walk`, `rewrite` |
| `change_talk(instruction, slides, fresh)` | Change the talk, or only some slides, and keep the `keep` slides | `talk_again`, `talk_fresh`, the slide rewrite |
| `set_poll(q, options)` | Change the poll | the talk editor's `edit` |
| `keep(ids)` / `free(ids)` | Leave steps or slides as they are, or let them change | the brief |
| `show()` | Give the agent a short outline of the walk or the talk now | `walk_slides`, `talk_state` |
| `undo()` | Take back the last change | the history and Undo that exist now |

Each change goes into the history of the walk or the talk, with Undo, as the edits of today do.

### 5. The brief in the builders

- `main` sources are read first. `extra` sources and research add passages, and lose when they conflict with a `main` source. Use the passage search and the grounding that exist, and give the `rules` to the prompt.
- `research` off: no web search, and the walk uses only your sources.
- `aim` goes to the planner (how deep, how technical) and to the slide writer.

## Not in version 1

- A builder for courses.
- Two or more people in one conversation.
- Removing the Start box. It stays as a quick way in. "Make a talk" and "Make it again" stay too.

## Tests and checks

- Unit tests for each tool, with the fake model, and a check of what the page shows.
- A real browser check of each owner example above, against a copy of the vault, with screenshots.
- Never the owner's real vault, and never the server on port 5088.
