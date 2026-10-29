"Settings and the route registry the blocks share (lego's `RouteOverrides`)."
import os
from fastcore.basics import AttrDict

__all__ = ['cfg', 'RouteOverrides']

cfg = AttrDict(port=int(os.getenv('ABHYASA_PORT', 5077)), host='127.0.0.1',
               vault=os.getenv('ABHYASA_VAULT') or os.getenv('VISHALAKSHI_VAULT'),
               leela=os.getenv('ABHYASA_LEELA', ''),   # a base URL, only when Leela runs where its address file cannot be seen
               vedicreader=os.getenv('ABHYASA_VEDICREADER', ''))   # the same for vedicreader

class RouteOverrides:
    "Blocks add the four tabs `(label, href, order)` to `nav`, the rows under a tab to `subtabs[tab]`, and Settings sets `gear`; the page header reads them."
    nav = []
    subtabs = {}   # tab label -> [(label, href, order)]
    gear = None
