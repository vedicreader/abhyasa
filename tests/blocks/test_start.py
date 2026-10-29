"The Start box in Learn: it reads what you paste, says what it will do, asks only when in doubt, and starts a walk."
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

def test_web_line_shows_once(mk, lr, fake):
    from abhyasa.settings import set_val
    set_val('research.told', False)   # the settings folder is shared by the tests
    cl = mk(); line = 'Your topic goes to the search.'
    assert line in cl.get('/learn/read', params=dict(q='how attention works')).text
    cl.post('/walk/new', data=dict(q='how attention works'))
    assert line not in cl.get('/learn/read', params=dict(q='how attention works')).text

def test_goal_box_left_today(mk):
    cl = mk()
    assert 'What do you want to learn?' not in cl.get('/').text
    h = cl.get('/learn').text
    assert '<summary>More</summary>' in h and 'Plan a path of concepts, with no source' in h

def test_add_opens_the_start_box(mk):
    r = mk().get('/add', follow_redirects=False)
    assert r.status_code == 303 and r.headers['location'] == '/learn#start'

def test_start_is_off_until_it_can_start(mk):
    "Empty, a video and a question keep Start off. A paper turns it on and fills it."
    cl = mk()
    for q in ('', 'https://youtu.be/x', 'The moon spends about one day in each of the lunar mansions.', '~/code/course22'):
        h = cl.get('/learn/read', params=dict(q=q)).text
        assert re.search(r'<button disabled type="button"( hidden)? id="start-go"', h), q
    h = cl.get('/learn/read', params=dict(q='1706.03762')).text
    assert 'data-wait="Reading the paper…" data-skel="#walk-out" id="start-go"' in h and 'class="go"' in h

def test_options_show_only_when_they_matter(mk):
    cl = mk()
    assert 'It is a library or a command-line tool' in cl.get('/learn/read', params=dict(q='github.com/a/b')).text
    assert 'Pages to read' in cl.get('/learn/read', params=dict(q='https://docs.python.org/3/')).text
    t = cl.get('/learn/read', params=dict(q='a\nb')).text
    assert 'name="title"' in t and 'name="subject"' in t and 'Find concepts only' in t and 'hx-post="/add"' in t
    assert 'name="subject"' not in cl.get('/learn/read', params=dict(q='1706.03762')).text

def test_answer_doc_walks_through_the_document(mk, lr, walk_fake):
    lr.vault.add('Softmax turns scores into weights. Large scores win.', title='Softmax notes', source='test://s')
    r = mk().post('/walk/new', data=dict(q='softmax notes', pick='doc'))
    assert r.headers.get('HX-Redirect', '').startswith('/w/')

def test_a_question_with_no_answer_does_not_start(mk, lr):
    lr.vault.add('Some text about nakshatras.', title='Nakshatras', source='test://n')
    assert 'Pick one answer first.' in mk().post('/walk/new', data=dict(q='Nakshatras')).text

def test_find_concepts_only_takes_the_box(mk, lr):
    t = mk(['add']).post('/add', data=dict(q='A rank is a position.', subject='ml')).text
    assert '/c/rank' in t

def test_drop_refuses_a_big_or_strange_file(mk, monkeypatch):
    import abhyasa.blocks.add.app as a
    monkeypatch.setattr(a, 'DROP_MB', 0)
    cl = mk()
    assert 'too big' in cl.post('/learn/file', files=dict(f=('a.pdf', b'%PDF-1.4 x', 'application/pdf'))).text
    assert 'Drop a PDF' in cl.post('/learn/file', files=dict(f=('a.exe', b'x'))).text

def test_drop_files_a_pdf_and_fills_the_box(mk, lr, monkeypatch):
    got = {}
    def pdf(path, title=None, **kw): got.update(path=path, title=title); return dict(title=title)
    monkeypatch.setattr(lr.vault, 'pdf', pdf)
    h = mk().post('/learn/file', files=dict(f=('My paper.pdf', b'%PDF-1.4 x', 'application/pdf'))).text
    assert got['title'] == 'My-paper' and 'A PDF. abhyasa reads it in full.' in h and 'value="My paper.pdf"' in h

def test_vedicreader_is_under_more_on_sources(mk):
    import re
    assert re.search(r'<summary>More</summary>.*Import vedicreader', mk().get('/sources').text, re.S)
