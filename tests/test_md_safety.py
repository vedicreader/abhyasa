"Vault text is not trusted: abhyasa's markdown render must show raw HTML as text and run nothing."
from pathlib import Path
import pytest
pw = pytest.importorskip('playwright.sync_api')
core = Path(__file__).parents[1]/'abhyasa'/'core'

MD = '\n\n'.join(['# Saved page', 'Some **bold** text and a table:', '| a | b |\n|---|---|\n| 1 | 2 |',
                  '<iframe src="https://www.youtube.com/embed/x?autoplay=1"></iframe>',
                  '<video autoplay src="https://example.org/v.mp4"></video>',
                  'inline <img src=x onerror="window.pwned=1"> image',
                  '[bad link](javascript:window.pwned=2) and [good link](https://example.org)'])

def test_markdown_shows_raw_html_as_text_and_runs_nothing(tmp_path):
    (tmp_path/'t.html').write_text(f'''<!doctype html><meta charset=utf-8><script src="{(core/'vendor/marked.min.js').as_uri()}"></script>
<script src="{(core/'core.js').as_uri()}"></script><div class="md" id="m">{MD.replace('&', '&amp;').replace('<', '&lt;')}</div>''')
    with pw.sync_playwright() as p:
        try: br = p.chromium.launch(headless=True)   # Playwright's own Chromium, never the user's Chrome
        except Exception as e: pytest.skip(f'no Chromium for Playwright: {e}')
        try:
            pg = br.new_page(); pg.goto((tmp_path/'t.html').as_uri()); pg.wait_for_timeout(300)
            r = pg.evaluate('''() => { const m = document.getElementById('m');
              return {media: m.querySelectorAll('iframe, video, audio, object, embed, script').length,
                      onerror: m.querySelectorAll('[onerror]').length,
                      jslinks: [...m.querySelectorAll('a')].filter(a => /^javascript/i.test(a.getAttribute('href') || '')).length,
                      goodlink: !!m.querySelector('a[href="https://example.org"]'), table: !!m.querySelector('table'), pwned: window.pwned || 0} }''')
        finally: br.close()
    assert r == dict(media=0, onerror=0, jslinks=0, goodlink=True, table=True, pwned=0)
