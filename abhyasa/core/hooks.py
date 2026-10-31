"""Blocks add to each other's pages without importing each other (vedicreader's `vr/core/hooks.py`).

The hooks: `today_top`, `today_next`, `learn_talks`, `learn_start`, `today_end` (the parts of Home, in that order: Continue, the reviews,
Teach after your courses and walks, Start something new, and the foot, whose parts go on one line);
`learning_top(subject='')` (the parts of You → Progress after This week: Your strengths, of one subject when `subject` is given) and `learning_end` (the end of Progress);
`nav_extra` (the right of the top bar: Continue, the activity chip, Explain, in the connect order);
`page_extra` (once at the end of each page); `concept_actions` and `concept_more` (a concept page); `answer_tools(q, into)` (the session
composer, and the answer row of a short check on a walk step); `lesson_extra` (under a lesson).

The walk step: `step_needs(j, i, c)` (under the title: the ideas the step needs, and the strip after a side walk);
`check_after(j, i, q)` (under a check: the gaps that an answer points at); `walk_end(j)` (the end of a walk: a side walk sends
`rh:done`); `concepts_added()` (a block added concepts from a source: the concepts block places the new ones in the groups of their subjects, on the pool); `walk_made(j)` (a block made topic walk `j`: the walk block looks for web sources for its steps on the pool); `walk_actions(j, quiet=False, row=False)` (the walk page, its step page and its row on Home: the talk adds
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
