"The code of a step on the page: a placeholder that a host such as Leela turns into a cell that runs, and a plain listing everywhere else."
import base64
from fasthtml.common import *
from abhyasa.learner import is_hosted

__all__ = ['LiveCell', 'LIVE_NOTE']

LIVE_NOTE = 'This code runs on your computer.'

def LiveCell(code, cid:str, walk:str='', step:int=None, check_url:str='', hosted:bool=None):
    """The code `code` of a step (`path.check_code`) as the page draws it. It always holds the code in a `pre`, so a page with no script, and the standalone app,
    show it. A hosted page (`is_hosted`) also marks the place for the host to make a cell that runs: the code in `data-src-b64`, the names to watch, and,
    when the step has an `expect`, the `check_url` that grades a run."""
    pre = Pre(Code(code['src'], cls='language-python'), cls='live-src')
    if not (is_hosted() if hosted is None else hosted): return Div(Span('Code', cls='lbl'), pre, cls='live-code')
    a = dict(data_lang='python', data_src_b64=base64.b64encode(code['src'].encode()).decode(), data_watch=','.join(code.get('watch') or ()), data_id=cid,
             data_ro=str(code.get('ro') or 0), data_walk=walk, data_step='' if step is None else str(step))
    if check_url and code.get('expect'): a['data_check_url'] = check_url
    return Div(Span('Code', cls='lbl'), pre, cls='lee-livecell', **a)
