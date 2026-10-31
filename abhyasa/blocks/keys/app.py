"Every keyboard shortcut on one page, from the table in `core/keys.py`; ⌥F or ? opens it from any page. The Keys panel shows the most useful keys of each page."
from fasthtml.common import *
from abhyasa.core import Page, hook, page_req
from abhyasa.core.keys import KEYS, MENU
from abhyasa.settings import val, set_val
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ()
SHOW = f"fetch('{Routes.float}', {{method: 'POST', body: new URLSearchParams({{on: '1'}})}}).then(() => location.reload())"

def connect(app, ctx):
    def page():
        groups = {}
        for r in [*KEYS, *MENU]: groups.setdefault(r[0], []).append(r)
        back = '' if val('look.keys_float') else P('You hid the Keys button. ', Button('Show the Keys button', type='button', cls='small quiet', onclick=SHOW), cls='mute')
        return Page('Keyboard shortcuts', ui.css(), H1('Keyboard shortcuts'),
                    P('All keys are for the left hand. ⌥ is the Option key. Sanketa shows the same list when abhyasa is in front.', cls='mute'),
                    back, *[ui.Group(k, v) for k, v in groups.items()], crumbs=[('Today', '/')])

    def float_(on:str=''):
        "The setting `look.keys_float`: Hide this in the panel sets it off, and the keys page sets it on again."
        set_val('look.keys_float', on in ('1', 'true', 'on'))
        return Response(status_code=204)

    @hook('today_end')
    def line(subject=None): return A('Keyboard shortcuts', href=Routes.base), ' ', Kbd('⌥F')

    @hook('page_extra')
    def key():   # ⌥F, or ? outside a text box, opens the page from any page
        return A(href=Routes.base, id='keys-key', tabindex='-1', aria_hidden='true', style='position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)'), Script("""abhyasaKeys.KeyF = '#keys-key';
if (!window.abhyasaHelp) { window.abhyasaHelp = true; document.addEventListener('keydown', e => {
  const t = e.target; if (e.key !== '?' || e.metaKey || e.ctrlKey || e.altKey || (t.matches && t.matches('textarea, input, select, [contenteditable]'))) return;
  e.preventDefault(); location.href = '/keys'; }); }""")

    @hook('page_extra')
    def keys_float():
        "The Keys pill and its panel, on each page but a page in the side pane, while the setting `look.keys_float` is on."
        req = page_req()
        if not val('look.keys_float') or (req is not None and req.query_params.get('pane') == '1'): return None
        return ui.Float(req.url.path if req is not None else '/', Routes.base, Routes.float)

    app.get(Routes.base)(page)
    app.post(Routes.float)(float_)
