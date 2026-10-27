"Learner, model and vault text are not trusted: `md_html` renders markdown with maths and code, and keeps no raw HTML that can run."
from abhyasa.core import md_html, Md
from fasthtml.common import to_xml

def test_dollar_math_becomes_math_carriers():
    h = md_html(r'So $z = 2\cdot4 + 3\cdot5 + 1 = 24$.' + '\n\n$$\na^2 + b^2\n$$')
    assert r'<span class="math inline">z = 2\cdot4 + 3\cdot5 + 1 = 24</span>' in h
    assert '<div class="math display">a^2 + b^2</div>' in h

def test_prices_are_not_math():
    assert 'math' not in md_html('It costs $5 and $6 in all.')

def test_code_fence_keeps_its_lines():
    h = md_html('Read this code:\n\n```python\nw = [2, 3]\nfor i in range(2):\n    z = z + w[i]\n```\n\nWhat is z?')
    assert '<pre><code class="language-python">w = [2, 3]\nfor i in range(2):\n    z = z + w[i]\n</code></pre>' in h
    assert '<p>What is z?</p>' in h

MD = '\n\n'.join(['# Saved page', 'Some **bold** text and a table:', '| a | b |\n|---|---|\n| 1 | 2 |',
                  '<iframe src="https://www.youtube.com/embed/x?autoplay=1"></iframe>',
                  '<video autoplay src="https://example.org/v.mp4"></video>', '<script>window.pwned=1</script>',
                  'inline <img src=x onerror="window.pwned=1"> image', '<div class="md opt go" style="color:red" onclick="x()">hi</div>',
                  '[bad link](javascript:window.pwned=2) and [good link](https://example.org)'])

def test_raw_html_cannot_run():
    h = md_html(MD).lower()
    for bad in ('<iframe', '<video', '<script', 'onerror', 'onclick', 'style=', 'javascript:', 'class="md', 'go"'): assert bad not in h, bad
    assert '<table>' in h and '<strong>bold</strong>' in h and 'href="https://example.org"' in h

def test_md_wraps_the_safe_html():
    x = to_xml(Md('$x$ <script>1</script>', cls='said'))
    assert 'class="md said"' in x and '<span class="math inline">x</span>' in x and '<script' not in x
