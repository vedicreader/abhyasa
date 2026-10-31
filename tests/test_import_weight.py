"Leela imports the engine for its hints and tutor rules, so importing the engine must not load the model layer or the web app."
import json, subprocess, sys

HEAVY = ('ramabana', 'rishi', 'mdhtml', 'nh3', 'ipywidgets')

def test_engine_import_is_light():
    "Importing store, model, method, tutor and talk loads no model layer, no renderer and no web app."
    code = ("import sys, json, abhyasa.store, abhyasa.model, abhyasa.method, abhyasa.tutor, abhyasa.talk; "
            "print(json.dumps(sorted(sys.modules)))")
    mods = json.loads(subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, check=True).stdout)
    bad = [m for m in mods if m.split('.')[0] in HEAVY or m.startswith(('abhyasa.app', 'abhyasa.blocks', 'abhyasa.core'))]
    assert not bad, bad


def test_nb_import_is_light():
    "Importing the notebook tutor loads no model layer: `route_ask` is imported, but ramabana loads on the first call."
    code = "import sys, json, abhyasa.nb; print(json.dumps(sorted(sys.modules)))"
    mods = json.loads(subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, check=True).stdout)
    bad = [m for m in mods if m.split('.')[0] in ('ramabana', 'rishi')]
    assert not bad, bad


def test_stagekit_imports_only_the_standard_library():
    "Leela imports room_spec and is_local with no abhyasa web code and no settings."
    code = "import abhyasa.stagekit, sys; assert 'fasthtml' not in sys.modules and 'abhyasa.settings' not in sys.modules and 'abhyasa.core' not in sys.modules"
    subprocess.run([sys.executable, '-I', '-c', code], check=True)

def test_core_names_are_the_stagekit_names():
    "The names in `core` are the same objects as in `stagekit`."
    import abhyasa.stagekit as k, abhyasa.core as c, abhyasa.core.pane as p
    assert c.room_spec is k.room_spec and p.is_local is k.is_local


def test_contract_imports_only_the_standard_library():
    "Leela imports the notebook spec and run checks with no web code, no settings, no model layer and no tutor: each new module is in the standard library."
    code = ("import sys, json; before = set(sys.modules); import abhyasa.contract; "
            "print(json.dumps(sorted(m for m in set(sys.modules) - before if m.split('.')[0] not in sys.stdlib_module_names and m not in ('abhyasa', 'abhyasa.contract'))))")
    out = subprocess.run([sys.executable, '-I', '-c', code], capture_output=True, text=True, check=True).stdout
    assert json.loads(out) == []

def test_walk_names_are_the_contract_names():
    "The old imports from `walk` and `journey` give the same objects as `contract`."
    import abhyasa.contract as k, abhyasa.walk as w, abhyasa.journey as j
    assert all(getattr(w, x) is getattr(k, x) for x in ('PKG', 'validate_nb_spec', 'NB_SPEC_CASES', 'run_ok', 'RUN_CASES'))
    assert j.WALK_ID is k.WALK_ID
    assert all(getattr(j, x) is getattr(k, x) for x in ('LEELA_ROUTE', 'TOPIC_MAX', 'vault_key', 'handoff', 'read_handoff', 'HANDOFF_CASES'))
