"The Start box on Home: it reads what you paste, says what it will do, asks only when in doubt, and starts a walk."
import re

def test_detect_never_touches_the_network(monkeypatch):
    import socket
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: (_ for _ in ()).throw(AssertionError('network')))
    from abhyasa.detect import detect, DETECT_CASES
    for t, ti, _ in DETECT_CASES: detect(t, ti)

def test_read_route_says_what_it_will_do(mk):
    h = mk().get('/learn/read', params=dict(q='1706.03762')).text
    assert 'aria-live="polite"' in h and 'An arXiv paper.' in h

def test_read_route_asks_for_a_vault_name(mk, lr):
    lr.vault.add('Some text about nakshatras.', title='Nakshatras', source='test://n')
    h = mk().get('/learn/read', params=dict(q='nakshatras')).text
    assert 'is in your vault.' in h and 'Walk through that document' in h and 'Plan a walk on the topic' in h

def test_start_with_q_makes_a_walk(mk, lr, walk_fake):
    r = mk().post('/walk/new', data=dict(q='Softmax turns scores into weights.\nLarge scores win.'))
    assert r.headers.get('HX-Redirect', '').startswith('/w/')

PLAN = dict(title='Attention', subject='ml', steps=[dict(name='Ranking', statement='', slug='', why='Scores to places.', needs=[], ways=['code'])])

def test_web_line_shows_once(mk, lr, walk_fake):
    "The line about the web search shows until a topic walk is made. A topic walk that fails does not count."
    from abhyasa.settings import set_val, val
    set_val('research.told', False)   # the settings folder is shared by the tests
    cl = mk(); line = 'Your topic goes to the search engine.'
    assert line in cl.get('/learn/read', params=dict(q='how attention works')).text
    walk_fake.rules['You plan a learning path'] = dict(title='Nothing', subject='ml', steps=[])
    assert 'req-err' in cl.post('/walk/new', data=dict(q='how attention works')).text and not val('research.told')
    assert line in cl.get('/learn/read', params=dict(q='how attention works')).text
    walk_fake.rules['You plan a learning path'] = PLAN
    assert cl.post('/walk/new', data=dict(q='how attention works')).headers.get('HX-Redirect', '').startswith('/w/')
    assert line not in cl.get('/learn/read', params=dict(q='how attention works')).text

def test_add_opens_the_start_box(mk):
    r = mk().get('/add', follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == '/#start'

def test_start_is_off_until_it_can_start(mk):
    "Empty, a video and a question keep Start off. A paper turns it on and fills it."
    cl = mk()
    for q in ('', 'https://youtu.be/x', 'The moon spends about one day in each of the lunar mansions.', '~/code/course22'):
        h = cl.get('/learn/read', params=dict(q=q)).text
        assert re.search(r'<button[^>]*\bdisabled\b[^>]*id="start-go"', h), q
    h = cl.get('/learn/read', params=dict(q='1706.03762')).text
    assert 'data-wait="Reading the paper…" data-skel="#walk-out" data-act="start" id="start-go"' in h and 'class="go"' in h

def test_options_show_only_when_they_matter(mk):
    cl = mk()
    assert 'It is a library or a command-line tool' in cl.get('/learn/read', params=dict(q='github.com/a/b')).text
    tick = lambda **kw: bool(re.search(r'<input type="checkbox" name="tool" checked id="start-tool"', cl.get('/learn/read', params=dict(q='github.com/a/b', **kw)).text))
    assert tick(opts='pages') and tick() and not tick(opts='tool')   # ticked, unless you took the tick off
    assert 'Pages to read' in cl.get('/learn/read', params=dict(q='https://docs.python.org/3/')).text
    t = cl.get('/learn/read', params=dict(q='a\nb')).text
    assert 'name="title"' in t and 'name="subject"' in t and 'Find concepts only' in t and 'hx-post="/add"' in t
    assert 'name="subject"' not in cl.get('/learn/read', params=dict(q='1706.03762')).text

def test_answer_doc_walks_through_the_document_by_its_id(mk, lr, walk_fake):
    "The question carries the id of the document, and the walk reads that document, not a newer one with a longer title that also matches."
    d = lr.vault.add('Softmax turns scores into weights. Large scores win.', title='Softmax notes', source='test://s')['doc_id']
    lr.vault.add('Softmax turns scores into weights. Large scores win. More.', title='Softmax notes, part 2', source='test://s2')
    cl = mk()
    assert f'name="doc" value="{d}"' in cl.get('/learn/read', params=dict(q='softmax notes')).text
    r = cl.post('/walk/new', data=dict(q='softmax notes', pick='doc', doc=d))
    jid = r.headers['HX-Redirect'].split('/')[-1]
    assert {s['read']['doc_id'] for s in lr.journey(jid).steps} == {d}

def test_a_question_with_no_answer_does_not_start(mk, lr):
    lr.vault.add('Some text about nakshatras.', title='Nakshatras', source='test://n')
    assert 'Pick one answer first.' in mk().post('/walk/new', data=dict(q='Nakshatras')).text

def test_find_concepts_only_takes_the_box(mk, lr):
    t = mk(['add']).post('/add', data=dict(q='A rank is a position.', subject='ml')).text
    assert '/c/rank' in t

PDF = b'%PDF-1.4 x'

def test_drop_refuses_a_big_or_strange_file(mk, monkeypatch):
    "A file over the limit, a file with no PDF name, and a .pdf with no PDF header are refused with a plain line."
    import abhyasa.blocks.add.app as a
    cl = mk()
    assert 'Drop a PDF' in cl.post('/learn/file', files=dict(f=('a.exe', b'x'))).text
    assert 'not a PDF' in cl.post('/learn/file', files=dict(f=('a.pdf', b'<html>', 'application/pdf'))).text
    monkeypatch.setattr(a, 'DROP_MB', 0)
    assert 'too big' in cl.post('/learn/file', files=dict(f=('a.pdf', PDF, 'application/pdf'))).text

def test_drop_reads_no_more_than_the_limit(mk, monkeypatch):
    "With no size, the route reads at most the limit and one byte."
    import abhyasa.blocks.add.app as a
    from starlette.datastructures import UploadFile
    got = []
    async def read(self, n=-1): got.append(n); return PDF + b'x' * 100
    monkeypatch.setattr(UploadFile, 'read', read)
    monkeypatch.setattr(UploadFile, 'size', property(lambda self: None, lambda self, v: None), raising=False)   # a client that sends no size
    monkeypatch.setattr(a, 'DROP_MB', 0)
    assert 'too big' in mk().post('/learn/file', files=dict(f=('a.pdf', PDF, 'application/pdf'))).text and got == [1]

def test_drop_files_a_pdf_and_fills_the_box(mk, lr, monkeypatch):
    "Each drop gets its own file, the title keeps the spaces of the name, and the form carries the id of the document."
    got = []
    def pdf(path, title=None, **kw): got.append((path, title)); return dict(title=title, doc_id=f'd{len(got)}')
    monkeypatch.setattr(lr.vault, 'pdf', pdf)
    cl = mk()
    h = cl.post('/learn/file', files=dict(f=('My paper.pdf', PDF, 'application/pdf'))).text
    assert got[0][1] == 'My paper' and 'A PDF. abhyasa reads it in full.' in h and 'value="My paper.pdf"' in h and 'value="d1"' in h
    cl.post('/learn/file', files=dict(f=('My paper.pdf', PDF + b' new', 'application/pdf')))
    from pathlib import Path
    assert got[0][0] != got[1][0] and Path(got[0][0]).read_bytes() == PDF and Path(got[1][0]).read_bytes() == PDF + b' new'

def test_a_slow_drop_answers_and_goes_on(mk, lr, monkeypatch):
    "When the vault takes longer than DROP_WAIT, the request answers with a plain line, and the job goes on to the end."
    import threading, abhyasa.blocks.add.app as a
    go, done = threading.Event(), threading.Event()
    def pdf(path, title=None, **kw): go.wait(5); done.set(); return dict(title=title, doc_id='d1')
    monkeypatch.setattr(lr.vault, 'pdf', pdf); monkeypatch.setattr(a, 'DROP_WAIT', .05)
    h = mk().post('/learn/file', files=dict(f=('Slow.pdf', PDF, 'application/pdf'))).text
    assert 'still reading this PDF' in h and 'shows in your vault' in h
    go.set(); assert done.wait(5)

def test_dropped_pdf_starts_from_its_id(mk, lr, walk_fake):
    "Start after a drop reads the document by its id, also when another title has the same words."
    d = lr.vault.add('Softmax turns scores into weights. Large scores win.', title='Notes', source='test://a')['doc_id']
    lr.vault.add('Softmax turns scores into weights. Large scores win. Other.', title='Notes, newer', source='test://b')
    jid = mk().post('/walk/new', data=dict(q='Notes', file='Notes.pdf', doc=d)).headers['HX-Redirect'].split('/')[-1]
    assert {s['read']['doc_id'] for s in lr.journey(jid).steps} == {d}

def test_title_index_is_made_again_only_when_the_vault_changes(lr):
    from abhyasa.detect import title_index
    a = title_index(lr.vault)
    assert title_index(lr.vault) is a
    lr.vault.add('A new text.', title='New one', source='test://new')
    b = title_index(lr.vault)
    assert b is not a and 'new one' in b

def test_a_file_name_or_a_bare_host(mk, lr):
    "A file name is never a topic. A bare host such as example.com is a site."
    cl = mk()
    assert 'drop it on this box' in cl.get('/learn/read', params=dict(q='paper.pdf')).text
    lr.vault.add('Text.', title='paper', source='test://p')
    assert 'A document in your vault.' in cl.get('/learn/read', params=dict(q='paper.pdf')).text
    assert 'A docs site.' in cl.get('/learn/read', params=dict(q='example.com')).text

