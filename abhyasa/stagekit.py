"The parts of the stage that Leela uses: this module imports only the standard library."
import re
from copy import deepcopy

__all__ = ['room_spec', 'is_local']

def room_spec(spec):
    "A copy of a demo spec for the audience window: no gate has its `answer`, so the HTML has no answer before the presenter shows it."
    def strip(x):
        if isinstance(x, list): return [strip(v) for v in x]
        if not isinstance(x, dict): return x
        return {k: strip(v) for k, v in x.items() if not (k == 'answer' and x.get('type') == 'gate')}
    return strip(deepcopy(spec))

_BAD = re.compile(r'[\x00-\x1f\x7f\\]')   # a control character or a backslash: a browser can make either into a way out of the app

def is_local(url) -> bool:
    "Whether `url` is a path in this app: one `/` at the start, no scheme, no host, no backslash and no control character."
    return isinstance(url, str) and url.startswith('/') and not url.startswith('//') and not _BAD.search(url)
