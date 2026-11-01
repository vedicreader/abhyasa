"The old engine module names, kept for one or two releases after 0.0.16: each one is its new module, so an import and a monkeypatch reach the same code."
import sys, types
from importlib import import_module

def _where(new, name:str) -> tuple:
    "The module and the name that the old name `name` means: `mod.name` is a name in another new module."
    if '.' not in name: return new, name
    mod, name = name.rsplit('.', 1)
    return import_module(f'abhyasa.{mod}'), name

class OldView(types.ModuleType):
    "A new module under an old name, for an old module that had a name which means another thing in the new module: it reads and writes the new module."
    def __init__(self, name, new, own):
        super().__init__(name, new.__doc__)
        vars(self).update(_new=new, _own=own)
    def __getattr__(self, k):
        m, n = _where(vars(self)['_new'], vars(self)['_own'].get(k, k))
        return getattr(m, n)
    def __setattr__(self, k, v): setattr(*_where(self._new, self._own.get(k, k)), v)
    def __delattr__(self, k): delattr(*_where(self._new, self._own.get(k, k)))
    def __dir__(self): return sorted(set(dir(self._new)) | set(self._own))

def alias(name:str, new:str, **own):
    "Make the old module `name` the new module `abhyasa.<new>`. `own` maps an old name to its new name (`mod.name` for another new module), when the two differ."
    m = import_module(f'abhyasa.{new}')
    sys.modules[name] = OldView(name, m, own) if own else m
