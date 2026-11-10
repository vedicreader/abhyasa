"The unseen dots of the graph show in every theme, light and dark: their fill and ring keep a contrast with the page, from the numbers in `graph.js` and `themes.css`."
import colorsys, re
from pathlib import Path

ROOT = Path(__file__).parent.parent/'abhyasa'
JS, CSS = (ROOT/'blocks/graph/graph.js').read_text(), (ROOT/'core/themes.css').read_text()

def rgb(h, s, l): return colorsys.hls_to_rgb(h / 360, l / 100, s / 100)

def lum(c):
    "The relative luminance of an sRGB colour `c` (three floats from 0 to 1)."
    f = lambda x: x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4
    r, g, b = map(f, c); return .2126 * r + .7152 * g + .0722 * b

def contrast(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True); return (x + .05) / (y + .05)

def themes():
    "`{(theme, mode): {name: rgb}}` from the `light-dark(hsl(), hsl())` colours of `themes.css`."
    out = {}
    for m in re.finditer(r'(?::root, )?\[data-theme=(\w+)\]\s*\{(.*?)\}', CSS, re.S):
        vals = {k: re.search(r'light-dark\(hsl\(([^)]*)\),\s*hsl\(([^)]*)\)\)', m.group(2)[m.group(2).index(f'--{k}:'):]) for k in ('bg', 'fg', 'mute') if f'--{k}:' in m.group(2)}
        for i, mode in enumerate(('light', 'dark')):
            out[m.group(1), mode] = {k: rgb(*[float(x.strip('%')) for x in v.group(i + 1).split()]) for k, v in vals.items()}
    return out

def test_the_graph_reads_the_theme_colours_of_every_theme():
    "The parse finds six themes in two modes, each with a page, text and quiet colour."
    t = themes()
    assert len(t) == 12 and all(set(v) == {'bg', 'fg', 'mute'} for v in t.values())

def test_an_unseen_dot_and_its_ring_show_against_the_page_in_every_theme():
    "The fill is a mix of the page and text colours (`UNSEEN`); it keeps a contrast of 1.6 with the page, and the ring (the quiet colour) 3, in each theme and mode."
    mix = float(re.search(r'const UNSEEN = ([\d.]+);', JS).group(1))
    for k, c in themes().items():
        fill = tuple(a + (b - a) * mix for a, b in zip(c['bg'], c['fg']))
        assert contrast(fill, c['bg']) >= 1.6, (k, contrast(fill, c['bg']))
        assert contrast(c['mute'], c['bg']) >= 3, (k, contrast(c['mute'], c['bg']))

def test_the_old_fill_was_too_faint_in_the_dark_themes():
    "The raised colour (93% page, 7% text) that the dot used had a contrast under 1.2 with the page in the dark themes: the number that this fix moves."
    c = themes()['ink', 'dark']
    assert contrast(tuple(a * .93 + b * .07 for a, b in zip(c['bg'], c['fg'])), c['bg']) < 1.2

def test_the_graph_draws_unseen_dots_with_the_unseen_colour_and_a_quiet_ring():
    "No node, ring or legend swatch of the graph takes the raised or the rule colour for an unseen dot."
    assert 'C.raised' not in JS and 'hollow(n) ? C.rule' not in JS and 'C.unseen' in JS
