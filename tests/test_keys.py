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
    "The ⌥ letters and digits in the table, and the plain letters of the graph, the talk and the guide board, which their js checks by `e.code` too."
    out = {k for g, k, _ in KEYS if g in ('Graph', 'Talk', 'Talk plan', 'Guide') and re.fullmatch('[A-Z]', k)}
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

def test_tab_keys():
    rows = {(g, k): a for g, k, a in KEYS}
    assert rows[('Everywhere', '⌥Q')] == 'Go to Learn' and rows[('Everywhere', '⌥R')] == 'Go to Library'
    assert rows[('Everywhere', '⌥G')] == 'Go to You' and rows[('Everywhere', '⌥1–⌥3')] == 'Pick a sub-tab'
    assert not any('Settings' in a for _, _, a in KEYS)
    talk = (ROOT/'blocks/talk/talk.js').read_text()
    assert all(f"'Key{k}'" in talk for k in 'QR') and 'Digit1' in talk   # the presenter window ignores them

def pack_rows():
    "The (keys, action, group) of each [[keys]] table of the pack, read back as TOML."
    import tomllib
    return [(r['keys'], r['action'], r['group']) for r in tomllib.loads(sanketa_pack())['keys']]

def test_pack_actions_are_short():
    "Sanketa warns about an action of more than six words: each action of the pack has six or fewer, and the page keeps the long text."
    long = [(k, a) for k, a, _ in pack_rows() if len(a.split()) > 6]
    assert not long, long
    from abhyasa.core.keys import SHORT
    assert set(SHORT) <= {a for _, _, a in KEYS}, 'a short label for an action that is not in the table'

def test_pack_keys_once_per_group_and_in_key_style():
    "The lint error rule: no two keys with the same keys text in one group. Plain letters are lower case, and choices have ` / `."
    rows = pack_rows()
    assert len({(k, g) for k, _, g in rows}) == len(rows)
    ks = {(g, k) for k, _, g in rows}
    assert ('Graph', 's') in ks and ('Everywhere', '⌥F / ?') in ks and ('Walk path', '⇧W / ⇧S') in ks and ('Everywhere', '⌥⇧F') in ks
    assert ('Everywhere', '⌥D') in ks and ('Guide', '⌃⌥⇧⌘E') in ks
