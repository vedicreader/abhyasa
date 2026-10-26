"The shortcuts table: the page, the ⌥ keys that the js binds, and the Sanketa pack and its writer."
import re
from pathlib import Path
from abhyasa.core.keys import KEYS, MENU, sanketa_pack, write_sanketa_pack, _MARK

ROOT = Path(__file__).parents[1]/'abhyasa'

def bound():
    "The ⌥ letters and digits that the js binds: `KeyX:` in abhyasaKeys tables, `abhyasaKeys.KeyX =`, and `e.code !== 'KeyX'` checks."
    js = '\n'.join(p.read_text() for p in [*ROOT.glob('core/*.js'), *ROOT.glob('blocks/*/*.js'), *ROOT.glob('blocks/*/app.py')])
    return set(re.findall(r"\b(?:Key|Digit)([A-Z0-9])\b(?=\s*[:=']|')", js))

def listed():
    "The ⌥ letters and digits in the table."
    out = set()
    for _, k, _ in KEYS:
        for m in re.finditer(r'⌥([A-Z0-9])(?:–⌥([0-9]))?', k):
            a, b = m.groups()
            out |= {str(i) for i in range(int(a), int(b) + 1)} if b else {a}
    return out

def test_table_matches_the_js():
    assert listed() == bound(), f'only in the table: {listed() - bound()}; only in the js: {bound() - listed()}'

def test_page_lists_every_key(mk):
    t = mk().get('/keys').text
    for g, k, a in [*KEYS, *MENU]: assert a.replace("'", '&#x27;') in t or a in t, a
    assert "abhyasaKeys.KeyF = '#keys-key'" in mk().get('/').text

def test_pack_has_each_key_once_per_group():
    p = sanketa_pack()
    assert p.startswith(_MARK) and 'apps = ["dev.vedicreader.abhyasa"]' in p
    assert p.count('[[keys]]') == len(KEYS) and 'Mac app' not in p   # Sanketa reads the menu keys by itself
    assert len({(g, k) for g, k, _ in KEYS}) == len(KEYS)

def test_writer_keeps_your_own_pack(tmp_path):
    assert write_sanketa_pack(tmp_path).read_text() == sanketa_pack()
    (tmp_path/'abhyasa.toml').write_text('id = "abhyasa"\nname = "mine"\n')
    assert write_sanketa_pack(tmp_path) is None and 'mine' in (tmp_path/'abhyasa.toml').read_text()
