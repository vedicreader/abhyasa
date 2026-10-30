"""The names that abhyasa and Leela share: the test rule of an exercise, the notebook spec of a walk step, and the check of a run
result that Leela files, and the link from a walk step to Leela. This module imports only the standard library, so Leela imports it
with no abhyasa web code and no settings."""
import ast, hashlib, math, re
from pathlib import Path
from urllib.parse import urlencode, parse_qs

__all__ = ['SAFE_NAMES', 'SAFE_NODES', 'safe_test', 'check_exercise', 'WALK_ID', 'PKG', 'DATA_NAME', 'NB_KEYS', 'RUN_MINUTES',
           'has_directive', 'data_path_why', 'path_why', 'validate_nb_spec', 'NB_SPEC_CASES', 'RUN_METRICS', 'RUN_IMAGES', 'RUN_IMAGE', 'run_ok', 'RUN_CASES',
           'LEELA_ROUTE', 'TOPIC_MAX', 'VAULT_KEY', 'vault_key', 'Handoff', 'handoff', 'read_handoff', 'HANDOFF_CASES', 'HANDOFF_BAD']

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

# Each pattern starts with `\A` and ends with `\Z`, so `match` and `fullmatch` both refuse a final newline (`$` accepts one).
WALK_ID = re.compile(r'\A[a-z0-9-]{1,48}\Z')                  # the form of a walk id (`journey._new_id`)
PKG = re.compile(r'\A[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z')      # one package name, with no extra and no version (Leela's `_NAME`)
DATA_NAME = re.compile(r'\A[A-Z][A-Z0-9_]{0,39}\Z')           # the name of a data path in the notebook: an upper-case Python name
NB_KEYS = ('task', 'fname', 'stub', 'tests', 'requires', 'data', 'run', 'demo')
RUN_MINUTES = 600                                              # the most minutes that a run can say

def _text(x, most:int=2000) -> bool: return isinstance(x, str) and len(x) <= most

def _line(x, most:int=200) -> bool:
    "Whether `x` is a text of one line: at most `most` characters, and no newline, tab or other control character."
    return _text(x, most) and x.isprintable()

def _number(x) -> bool:
    "Whether `x` is a finite int or float, and not a bool. An int too large for a float is not one."
    if not isinstance(x, (int, float)) or isinstance(x, bool): return False
    try: return math.isfinite(x)
    except OverflowError: return False

def has_directive(text) -> bool:
    "Whether a line of `text` starts with `#|` after its leading white space: a notebook directive, as `#| setup` or `#| test`."
    return isinstance(text, str) and any(l.lstrip().startswith('#|') for l in text.splitlines())

def data_path_why(p) -> str:
    """Why `p` cannot be the data path of an exercise, or an empty text when it can. A data path is one line, has no `..`, is inside the home folder
    (not the home folder itself) with `~` read and links followed, and has no part that starts with a dot (as `~/.ssh`)."""
    if not (_line(p, 500) and p.strip()): return 'give a path of one line'
    try: given, home = Path(p).expanduser(), Path.home().resolve()
    except (RuntimeError, ValueError): return 'the path is not valid'
    if '..' in given.parts: return 'the path has ..'
    try: q = given.resolve()
    except (OSError, RuntimeError, ValueError): return 'the path is not valid'
    if q == home or not q.is_relative_to(home): return 'the path is not in your home folder'
    if any(x.startswith('.') for x in (*given.parts[1:], *q.relative_to(home).parts)): return 'a part of the path starts with a dot'
    return ''

path_why = data_path_why   # the old name: Leela imports `abhyasa.contract.path_why`

def _exercise_key(e:ValueError) -> str:
    "The spec key that an exercise error names: `task`, `fname` or `stub`, else `tests`."
    return next((k for k in ('task', 'fname', 'stub') if f'`{k}`' in str(e)), 'tests')

def validate_nb_spec(spec) -> dict:
    """The notebook spec of a walk step, checked, with only the keys of the contract. A `ValueError` starts with the key that fails:
    `task`, `fname`, `stub` or `tests` (the exercise rule, `say` 1 to 200 characters, `shown` a bool), `requires` (at most 5 names that
    match `PKG`), `data` (an upper-case `name`, a `path` inside the home folder, text `what`, bool `need`), `run` (a text `say`, `minutes`
    from 0 to `RUN_MINUTES`, text `makes` and `predict`) or `demo` (a text). Each text but `task` and `stub` is one line (`str.isprintable`).
    An empty `requires` is left out of the result, as Leela's exercise spec wants."""
    if not isinstance(spec, dict): raise ValueError('spec: the spec is not a JSON object')
    rows = spec.get('tests')
    if not (isinstance(rows, list) and all(isinstance(t, dict) for t in rows)): raise ValueError('tests: give a list of test objects {test, say, shown}')
    try: ex = check_exercise({k: spec.get(k) for k in ('task', 'fname', 'stub')} | {'tests': [t.get('test') for t in rows]})
    except ValueError as e: raise ValueError(f'{_exercise_key(e)}: {e}') from None
    for k in ('task', 'stub'):
        if has_directive(spec[k]): raise ValueError(f'{k}: a line starts with #|, which makes a setup or test cell in a notebook')
    tests = []
    for t in rows:
        say = t.get('say')
        if not (_line(say) and say.strip()): raise ValueError('tests: `say` must be a short plain text of one line (1 to 200 characters)')
        if type(t.get('shown')) is not bool: raise ValueError('tests: `shown` must be true or false')
        tests.append(dict(test=t['test'], say=say, shown=t['shown']))
    req = spec.get('requires', [])
    if not (isinstance(req, list) and len(req) <= 5): raise ValueError('requires: give a list of at most 5 package names')
    if bad := [n for n in req if not (isinstance(n, str) and PKG.fullmatch(n))]: raise ValueError(f'requires: {str(bad[0])[:40]!r} is not a package name')
    data = spec.get('data', [])
    if not (isinstance(data, list) and len(data) <= 8): raise ValueError('data: give a list of at most 8 data entries')
    for d in data:
        if not isinstance(d, dict): raise ValueError('data: each entry is an object {name, path, what, need}')
        if not (isinstance(d.get('name'), str) and DATA_NAME.fullmatch(d['name'])): raise ValueError('data: `name` must be an upper-case Python name, as EPISODES')
        if why := data_path_why(d.get('path')): raise ValueError(f"data: {d['name']}: {why}")
        if not _line(d.get('what', '')): raise ValueError('data: `what` must be a short text of one line')
        if type(d.get('need', False)) is not bool: raise ValueError('data: `need` must be true or false')
    if len({d['name'] for d in data}) != len(data): raise ValueError('data: two entries have the same name')
    run = spec.get('run')
    if not isinstance(run, dict): raise ValueError('run: the spec has no run')
    if not (_line(run.get('say'), 500) and run['say'].strip()): raise ValueError('run: `say` must say what the run does, in one line')
    if not (_number(run.get('minutes')) and 0 <= run['minutes'] <= RUN_MINUTES): raise ValueError(f'run: `minutes` must be a number from 0 to {RUN_MINUTES}')
    if not (_line(run.get('makes', '')) and _line(run.get('predict', ''), 300)): raise ValueError('run: `makes` and `predict` must be short texts of one line')
    if not _line(spec.get('demo', ''), 100): raise ValueError('demo: `demo` must be the slug of a demo, or empty')
    return dict(task=ex['task'], fname=ex['fname'], stub=ex['stub'], tests=tests, **(dict(requires=list(req)) if req else {}),
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
                 ({**_GOOD, 'run': {**_GOOD['run'], 'say': ''}}, 'run'),
                 ({**_GOOD, 'data': [{**_GOOD['data'][0], 'what': "x\nimport os; os.system('echo owned')"}]}, 'data'),
                 ({**_GOOD, 'data': [{**_GOOD['data'][0], 'path': "~/x')\nimport os"}]}, 'data'),
                 ({**_GOOD, 'data': [{**_GOOD['data'][0], 'name': 'EPISODES\n'}]}, 'data'),
                 ({**_GOOD, 'data': [{**_GOOD['data'][0], 'path': '~/code/../code/x.json'}]}, 'data'),
                 ({**_GOOD, 'data': [{**_GOOD['data'][0], 'path': '~/.ssh'}]}, 'data'),
                 ({**_GOOD, 'data': [{**_GOOD['data'][0], 'path': '~/.aws/credentials'}]}, 'data'),
                 ({**_GOOD, 'run': {**_GOOD['run'], 'say': "Run it.\nimport os; os.system('echo owned')"}}, 'run'),
                 ({**_GOOD, 'run': {**_GOOD['run'], 'makes': 'a\rb'}}, 'run'),
                 ({**_GOOD, 'run': {**_GOOD['run'], 'predict': 'How many?\tx'}}, 'run'),
                 ({**_GOOD, 'run': {**_GOOD['run'], 'minutes': 10**400}}, 'run'),
                 ({**_GOOD, 'run': {**_GOOD['run'], 'minutes': float('inf')}}, 'run'),
                 ({**_GOOD, 'run': {**_GOOD['run'], 'minutes': True}}, 'run'),
                 ({**_GOOD, 'tests': [dict(test="assert caption({}, {}, {}) == ''", say='a\nb', shown=True)]}, 'tests'),
                 ({**_GOOD, 'requires': ['torch\n']}, 'requires'),
                 ({**_GOOD, 'demo': 'x\ny'}, 'demo'),
                 ({**_GOOD, 'stub': '#| setup\nimport os\ndef caption(ep, places, chars): ...'}, 'stub'),
                 ({**_GOOD, 'stub': 'def caption(ep, places, chars):\n    #| test: x\n    import os'}, 'stub'),
                 ({**_GOOD, 'task': 'Write caption.\n  #| test: x'}, 'task')]

# --- the check of a run result that Leela files -------------------------------------------------------------------------

RUN_METRICS, RUN_IMAGES = 12, 4                                # the most numbers and images of one run
RUN_IMAGE = re.compile(r'\Aleela/([a-z0-9-]{1,48})/(0|[1-9][0-9]{0,3})/(0|[1-9][0-9]{0,2})\.png\Z')   # leela/<walk>/<step>/<n>.png in the vault assets

def run_ok(a) -> bool:
    "Whether `a` is a run attempt that abhyasa can show (`_run_ok`). It never raises: a strange value gives False."
    try: return _run_ok(a)
    except Exception: return False

def _run_ok(a) -> bool:
    """Whether `a` is a run attempt that abhyasa can show: `kind='run'` and `app='leela'`, a walk id and a step, at most `RUN_METRICS`
    numbers by name, at most `RUN_IMAGES` asset paths `leela/<walk>/<step>/<n>.png` of this walk and step, and plain `secs`, `device`,
    `notebook` and `makes`."""
    if not (isinstance(a, dict) and a.get('kind') == 'run' and a.get('app') == 'leela'): return False
    walk, step = a.get('walk'), a.get('step')
    if not (isinstance(walk, str) and WALK_ID.fullmatch(walk) and type(step) is int and 0 <= step < 10_000): return False
    m = a.get('metrics', {})
    if not (isinstance(m, dict) and len(m) <= RUN_METRICS and all(_line(k, 40) and k and _number(v) for k, v in m.items())): return False
    ims = a.get('images', [])
    if not (isinstance(ims, list) and len(ims) <= RUN_IMAGES and len(set(map(str, ims))) == len(ims)): return False
    for p in ims:
        g = isinstance(p, str) and RUN_IMAGE.fullmatch(p)
        if not (g and g[1] == walk and int(g[2]) == step): return False
    if 'secs' in a and not (_number(a['secs']) and a['secs'] >= 0): return False
    return all(_line(a.get(k, ''), 500) for k in ('device', 'notebook', 'makes'))

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
             ({**_RUN, 'secs': -1}, False),
             ({**_RUN, 'walk': 'w\n'}, False),
             ({**_RUN, 'images': ['leela/ramayana-comic-ab12/7/0.png\n']}, False),
             ({**_RUN, 'metrics': dict(loss=10**400)}, False),
             ({**_RUN, 'metrics': dict(loss=float('inf'))}, False),
             ({**_RUN, 'metrics': dict(ok=True)}, False),
             ({**_RUN, 'secs': 10**400}, False),
             ({**_RUN, 'metrics': {'a\nb': 1}}, False),
             ({**_RUN, 'device': 'mps\nx'}, False),
             ({**_RUN, 'images': [['leela/ramayana-comic-ab12/7/0.png']]}, False),
             ('not an attempt', False)]

# --- the link from a walk step to Leela ---------------------------------------------------------------------------------

LEELA_ROUTE = '/learn'
TOPIC_MAX = 200
VAULT_KEY = re.compile(r'\A[0-9a-f]{8}\Z')                    # the vault key `v` in the link: 8 lower-case hex characters

def vault_key(path) -> str:
    "The key of the vault at `path`: the first 8 hex characters of the sha256 of the resolved path. Two apps on the same vault file get the same key."
    return hashlib.sha256(str(Path(path).expanduser().resolve()).encode()).hexdigest()[:8]

class Handoff(dict):
    "The result of `read_handoff`: a dict whose keys also read as attributes, as fastcore's `AttrDict`."
    def __getattr__(self, k):
        try: return self[k]
        except KeyError: raise AttributeError(k) from None

def handoff(jid:str='', i:int|None=None, topic:str='', v:str='') -> str:
    "The path and query that Leela opens: a walk, a step of it, a topic, or a mix. `v` is the `vault_key` of abhyasa's vault."
    if not (jid or topic): raise ValueError('nothing to open')
    if v and not VAULT_KEY.fullmatch(v): raise ValueError('v is not a vault key: give 8 characters from 0-9 and a-f')
    q = [(k, x) for k, x in (('walk', jid), ('step', i), ('topic', topic), ('v', v)) if x not in ('', None)]
    return f'{LEELA_ROUTE}?{urlencode(q)}'

def read_handoff(query:str) -> Handoff:
    """The `walk`, `step`, `topic` and `v` in `query`, checked. A `ValueError` names the key that is not valid. Other keys are ignored.
    A missing `v` gives '', as a link from abhyasa 0.0.12. A `v` that is not 8 lower-case hex characters is refused."""
    q = {k: x[0] for k, x in parse_qs(query).items()}
    walk, step, topic, v = q.get('walk', ''), q.get('step'), q.get('topic', ''), q.get('v', '')
    if walk and not WALK_ID.fullmatch(walk): raise ValueError('walk is not a walk id')
    if step is not None and not (step.isascii() and step.isdigit()): raise ValueError('step must be a whole number from 0')
    if len(topic) > TOPIC_MAX: raise ValueError(f'topic is more than {TOPIC_MAX} characters')
    if v and not VAULT_KEY.fullmatch(v): raise ValueError('v is not a vault key: give 8 characters from 0-9 and a-f')
    if not (walk or topic): raise ValueError('nothing to open')
    return Handoff(walk=walk, step=None if step is None else int(step), topic=topic, v=v)

# Both test suites run these: each `handoff(**kw)` gives the path, and `read_handoff` of its query gives the same walk, step, topic and v.
HANDOFF_CASES = [(dict(jid='attention-ab12'), '/learn?walk=attention-ab12'),
                 (dict(jid='attention-ab12', i=3), '/learn?walk=attention-ab12&step=3'),
                 (dict(topic='Agents and tools'), '/learn?topic=Agents+and+tools'),
                 (dict(jid='pydantic-ai-docs-9f0c', i=0, topic='Agents'), '/learn?walk=pydantic-ai-docs-9f0c&step=0&topic=Agents'),
                 (dict(jid='attention-ab12', i=3, v='0a1b2c3d'), '/learn?walk=attention-ab12&step=3&v=0a1b2c3d')]

# Queries that `read_handoff` refuses with a `ValueError`: a bad walk or step, nothing to open, and a `v` that is not a vault key.
HANDOFF_BAD = ['walk=../x', 'walk=a-1&step=-1', '', 'walk=a&v=xyz', 'walk=a&v=0A1B2C3D', 'walk=a&v=0a1b2c3d4', 'walk=a&v=0a1b2c3d%0A']
