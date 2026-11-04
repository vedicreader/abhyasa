# Plan: the builder

Status: version 1, 4 Nov 2026. This plan joins the first plan, the product plan and the design plan, with the decisions of the owner.

## Why

Today you make a walk or a talk with a form, and you change it with buttons. The owner says that this is a black box. The builder is a
conversation: you say what you want, you see the walk or the talk change on the same page, and you fix it with your own words.

## The decisions of the owner

1. Research waits for Keep. Each find has Keep and Drop, and there are Keep all and Drop all. A find that you did not decide stays out.
2. The builder is in the side pane at the right, with its grip and its widths. The walk or the talk is the page at the left. Build and
   "Change with the builder" are one layout and one code path.
3. Start and Make a talk in the Start box open the page with the builder open. Your text is the first message, the chips are `main`
   sources, and the job starts at once.
4. While a talk runs, the builder changes nothing. The room never sees the conversation or the ask control of a demo. The presenter and
   audience windows show demos with `askable=False`.

## The rule

Each way to make or change a walk or a talk ends in one conversation, on one brief.

## The brief

The brief is one record. It is kept on the conversation and on the walk or the talk. The tools of the agent and the brief box write it
through one function. After each change the conversation keeps a snapshot. When you change the brief by hand, the next turn of the agent
starts with a short note, such as "The owner changed: research off; aim = become technical".

- `sources`: each a chip id with a role: `main`, `extra` or `dropped`. The main sources win a conflict.
- `rules`, `aim`, `audience`, `no_code`, `minutes`, `goal` and `kind`.
- `research`: on or off. Off means that abhyasa uses only your sources: no web search, and no passage from the rest of the vault.
- `keep`: the slides or steps that do not change.
- `found`: the finds of research, each with the role that you gave it.

`brief_asks` puts the brief in plain words. The planner and the slide writer get it as an instruction from the owner (`owner_says`), never
as a `<source>`.

## The agent

One ramabana agent for each conversation, made by `ramabana_lead` with no web tools (`web=False`). Research goes only through the
`research` tool. Its system prompt is `build.agent`, which you can change in Settings. A turn runs as a pool job, so the activity chip
and Stop work. When the app starts again, the first turn gets a recap of the conversation.

## The tools

Each tool is a thin wrapper over an engine function or a hook of the talk block.

| Tool | Stands on |
|---|---|
| `add_source`, `set_source`, `set_brief`, `keep`, `free` | the brief |
| `show` | the walk or the talk now |
| `make_talk` | `walk_for_talk`, `talk_from_walk` |
| `make_walk` | `walk_for_talk`; a remake: `replan_walk`, or with research off a walk from your sources only, as one change |
| `change_talk` | the slide rewrite (`talk_rewrite` hook), or `talk_again` / `talk_fresh`; kept slides stay word for word |
| `edit_slide`, `set_poll` | the `edit` of the talk editor (`talk_edit` hook) |
| `make_demo` | `make_demo` of the engine, then the `talk_demo` hook |
| `change_walk` | `propose`, `improve_walk` |
| `research` | `web_search`; the finds wait for Keep |
| `undo` | the history and Undo of the walk or the talk |

## The pane

- Your brief: a fold with one line. ⌥A opens it.
- The thread: your message, one row for each tool call, then one line from the builder with Undo, and What I read and What changed.
- The view of a tool comes from a dict that maps a tool name to its renderer: research shows the finds, a change shows before and after,
  a make shows the outline, and a demo shows the demo live, with "Ask about this".
- The box takes voice (⌥D). ⌥S sends, ⌥X stops, ⌥W goes to the box, ⌘Z undoes, F keeps a find and X drops it. ⌥E opens or closes the builder.
- After a change, the page at the left loads again, and the pane stays open.

## The slot of a talk

`make_talk(minutes)` fits the slot before it writes the slides: `fit_walk` skips steps of the hidden walk from the end until the slides and the
closing slides fit. A slide that explains a section of a notebook counts only what it shows. A remake keeps the fit. The tool result gives
the real minutes against the slot, and the agent says those numbers.

## The pages

- Keep and Kept replace Lock on the walk page, and each slide of the talk editor has Keep (F). The builder reads them as `keep`.
- Make it again is one item in the ⋯ menu, with no form. Make it again from scratch is a second item.
- The change box of the walk page and Change this slide send the words to the builder, in the side pane.
- A change by hand adds a quiet line to the conversation, and a note for the next turn.
- After a change of the builder, the page at the left takes it in place, and the rows that changed get `.landed`.
- A narrow window has two tabs: Builder and Result.

## Trust

- The line after a turn comes from what the tools did, never from the words of the model. A reply that tells of a change that no tool made
  gets the line "Nothing changed in the walk or the talk in this turn." The words of the model and the calls that did not work are in openable parts.
- A walk says how many steps have a passage from a source. A kept web find is filed before a make, so its passages reach the steps.
- When you decide the last open find, the builder starts a turn that uses the kept finds.
- Conflicts: `passages` reads the main and the extra sources, and `note_conflict` keeps two quotes word for word, each with its link, and the source that won.
- Undo takes back each change of the last turn in one step.
- A rule covers the whole walk or talk. A fix for one slide is not a rule.

## Events

The conversation keeps events with the names and fields of AG-UI. `events.py` reads them for the pane. A ramabana with `Agent.events`
gives them itself; with an older ramabana, the builder makes them from the tool calls. They go to the page through the job event stream.

## Demos

`make_demo(slide, what)` makes a rupaka demo from your words and puts it on the slide. A question from the demo (`rk-ask`) puts a message
in the box, such as "About the demo on slide 4 (temperature = 2): …".

## Not in version 1

- A builder for courses, and two or more people in one conversation.
- Removing the Start box.

## Proof

The browser flows run against a copy of the vault, never the real vault and never the server on port 5088:

1. A talk from a notebook, for managers, 20 minutes, from the notebook only.
2. Slide 3 changes, slide 2 stays word for word, and Undo works.
3. A walk on attention, with research that waits for Keep, then "use only my sources".
4. "Change with the builder" beside a talk, and one change.
5. A demo on a slide of a talk, live in the builder and in the presenter window.
