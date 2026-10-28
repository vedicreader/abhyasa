"Every keyboard shortcut on one page, from the table in `core/keys.py`; ⌥F or ? opens it from any page."
from fasthtml.common import *
from abhyasa.core import Page, hook
from abhyasa.core.keys import KEYS, MENU
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ()

def connect(app, ctx):
    def page():
        groups = {}
        for r in [*KEYS, *MENU]: groups.setdefault(r[0], []).append(r)
        return Page('Keyboard shortcuts', ui.css(), H1('Keyboard shortcuts'),
                    P('All keys are for the left hand. ⌥ is the Option key. Sanketa shows the same list when abhyasa is in front.', cls='mute'),
                    *[ui.Group(k, v) for k, v in groups.items()], crumbs=[('Today', '/')])

    @hook('today_end')
    def line(subject=None): return A('Keyboard shortcuts', href=Routes.base), ' ', Kbd('⌥F')

    @hook('page_extra')
    def key():   # ⌥F, or ? outside a text box, opens the page from any page
        return A(href=Routes.base, id='keys-key', tabindex='-1', aria_hidden='true', style='position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)'), Script("""abhyasaKeys.KeyF = '#keys-key';
if (!window.abhyasaHelp) { window.abhyasaHelp = true; document.addEventListener('keydown', e => {
  const t = e.target; if (e.key !== '?' || e.metaKey || e.ctrlKey || e.altKey || (t.matches && t.matches('textarea, input, select, [contenteditable]'))) return;
  e.preventDefault(); location.href = '/keys'; }); }""")

    app.get(Routes.base)(page)
