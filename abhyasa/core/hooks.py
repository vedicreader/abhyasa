"""Blocks add to each other's pages without importing each other (vedicreader's `vr/core/hooks.py`).

The hooks: `today_top`, `today_next`, `today`, `today_end` (the parts of Today, in that order; `today_end` parts go on one line);
`learning_end` (the end of Your learning); `nav_extra` (the right of the top bar);
`page_extra` (once at the end of each page); `concept_actions` and `concept_more` (a concept page); `answer_tools` (the session
composer); `lesson_extra` (under a lesson).

The walk step: `step_needs(j, i, c)` (under the title: the ideas the step needs, and the strip after a side walk);
`check_after(j, i, q)` (under a check: the gaps that an answer points at); `walk_end(j)` (the end of a walk: a side walk sends
`rh:done`); `walk_actions(j)` (beside the actions of the plan of a walk and of its journey page: the talk adds
"Present this walk"); `term_lookup(term, at)` (a selected term as `{slug, name, statement, url}`).

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
