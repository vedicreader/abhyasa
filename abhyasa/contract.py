"""The names that abhyasa and Leela share: the test rule of an exercise, the notebook spec of a walk step, and the check of a run
result that Leela files. This module imports only the standard library, so Leela imports it with no abhyasa web code and no settings."""
import ast, math, re
from pathlib import Path

__all__ = ['SAFE_NAMES', 'SAFE_NODES', 'safe_test', 'check_exercise', 'WALK_ID', 'PKG', 'DATA_NAME', 'NB_KEYS', 'RUN_MINUTES',
           'validate_nb_spec', 'NB_SPEC_CASES', 'RUN_METRICS', 'RUN_IMAGES', 'RUN_IMAGE', 'run_ok', 'RUN_CASES']

# --- the test rule of an exercise --------------------------------------------------------------------------------------

SAFE_NAMES = ('abs', 'all', 'any', 'bool', 'dict', 'enumerate', 'float', 'int', 'isinstance', 'len', 'list', 'max', 'min',
              'range', 'reversed', 'round', 'set', 'sorted', 'str', 'sum', 'tuple', 'zip', 'True', 'False', 'None')
SAFE_NODES = (ast.Module, ast.Assert, ast.Expr, ast.Compare, ast.Call, ast.Name, ast.Load, ast.Constant, ast.List, ast.Tuple, ast.Dict,
              ast.Set, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Subscript, ast.Slice, ast.keyword, ast.Attribute, ast.IfExp,
              ast.operator, ast.unaryop, ast.boolop, ast.cmpop, ast.ListComp, ast.GeneratorExp, ast.comprehension, ast.Store)

def safe_test(t:str, fname:str) -> bool:
    "Whether `t` is one plain `assert` that uses only `fname`, literals and the safe builtins."
    try: tree = ast.parse(t)
    except SyntaxError: return False
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Assert): return False
    bound = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}   # names of a comprehension
    for n in ast.walk(tree):
        if not isinstance(n, SAFE_NODES): return False
        if isinstance(n, ast.Name) and n.id not in (fname, *SAFE_NAMES, *bound): return False
        if isinstance(n, ast.Attribute) and n.attr.startswith('_'): return False
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and len(n.value) > 2000: return False
    return True

def check_exercise(r) -> dict:
    "Check the model's exercise and raise `ValueError` with the reason if invalid. `abhyasa.check.validate_exercise` gives the same as an `AttrDict`."
    if not isinstance(r, dict): raise ValueError('the reply is not a JSON object')
    task, fname, stub, tests = r.get('task'), r.get('fname'), r.get('stub'), r.get('tests')
    if not (isinstance(task, str) and task.strip()): raise ValueError('`task` must be a text')
    if not (isinstance(fname, str) and fname.isidentifier() and not fname.startswith('_')): raise ValueError('`fname` must be a plain function name')
    if not isinstance(stub, str): raise ValueError('`stub` must be a text')
    if not (isinstance(tests, list) and 1 <= len(tests) <= 12): raise ValueError('`tests` must be a list of 1 to 12 texts or test objects')
    for t in tests:
        if isinstance(t, dict):
            if not isinstance(t.get('say', ''), str) or not isinstance(t.get('hidden', False), bool):
                raise ValueError('a test object needs text `say` and boolean `hidden`')
            t = t.get('test')
        if not isinstance(t, str): raise ValueError('`tests` must be a list of 1 to 12 texts or test objects')
        if not safe_test(t, fname): raise ValueError(f'a test is not one plain assert on `{fname}`: {t[:120]}')
    return dict(task=task, fname=fname, stub=stub, tests=tests, solution=r.get('solution', '') if isinstance(r.get('solution'), str) else '')

# --- the notebook spec of a walk step ----------------------------------------------------------------------------------

WALK_ID = re.compile(r'^[a-z0-9-]{1,48}$')                    # the form of a walk id (`journey._new_id`)
PKG = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')        # one package name, with no extra and no version (Leela's `_NAME`)
DATA_NAME = re.compile(r'^[A-Z][A-Z0-9_]{0,39}$')             # the name of a data path in the notebook: an upper-case Python name
NB_KEYS = ('task', 'fname', 'stub', 'tests', 'requires', 'data', 'run', 'demo')
RUN_MINUTES = 600                                              # the most minutes that a run can say

def _text(x, most:int=2000) -> bool: return isinstance(x, str) and len(x) <= most

def _number(x) -> bool: return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)

def _under_home(p) -> bool:
    "Whether path `p`, with `~` read and links followed, is inside the home folder (and is not the home folder)."
    try: q, home = Path(p).expanduser().resolve(), Path.home().resolve()
    except (OSError, RuntimeError, ValueError): return False
    return q != home and q.is_relative_to(home)

def _exercise_key(e:ValueError) -> str:
    "The spec key that an exercise error names: `task`, `fname` or `stub`, else `tests`."
    return next((k for k in ('task', 'fname', 'stub') if f'`{k}`' in str(e)), 'tests')

def validate_nb_spec(spec) -> dict:
    """The notebook spec of a walk step, checked, with only the keys of the contract. A `ValueError` starts with the key that fails:
    `task`, `fname`, `stub` or `tests` (the exercise rule, `say` 1 to 200 characters, `shown` a bool), `requires` (at most 5 names that
    match `PKG`), `data` (an upper-case `name`, a `path` inside the home folder, text `what`, bool `need`), `run` (a text `say`, `minutes`
    from 0 to `RUN_MINUTES`, text `makes` and `predict`) or `demo` (a text)."""
    if not isinstance(spec, dict): raise ValueError('spec: the spec is not a JSON object')
    rows = spec.get('tests')
    if not (isinstance(rows, list) and all(isinstance(t, dict) for t in rows)): raise ValueError('tests: give a list of test objects {test, say, shown}')
    try: ex = check_exercise({k: spec.get(k) for k in ('task', 'fname', 'stub')} | {'tests': [t.get('test') for t in rows]})
    except ValueError as e: raise ValueError(f'{_exercise_key(e)}: {e}') from None
    tests = []
    for t in rows:
        say = t.get('say')
        if not (isinstance(say, str) and say.strip() and len(say) <= 200 and say.isprintable()): raise ValueError('tests: `say` must be a short plain text (1 to 200 characters)')
        if type(t.get('shown')) is not bool: raise ValueError('tests: `shown` must be true or false')
        tests.append(dict(test=t['test'], say=say, shown=t['shown']))
    req = spec.get('requires', [])
    if not (isinstance(req, list) and len(req) <= 5): raise ValueError('requires: give a list of at most 5 package names')
    if bad := [n for n in req if not (isinstance(n, str) and PKG.match(n))]: raise ValueError(f'requires: {str(bad[0])[:40]!r} is not a package name')
    data = spec.get('data', [])
    if not (isinstance(data, list) and len(data) <= 8): raise ValueError('data: give a list of at most 8 data entries')
    for d in data:
        if not isinstance(d, dict): raise ValueError('data: each entry is an object {name, path, what, need}')
        if not (isinstance(d.get('name'), str) and DATA_NAME.match(d['name'])): raise ValueError('data: `name` must be an upper-case Python name, as EPISODES')
        if not (_text(d.get('path'), 500) and d['path'].strip() and _under_home(d['path'])): raise ValueError(f"data: the path of {d['name']} is not in your home folder")
        if not _text(d.get('what', ''), 200): raise ValueError('data: `what` must be a short text')
        if type(d.get('need', False)) is not bool: raise ValueError('data: `need` must be true or false')
    if len({d['name'] for d in data}) != len(data): raise ValueError('data: two entries have the same name')
    run = spec.get('run')
    if not isinstance(run, dict): raise ValueError('run: the spec has no run')
    if not (_text(run.get('say')) and run['say'].strip()): raise ValueError('run: `say` must say what the run does')
    if not (_number(run.get('minutes')) and 0 <= run['minutes'] <= RUN_MINUTES): raise ValueError(f'run: `minutes` must be a number from 0 to {RUN_MINUTES}')
    if not (_text(run.get('makes', ''), 200) and _text(run.get('predict', ''), 300)): raise ValueError('run: `makes` and `predict` must be short texts')
    if not _text(spec.get('demo', ''), 100): raise ValueError('demo: `demo` must be the slug of a demo, or empty')
    return dict(task=ex['task'], fname=ex['fname'], stub=ex['stub'], tests=tests, requires=list(req),
                data=[dict(name=d['name'], path=d['path'], what=d.get('what', ''), need=d.get('need', False)) for d in data],
                run=dict(say=run['say'], makes=run.get('makes', ''), minutes=run['minutes'], predict=run.get('predict', '')), demo=spec.get('demo', ''))

_GOOD = dict(task='Write `caption(ep, places, chars)`. It gives one line for one episode: the summary, the names of the people who act, and the place. Then run it on all the episodes.',
             fname='caption', stub='def caption(ep, places, chars):\n    ...',
             tests=[dict(test="assert caption({'desc': 'Valmiki asks Narada.', 'acts': ['valmiki'], 'place': 'hermitage'}, {'hermitage': 'the hermitage'}, {'valmiki': 'Valmiki'}) == 'Valmiki asks Narada. Valmiki. the hermitage.'",
                         say='episode 1', shown=True),
                    dict(test="assert caption({'desc': 'Narada tells.', 'acts': [], 'place': ''}, {}, {}) == 'Narada tells.'", say='no people and no place', shown=False)],
             requires=[],
             data=[dict(name='EPISODES', path='~/code/personal/orgs/vedicreader/static/story/ramayana/episodes.json', what='episodes', need=False),
                   dict(name='IMAGES', path='~/Pictures/comic', what='the images to train on', need=True)],
             run=dict(say='Run it on all episodes. Write one line to captions.jsonl for each.', makes='captions.jsonl', minutes=2, predict='How many episodes have no place?'),
             demo='')

NB_SPEC_CASES = [(_GOOD, None),
                 ({**_GOOD, 'requires': ['torch', 'diffusers', 'transformers', 'peft', 'accelerate']}, None),
                 ({**_GOOD, 'requires': list('abcdef')}, 'requires'),
                 ({**_GOOD, 'requires': ['torch; rm -rf ~']}, 'requires'),
                 ({**_GOOD, 'data': [{**_GOOD['data'][0], 'path': '/etc/passwd'}]}, 'data'),
                 ({**_GOOD, 'data': [{**_GOOD['data'][0], 'path': '~/../../etc'}]}, 'data'),
                 ({**_GOOD, 'data': [{**_GOOD['data'][0], 'name': 'episodes'}]}, 'data'),
                 ({**_GOOD, 'tests': [dict(test='import os', say='os', shown=True)]}, 'tests'),
                 ({**_GOOD, 'tests': [dict(test='assert caption(EP1) == 1', say='a name that is not a value', shown=True)]}, 'tests'),
                 ({**_GOOD, 'tests': [dict(test="assert caption({}, {}, {}) == ''", say='', shown=True)]}, 'tests'),
                 ({k: v for k, v in _GOOD.items() if k != 'task'}, 'task'),
                 ({k: v for k, v in _GOOD.items() if k != 'run'}, 'run'),
                 ({**_GOOD, 'run': {**_GOOD['run'], 'minutes': 900}}, 'run'),
                 ({**_GOOD, 'run': {**_GOOD['run'], 'say': ''}}, 'run')]

# --- the check of a run result that Leela files -------------------------------------------------------------------------

RUN_METRICS, RUN_IMAGES = 12, 4                                # the most numbers and images of one run
RUN_IMAGE = re.compile(r'^leela/([a-z0-9-]{1,48})/(0|[1-9][0-9]{0,3})/(0|[1-9][0-9]{0,2})\.png$')   # leela/<walk>/<step>/<n>.png in the vault assets

def run_ok(a) -> bool:
    """Whether `a` is a run attempt that abhyasa can show: `kind='run'` and `app='leela'`, a walk id and a step, at most `RUN_METRICS`
    numbers by name, at most `RUN_IMAGES` asset paths `leela/<walk>/<step>/<n>.png` of this walk and step, and plain `secs`, `device`,
    `notebook` and `makes`."""
    if not (isinstance(a, dict) and a.get('kind') == 'run' and a.get('app') == 'leela'): return False
    walk, step = a.get('walk'), a.get('step')
    if not (isinstance(walk, str) and WALK_ID.match(walk) and type(step) is int and 0 <= step < 10_000): return False
    m = a.get('metrics', {})
    if not (isinstance(m, dict) and len(m) <= RUN_METRICS and all(isinstance(k, str) and 0 < len(k) <= 40 and k.isprintable() and _number(v) for k, v in m.items())): return False
    ims = a.get('images', [])
    if not (isinstance(ims, list) and len(ims) <= RUN_IMAGES and len(set(map(str, ims))) == len(ims)): return False
    for p in ims:
        g = isinstance(p, str) and RUN_IMAGE.match(p)
        if not (g and g[1] == walk and int(g[2]) == step): return False
    if 'secs' in a and not (_number(a['secs']) and a['secs'] >= 0): return False
    return all(_text(a.get(k, ''), 500) for k in ('device', 'notebook', 'makes'))

_RUN = dict(kind='run', app='leela', walk='ramayana-comic-ab12', step=7, metrics=dict(loss=0.083, steps=500), images=['leela/ramayana-comic-ab12/7/0.png', 'leela/ramayana-comic-ab12/7/1.png'],
            secs=124.5, device='mps', notebook='lessons/ramayana-comic-ab12-7.ipynb', makes='lora.safetensors')

RUN_CASES = [(_RUN, True),
             ({**_RUN, 'images': []}, True),
             ({**_RUN, 'app': 'abhyasa'}, False),
             ({**_RUN, 'kind': 'code'}, False),
             ({**_RUN, 'walk': '../x'}, False),
             ({**_RUN, 'step': True}, False),
             ({**_RUN, 'metrics': {f'm{k}': k for k in range(13)}}, False),
             ({**_RUN, 'metrics': dict(loss='low')}, False),
             ({**_RUN, 'metrics': dict(loss=float('nan'))}, False),
             ({**_RUN, 'images': [f'leela/ramayana-comic-ab12/7/{k}.png' for k in range(5)]}, False),
             ({**_RUN, 'images': ['leela/ramayana-comic-ab12/7/../../x/0.png']}, False),
             ({**_RUN, 'images': ['/Users/x/leela/ramayana-comic-ab12/7/0.png']}, False),
             ({**_RUN, 'images': ['leela/other-walk/7/0.png']}, False),
             ({**_RUN, 'images': ['leela/ramayana-comic-ab12/6/0.png']}, False),
             ({**_RUN, 'images': ['leela/ramayana-comic-ab12/7/x.png']}, False),
             ({**_RUN, 'secs': -1}, False)]
