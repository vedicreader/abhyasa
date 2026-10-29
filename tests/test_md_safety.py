"Learner, model and vault text are not trusted: `md_html` renders markdown with maths and code, and keeps no raw HTML that can run."
import re
from abhyasa.core import md_html, clean_html, Md
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

def test_htmx_ids_targets_and_svg_are_removed():
    h = md_html('<div id="send" hx-get="/s/start" hx-trigger="load" data-hx-post="/x">a</div>\n\n'
                '<a href="https://example.org" target="_top" name="chat">b</a>\n\n<svg onload="alert(1)"><circle r="9"/></svg>\n\nc').lower()
    for bad in ('id=', 'hx-', '/s/start', 'target=', 'name=', '<svg', '<circle'): assert bad not in h, bad   # mdhtml shows the svg as text
    assert re.search(r'<div>\s*(<p>)?a(</p>)?\s*</div>', h) and 'href="https://example.org"' in h   # newer mdhtml wraps the text in a <p>
    assert clean_html('<p><svg onload="alert(1)"><circle r="9"/></svg>c</p>') == '<p>c</p>'   # svg inline in a paragraph too

def test_relative_urls_are_removed():
    h = md_html('![](/s/start?subject=x) [x](//evil.com) [y](/s/1) [z](#send) <a href=" /s/start">w</a>')
    assert 'src=' not in h and 'href=' not in h and '<img alt="">' in h

def test_images_are_inline_data_only():
    dot = 'data:image/png;base64,iVBORw0KGgo='
    h = md_html(f'![dot]({dot}) ![far](https://tracker.example/p.png) ![svg](data:image/svg+xml;base64,PHN2Zz4=) [d](data:text/html;base64,PHNjcmlwdD4=)')
    assert f'<img src="{dot}" alt="dot">' in h and '<img alt="far">' in h and '<img alt="svg">' in h
    assert 'tracker' not in h and 'svg+xml' not in h and 'text/html' not in h

def test_md_wraps_the_safe_html():
    x = to_xml(Md('$x$ <script>1</script>', cls='said'))
    assert 'class="md said"' in x and '<span class="math inline">x</span>' in x and '<script' not in x
