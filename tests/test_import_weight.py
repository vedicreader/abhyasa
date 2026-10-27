"Leela imports the engine for its hints and tutor rules, so importing the engine must not load the model layer or the web app."
import json, subprocess, sys

HEAVY = ('ramabana', 'rishi', 'mdhtml', 'nh3', 'ipywidgets')

def test_engine_import_is_light():
    "Importing store, model, method and tutor loads no model layer, no renderer and no web app."
    code = ("import sys, json, abhyasa.store, abhyasa.model, abhyasa.method, abhyasa.tutor; "
            "print(json.dumps(sorted(sys.modules)))")
    mods = json.loads(subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, check=True).stdout)
    bad = [m for m in mods if m.split('.')[0] in HEAVY or m.startswith(('abhyasa.app', 'abhyasa.blocks', 'abhyasa.core'))]
    assert not bad, bad
