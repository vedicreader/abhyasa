"""Blocks add to each other's pages without importing each other (vedicreader's `vr/core/hooks.py`).

The hooks: `today_top`, `today_next`, `today`, `today_end` (the parts of Today, in that order; `today_end` parts go on one line);
`learning_top` (the parts of Your learning after This week: Your strengths) and `learning_end` (the end of Your learning);
`learn_talks` and `learn_start` (the parts of Learn after your walks: your talks, and Start something new); `start_more` (under More in
the Start box: the goal box); `nav_extra` (the right of the top bar);
`page_extra` (once at the end of each page); `concept_actions` and `concept_more` (a concept page); `answer_tools(q, into)` (the session
composer, and the answer row of a short check on a walk step); `lesson_extra` (under a lesson).

The walk step: `step_needs(j, i, c)` (under the title: the ideas the step needs, and the strip after a side walk);
`check_after(j, i, q)` (under a check: the gaps that an answer points at); `walk_end(j)` (the end of a walk: a side walk sends
`rh:done`); `concepts_added()` (a block added concepts from a source: the concepts block places the new ones in the groups of their subjects, on the pool); `walk_made(j)` (a block made topic walk `j`: the walk block looks for web sources for its steps on the pool); `walk_from_path(j)` (the path page asks to make path `j` a walk that reads your sources: the walk block does it on the pool and gives its pending card); `walk_actions(j, quiet=False, row=False)` (the plan of a walk, its step page, its last page and its path page: the talk adds
"Present this walk", or "Open the talk" and "Make it again", also on a walk planned from a goal; `quiet` is for a page with its own main button;
`row` is for its row in a list, with one quiet control: "Present" or "Open the talk"); `walk_plan_more(j)` (under the plan of walk `j`: the add block puts Add a source there for a goal walk);
`walk_add_sources(jid, ids)` (the walk block files the chips `ids` for walk `jid`, each on its own job, and each one joins the walk
when it is filed: it gives the ids that it started).
`show_me(words, at)` ("show me …" in an answer box: the demo block gives the card of a demo made from `words`; `at` is the place, `{where: 'walk', concept, walk, step}` or
`{where: 'session', qid}`, or `{where: 'guide', concept}` for "show me …" to the screen guide; on a walk step the card swaps into the place under the title).
`goal_walk(j)` (the walk block made walk `j` from a goal on Start: the course block joins it to the course of its goal).
`guide_board(page, board)` (the screen guide drew `board` on the page at the path `page`, which shows a check: the walk block counts it
as one hint on the open check of that step, and gives the line for the check).

The side pane: `pane_title(url)` (the title of the page at the local path `url`, for the pane bar and the line under 1100 px)."""
from collections import defaultdict

__all__ = ['HOOKS', 'hook', 'run', 'clear']

HOOKS = defaultdict(list)

def hook(name):
    "Register `f` under `name`."
    def d(f): HOOKS[name].append(f); return f
    return d

def run(name, *a, **kw):
    "Call every function under `name`; keep the results that are not None."
    return [r for f in HOOKS[name] if (r := f(*a, **kw)) is not None]

def clear():
    "Drop every hook; a new app connects its blocks again."
    HOOKS.clear()
