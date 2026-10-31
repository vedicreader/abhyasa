def old_session(lr, sid, text):
    "A session document as abhyasa filed it before 0.0.16: the vault keeps it, and nothing files new ones."
    return lr.vault.shelf('ramabana').add(text, title=f'Session {sid}', source=f'ramabana://session/{sid}', kind='session',
                                          meta=dict(session=sid, turns=1, first_at=1., last_at=1., model='m', roots=[]))['doc_id']

def test_viewer_shows_an_old_session_and_its_resume_command(mk, lr):
    doc_id = old_session(lr, 'agent_1', '## why does rrf use ranks\n\nScores differ in scale.')
    t = mk(['vault']).get(f'/v/ramabana/{doc_id}').text
    assert 'why does rrf use ranks' in t and 'Scores differ in scale' in t
    assert 'ramabana --resume agent_1' in t and 'Only find its ideas' in t

def test_old_memory_and_agent_notebook_open_and_search(mk, lr):
    "A memory document and a leela agent notebook that abhyasa filed before 0.0.16 open in the viewer, and search finds them."
    from abhyasa.ground import VaultSource
    m = lr.vault.shelf('ramabana').add('- Use RRF for hybrid search.', title='Memory: abc', source='ramabana://memory/abc', kind='memory', meta=dict(ref='memory/abc'))['doc_id']
    n = lr.vault.shelf('notebooks').add('# Sandhi notes\n\nThe sandhi of a and i gives e.', title='_leela_agent_sessions/a', source='/tmp/proj/_leela_agent_sessions/a.ipynb',
                                         kind='notebook', meta=dict(path='/tmp/proj/_leela_agent_sessions/a.ipynb', agent=True, mtime=1.))['doc_id']
    cl = mk(['vault'])
    assert 'Use RRF for hybrid search' in cl.get(f'/v/ramabana/{m}').text and 'The sandhi of a and i gives e' in cl.get(f'/v/notebooks/{n}').text
    srcs = {p.src for q in ('hybrid search RRF', 'sandhi of a and i') for p in VaultSource(lr).search(q)}
    assert {'vault:ramabana', 'vault:notebooks'} <= srcs, srcs

def test_viewer_learns_concepts_from_a_document(mk, lr):
    doc_id = old_session(lr, 'agent_2', '## what is a rank\n\nA position in a list.')
    t = mk(['vault']).post(f'/v/ramabana/{doc_id}/learn').text
    assert '/c/rank' in t
    assert lr.concept('rank').provenance[0]['src'] == 'vault:ramabana'

def test_viewer_refuses_unknown_or_unsafe(mk):
    cl = mk(['vault'])
    assert 'No such document' in cl.get('/v/ramabana/nope').text
    assert 'No such document' in cl.get('/v/bad;name/x').text

PNG = b'\x89PNG\r\n\x1a\n'

def rasi(lr):
    "A PDF document with four image links: one in its assets folder, one not there, one of another document, one not an image."
    text = ('Aries is a fire sign.\n\n![Image 1 from page 2](images/page2_1.png)\n\n![Image 2 from page 2](images/page2_2.png)\n\n'
            '![Other](../attention/images/fig2.png)\n\n![Notes](images/notes.txt)')
    d = lr.vault.add([(2, text)], 'Rasi Characteristics', source='/tmp/vr/Rasi-Characteristics.pdf', kind='pdf')['doc_id']
    for f, b in (('Rasi-Characteristics/images/page2_1.png', PNG), ('Rasi-Characteristics/images/notes.txt', b'x'), ('attention/images/fig2.png', PNG)):
        p = lr.vault.assets()/f; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b)
    return d

def test_document_shows_its_images(mk, lr):
    "An image link that is in the assets folder of the document is an image from the app; the others are left out, with no empty image."
    import re
    d = rasi(lr)
    t = mk(['vault']).get(f'/v/store/{d}').text
    assert re.findall(r'<img [^>]*>', t) == [f'<img src="/v/store/{d}/img?f=images/page2_1.png" alt="Image 1 from page 2">']
    assert 'Image 2 from page 2' not in t and 'Other' not in t and 'Aries is a fire sign' in t

def test_document_image_route_is_safe(mk, lr, monkeypatch):
    "The image route sends only an image of that document, from its assets folder, under the size cap."
    d = rasi(lr)
    cl = mk(['vault'])
    r = cl.get(f'/v/store/{d}/img?f=images/page2_1.png')
    assert r.status_code == 200 and r.content == PNG and r.headers['content-type'] == 'image/png' and r.headers['x-content-type-options'] == 'nosniff'
    for bad in ('images/page2_2.png', 'images/notes.txt', '../attention/images/fig2.png', '..%2Fattention%2Fimages%2Ffig2.png',
                '%2Fetc%2Fhosts', '../../../../etc/hosts', 'images/../../attention/images/fig2.png'):
        assert cl.get(f'/v/store/{d}/img?f={bad}').status_code == 404, bad
    assert cl.get(f'/v/store/{d}/img').status_code == 404
    assert cl.get('/v/store/nope/img?f=images/page2_1.png').status_code == 404
    assert cl.get(f'/v/bad;name/{d}/img?f=images/page2_1.png').status_code == 404
    monkeypatch.setattr('abhyasa.blocks.vault.app.IMG_MAX', 4)
    assert cl.get(f'/v/store/{d}/img?f=images/page2_1.png').status_code == 404   # larger than the cap

def test_image_syntax_in_code_stays_as_text(mk, lr):
    "Image syntax in a code fence or in inline code is code: the page shows it as text and makes no image of it."
    text = ('Fig:\n\n![Image 1 from page 2](images/page2_1.png)\n\n```\n![In a fence](images/page2_1.png)\n```\n\n'
            'Write `![inline](images/page2_1.png)` for an image.')
    d = lr.vault.add([(2, text)], 'Code notes', source='/tmp/vr/Code-notes.pdf', kind='pdf')['doc_id']
    p = lr.vault.assets('Code-notes')/'images'/'page2_1.png'; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(PNG)
    t = mk(['vault']).get(f'/v/store/{d}').text
    assert t.count('<img ') == 1 and '![In a fence](images/page2_1.png)' in t and '![inline](images/page2_1.png)' in t

def test_viewer_refuses_the_history_of_an_editor(mk, lr):
    "A history keeps old text that you took out of a talk or a walk: the vault page never shows it, as for an open question."
    import abhyasa.edit
    lr.add_edit('talk', 't1', 'Removed “Softmax”.', 'you', [dict(id='s1', title='A secret slide')])
    d = lr.v.t.docs(where="kind='edits'")[0]['id']
    t = mk(['vault']).get(f'/v/learning/{d}').text
    assert 'No such document' in t and 'A secret slide' not in t

def test_a_long_word_in_a_document_wraps(mk, lr):
    "A text line with no space, as in a transliterated Sanskrit file (words joined by dots), wraps in the page: the page gets no side scroll."
    import socket, threading, time, uvicorn, pytest
    from test_board_js import _chromium
    if not _chromium(): pytest.skip("Playwright's Chromium is not installed")
    from playwright.sync_api import sync_playwright
    long = '.'.join(['mūrtitve', 'parikalpitaḥ', 'śaśa', 'bhṛto', 'vartmā', 'apunar', 'janmanām'] * 12)
    d = lr.vault.add(f'Header\n\n{long}\n\nThe end.', title='gretil bj', source='/tmp/vr/gretil_bj.txt', kind='txt')['doc_id']
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(mk().app, host='127.0.0.1', port=port, log_level='error'))
    threading.Thread(target=srv.run, daemon=True).start()
    while not srv.started: time.sleep(.05)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page(viewport=dict(width=1100, height=800))
                pg.goto(f'http://127.0.0.1:{port}/v/store/{d}', wait_until='load')
                assert long[:40] in pg.content()
                assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
            finally: b.close()
    finally: srv.should_exit = True
