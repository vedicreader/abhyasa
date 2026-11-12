"""Work with abhyasa, the tutor that asks you questions. Write exercises and notebook steps that abhyasa and Leela accept, link a walk step to Leela, drive the learning operations from a host agent, or run the tutor from Python. Use this skill when you write a lesson exercise, the notebook spec of a walk step, an Open in Leela link, or a tool that wraps abhyasa.

## Words

| word | what it is |
|---|---|
| walk | an ordered list of ideas toward one goal, made from a source or from the goal. `jid` is its id |
| step | one idea of a walk, with a passage from the source and a check. `i` is its place in the walk |
| concept | one idea that the learner model tracks, by its slug |
| check | a question that asks the learner to explain, predict, compare or apply an idea |
| attempt | one graded answer to a check |
| shelf | the `learning` shelf of the vishalakshi vault. It holds the concepts, attempts, sessions and walks |

`abhyasa.contract` holds the names that abhyasa and Leela share. It imports only the standard library.

## Write an exercise

An exercise asks the learner to write one function. Its tests are plain `assert` lines on that function.

```python
from abhyasa.contract import check_exercise, safe_test, validate_nb_spec, handoff, read_handoff
ex = dict(task='Write rrf(ranks, k) that gives the reciprocal rank fusion score of a list of ranks.', fname='rrf',
          stub='def rrf(ranks, k=60): ...',
          tests=['assert rrf([1], 60) == 1/61',
                 dict(test='assert rrf([], 60) == 0', say='No ranks give zero.', hidden=True)])
assert check_exercise(ex)['fname'] == 'rrf'
assert not safe_test('assert rrf.__class__', 'rrf')
```

`check_exercise(ex)` gives the clean exercise, or raises `ValueError` with the reason. It refuses an exercise that breaks one of these rules:

- `task` is a text that is not empty. `stub` is a text.
- `fname` is a plain Python name that does not start with `_`.
- `tests` has 1 to 12 items. An item is a test text, or an object `{test, say, hidden}`.
- Each test is one `assert` (`safe_test`). It uses only `fname`, literals, the names of its own comprehensions and the builtins in `SAFE_NAMES`. It has no import, no assignment, no `def`, no `lambda` and no attribute that starts with `_`. A string in it has at most 2000 characters.

In Leela, the `add_exercise` tool puts an exercise in a lesson notebook. It runs the solution only to check the tests, and it never stores the solution. Leela's `check_exercise` tool runs the learner's cell and its tests. It is a different function from `abhyasa.contract.check_exercise`.

## The notebook spec of a walk step

A step that teaches with code opens in Leela as a notebook. `validate_nb_spec(spec)` checks its spec and gives it back with only the keys of the contract (`NB_KEYS`). A `ValueError` starts with the key that fails.

```python
nb = validate_nb_spec(dict(task=ex['task'], fname='rrf', stub=ex['stub'],
                           tests=[dict(test='assert rrf([1], 60) == 1/61', say='One list at rank 1.', shown=True)],
                           run=dict(say='fuse two ranked lists and print the top 3', minutes=2, makes='a ranked list',
                                    predict='Which item comes first?')))
assert nb['run']['say'] == 'Write the run here: fuse two ranked lists and print the top 3'
```

- `tests` is a list of objects `{test, say, shown}`. `say` is one line of 1 to 200 characters, and `shown` is true or false.
- `requires` has at most 5 package names. `data` has at most 8 entries `{name, path, what, need}`. A `name` is an upper-case Python name, and a `path` is inside the home folder, or empty for a folder that the learner adds.
- `run` is required: `say`, `minutes` from 0 to 600, `makes` and `predict`. `say` starts with `RUN_SAY`, and the function adds it when it is missing.
- `demo` is the slug of a demo, at most 100 characters on one line, or empty.
- `task` and `stub` have no line that starts with `#|`. Each other text is one line.

## Open in Leela

`handoff` gives the path and query that Leela opens for a walk, a step, a topic or a notebook in the vault. `read_handoff` reads them back and checks them. It raises `ValueError` with the reason when the query is not valid.

```python
link = handoff('rrf-basics', 2)
assert link == '/learn?walk=rrf-basics&step=2'
assert read_handoff(link.split('?', 1)[1])['step'] == 2
```

abhyasa runs no code. It never calls Leela. A running Leela writes a file that abhyasa reads, and abhyasa links only to an address on this computer.

## Drive abhyasa from a host agent

`abhyasa.agent_tools` holds the learning operations that a host agent, such as Leela, wraps as tools. Its import loads the whole engine and the settings.

Each operation takes the learner's store `lr` (a `Learning`). An operation that calls a model also takes the host's `ask(prompt, sp='')`. Only `create_walk`, `record_attempt` and `change_walk` call a model.

| operation | what it does |
|---|---|
| `create_walk(lr, ask, goal)` | plans a walk to `goal` and saves it, with a passage from the vault for each step |
| `walk_state(lr, jid)` | gives the walk as plain data: its steps, their quotes and checks, and the gauge of each concept |
| `record_attempt(lr, jid, i, answer, attempt_id, ask)` | grades the answer to the check of step `i` and saves it, once for each `attempt_id` |
| `record_code_attempt(lr, jid, i, ok, attempt_id)` | files one graded run of the code of step `i`, with no model |
| `note_confusion(lr, jid, i, note)` | keeps what confuses the learner on step `i` |
| `change_walk(lr, ask, jid, instruction)` | changes the walk from the learner's words |
| `keep_idea`, `drop_idea`, `move_idea` | locks, removes or moves one idea |
| `add_source(lr, jid, source)` | files a source and adds it to the walk |
| `list_versions`, `restore_version` | lists the earlier versions of a walk; goes back to one |
| `explain_here(lr, jid, i, note)` | gives the data and the rules to explain step `i`; the agent writes the explanation |
| `learner_context(lr, jid, i)` | gives a short plain-text block for a system prompt |

Each operation gives one dict with `status` (`ok`, `error` or `stopped`), `operation_id`, `vault`, `walk`, `step`, `revision`, `data` and `error`. An expected failure does not raise. It has `status` `error`, an `error` from `ERRORS`, and `data['message']`. A change to a walk takes the `revision` that the caller last saw, and refuses an old one with `stale_state`. Each change has an Undo in the history of the walk. `TOOLS` lists each operation that a host makes a tool, with the arguments that the model gives. `READS` names the tools that change nothing. The host owns privacy: `create_walk` takes the host's `guard(text)`.

## The tutor in Python

This example runs offline. `temp_learning` makes a shelf in a vault in a temporary folder, and `Fake` takes the place of the model.

```python
from abhyasa.learner import temp_learning
from abhyasa.models import Fake
from abhyasa.tutor import Tutor
lr = temp_learning()
lr.put('Ranking', 'Order items by a score.', 'ml')
fake = Fake({'You grade one answer': dict(correct=True, grade=8, first_error='', misconception='', feedback='Yes. Only the order counts.')},
            dflt=dict(question='Why can you compare ranks from two systems, but not their scores?', answer='Ranks share one scale.',
                      rubric=['ranks share one scale']))
t = Tutor(lr, fake, context=False)
q = t.next()
r = t.answer(q.id, 'A rank is a position, and positions use the same scale in each list.', confidence=80)
assert r.outcome == 'solid'
```

- In a notebook, `from abhyasa.tutor import learn` and `learn('reciprocal-rank-fusion')` give a question card on the default vault.
- A test never opens the real vault (`~/.vishalakshi/vault.db`). Use `temp_learning()`. Set `ABHYASA_CONFIG` to a temporary folder and `RAMABANA_CONFIG` to a `config.toml` file in a temporary folder, so that the test reads no real settings.
- abhyasa makes demos with rupaka. Read the `rupaka` skill to write one. `abhyasa.show.make_demo(lr, ask, slug)` makes a demo for a concept and stores it, or gives None when the model fails. It plays the demo in a browser only when `rupaka.check.can_check()` is True. `make_explainer(lr, ask, slug)` makes a 3D explainer.

## The app

`uv run abhyasa` in a clone, or `abhyasa` after `uv tool install abhyasa`, starts the web app on http://127.0.0.1:5077. It answers only requests from this computer. `ABHYASA_VAULT` sets the vault file, and `ABHYASA_CONFIG` sets the folder of the settings and keys.

## This sheet in a harness

The `pyskills` entry point `abhyasa` names this module. Leela and ramabana list it with the other skills, and `read_skill('abhyasa')` reads it. When `pyskills` is installed, this module allows the names in `ALLOW` in a sandbox. They are the checks of `abhyasa.contract`, which read no file of the learner and need no model.

`mv_skill_md(dry_run=False)` writes this sheet as `.agents/skills/abhyasa/SKILL.md` and `.claude/skills/abhyasa/SKILL.md` in the current git repository, for Claude Code, Codex and other harnesses that read Agent Skills.

Docs: https://vedicreader.github.io/abhyasa/skill.html.md"""

# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/07_skill.ipynb.

# %% auto #0
__all__ = ['ALLOW', 'skill_md', 'mv_skill_md']

# %% ../nbs/07_skill.ipynb #670bfb1e
from importlib import import_module
import json
from fastcore.xtras import Path, find_file_parents
from . import contract
try: from pyskills import allow
except ImportError: allow = None

ALLOW = {contract: 'safe_test check_exercise validate_nb_spec has_directive data_path_why run_ok handoff read_handoff'.split()}
if allow: allow(ALLOW)

# %% ../nbs/07_skill.ipynb #d147c49d
def skill_md() -> str:
    "This sheet as an Agent Skills `SKILL.md`: a front matter with `name` and `description`, then the body."
    desc, _, body = import_module('abhyasa.skill').__doc__.partition('\n\n')
    return f"---\nname: abhyasa\ndescription: {json.dumps(' '.join(desc.split()), ensure_ascii=False)}\n---\n\n{body}\n"

def mv_skill_md(dry_run=True, dir=None):
    "Write `skill_md()` to the `.agents` and `.claude` skill folders of `dir` or of the current git repository; with `dry_run`, print the paths only."
    root = Path(dir or find_file_parents('.git') or '.')
    ts = [root/f'{d}/skills/abhyasa/SKILL.md' for d in ('.agents', '.claude')]
    if dry_run: return print(f'Would write: {list(map(str, ts))}')
    for p in ts: p.mk_write(skill_md())
    print(f'Wrote: {list(map(str, ts))}')
