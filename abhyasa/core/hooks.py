"Blocks add to each other's pages without importing each other (vedicreader's `vr/core/hooks.py`)."
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
