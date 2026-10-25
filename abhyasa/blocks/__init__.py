"The blocks, in connect order: providers first, the home page last."
from importlib import import_module

__all__ = ['NAMES', 'blocks']

NAMES = 'voice concepts graph search add session today'.split()

def blocks(names=NAMES): return [import_module(f'{__name__}.{n}') for n in names]
