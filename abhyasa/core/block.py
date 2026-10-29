"What a block may touch, and the ordered wiring that applies it (after leela's `core/block.py`)."
from fastcore.basics import store_attr

__all__ = ['CAPABILITIES', 'Ctx', 'Block', 'connect_all', 'block_name', 'block_caps']

#: the services the app hands to blocks
CAPABILITIES = ('learning', 'tutor', 'ask', 'transcribe', 'speech', 'pool', 'sessions', 'sources', 'research')

def _undeclared(ctx, name): return f"block {ctx.name!r} used capability {name!r} without declaring it; add it to the block's `CAPS`"

class Ctx:
    "The capability surface handed to one block's `connect`."
    def __init__(self, name='', caps=None, **svc):
        if (bad := sorted(set(svc) - set(CAPABILITIES))): raise TypeError(f'unknown capabilities: {bad}')
        self.name, self.caps = name, tuple(CAPABILITIES if caps is None else caps)
        for c in self.caps:
            if c in svc: setattr(self, c, svc[c])
    def __getattr__(self, name):
        if name in CAPABILITIES: raise AttributeError(_undeclared(self, name))
        raise AttributeError(f'Ctx has no attribute {name!r}')
    def __repr__(self): return f"Ctx({self.name!r}, caps={','.join(self.caps)})"

class Block:
    "One connected block, as recorded by `connect_all`."
    __slots__ = ('name', 'module', 'caps', 'order')
    def __init__(self, name, module, caps, order): store_attr()
    def __repr__(self): return f'Block({self.name!r}, order={self.order}, caps={list(self.caps)})'

def block_name(m):
    "`abhyasa.blocks.graph` -> `graph`."
    return getattr(m, 'NAME', None) or m.__name__.split('.')[-1]

def block_caps(m):
    "A block's declared capabilities; it must declare them."
    caps = getattr(m, 'CAPS', None)
    if caps is None: raise ValueError(f'{block_name(m)}: no CAPS')
    if (bad := sorted(set(caps) - set(CAPABILITIES))): raise ValueError(f'{block_name(m)}: unknown capabilities {bad}')
    return tuple(caps)

def connect_all(app, blocks, **svc):
    "Connect `blocks` to `app` in order, each with its own narrowed `Ctx`; returns `Block` receipts."
    out = []
    for i, m in enumerate(blocks):
        name, caps = block_name(m), block_caps(m)
        m.connect(app, Ctx(name, caps, **svc))
        out.append(Block(name, m, caps, i))
    return out
