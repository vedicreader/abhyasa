"The blocks, in connect order: providers first, the home page last."
from importlib import import_module

__all__ = ['NAMES', 'blocks']

NAMES = 'voice profile strengths course history jobs concepts graph search add sources vault settings keys session demo walk detour talk guide today'.split()

def blocks(names=NAMES): return [import_module(f'{__name__}.{n}') for n in names]
