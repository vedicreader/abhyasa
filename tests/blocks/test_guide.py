"The guide block: the Explain button and the box on each page, the figure labels, the three tiers, and the explainer video."
import json, pytest

PNG = b'\x89PNG\r\n\x1a\n' + b'\0' * 64
LABELS = dict(labels=[dict(text='a', box=[90, 400, 160, 500]), dict(text='b', box=[480, 880, 540, 960])])

def test_each_page_has_the_explain_button(mk):
    t = mk().get('/').text
    assert 'id="guide-go"' in t and '>Explain<' in t and 'id="guide-box"' in t and 'guide.js' in t
    assert 'aria-label="What do you not understand?"' in t

def test_figure_labels_are_found_once(mk, fake):
    fake.rules['You find the text labels'] = LABELS
    cl = mk()
    r = cl.post('/guide/figure?alt=A+right+triangle', content=PNG)
    assert r.json()['labels'] == {'a': [90, 400, 160, 500], 'b': [480, 880, 540, 960]}
    n = sum('You find the text labels' in sp for _, sp in fake.calls)
    assert cl.post('/guide/figure', content=PNG).json()['labels']['b'] == [480, 880, 540, 960]
    assert sum('You find the text labels' in sp for _, sp in fake.calls) == n == 1

def test_figure_route_takes_only_images(mk):
    assert mk().post('/guide/figure', content=b'<svg onload=alert(1)>').status_code == 415

GUIDE_JS = __import__('pathlib').Path(__file__).parents[2]/'abhyasa/blocks/guide/guide.js'

def tex_parts(tex):
    import shutil, subprocess
    if not shutil.which('node'): pytest.skip('node is not installed')
    code = f"const g = require({json.dumps(str(GUIDE_JS))}); console.log(JSON.stringify(g.texParts({json.dumps(tex)}, 1)))"
    return json.loads(subprocess.run(['node', '-e', code], capture_output=True, text=True, check=True).stdout)

def test_formula_parts_of_ddpm():
    "The page marks the parts of the DDPM formula, so the board can point at alpha bar, its root and the noise share."
    marked, parts = tex_parts(r'q(\mathbf{x}_t\mid\mathbf{x}_0)=\mathcal{N}(\mathbf{x}_t;\sqrt{\bar\alpha_t}\mathbf{x}_0,(1-\bar\alpha_t)\mathbf{I})')
    texs = [t for t, _ in parts]
    for t in (r'\bar\alpha_t', r'\sqrt{\bar\alpha_t}', r'\mathbf{x}_0', r'(1-\bar\alpha_t)', r'\mathbf{I}'): assert t in texs, t
    assert marked.count(r'\htmlId{') == len(parts) and len({i for _, i in parts}) == len(parts)
    assert r'\htmlId{g-1-' in marked and r'\mid' in marked and r'\htmlId{g-1-0}{q}' in marked

def test_formula_parts_keep_accents_whole():
    "An accent and its symbol are one part: no id inside the bar."
    marked, parts = tex_parts(r'\hat{y} = \frac{a}{b}')
    assert [t for t, _ in parts][:1] == [r'\hat{y}'] and r'\hat{\htmlId' not in marked and r'\frac{\htmlId' in marked
