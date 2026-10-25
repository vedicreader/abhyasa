"Settings and the route registry the blocks share (lego's `RouteOverrides`)."
import os
from fastcore.basics import AttrDict

__all__ = ['cfg', 'RouteOverrides']

cfg = AttrDict(port=int(os.getenv('ABHYASA_PORT', 5077)), host='127.0.0.1',
               vault=os.getenv('ABHYASA_VAULT') or os.getenv('VISHALAKSHI_VAULT'))

class RouteOverrides:
    "Blocks add `(label, href, order)` to `nav` in `connect`; the page header reads it."
    nav = []
