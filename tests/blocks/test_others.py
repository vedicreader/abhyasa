from abhyasa.ground import passage

def test_voice_stt(mk):
    assert mk(['voice']).post('/voice/stt?hint=rrf', content=b'1234').json() == dict(text='4 bytes about rrf')

def test_graph_json(mk):
    g = mk(['graph']).get('/graph.json?subject=ml').json()
    assert {n['id'] for n in g['nodes']} == {'ranking', 'reciprocal-rank-fusion'}
    assert g['links'] == [dict(source='ranking', target='reciprocal-rank-fusion', kind='prereq')]

def test_concepts_list(mk):
    t = mk(['concepts']).get('/concepts?subject=ml').text
    assert 'Ranking' in t and 'Reciprocal rank fusion' in t

def test_search(mk):
    t = mk(['search']).get('/search?q=score').text
    assert 'In what you learned' in t and 'Order items by a score' in t

def test_add_text(mk, lr):
    t = mk(['add']).post('/add', data=dict(subject='ml', text='A rank is a position.')).text
    assert '/c/rank' in t and lr.concept('rank').subject == 'ml'

def test_add_needs_input(mk):
    assert 'Paste text' in mk(['add']).post('/add', data=dict(subject='ml')).text

def test_sources_page(mk):
    t = mk(['sources']).get('/sources').text
    assert 'Vault shelves' not in t and 'Index ' not in t and 'vedicreader' not in t and 'Sources appear here when you start a walk' in t
    assert mk(['sources']).post('/sources/index/ramabana').status_code == 404   # abhyasa no longer indexes ramabana or leela sessions

def test_concept_seen_in_your_work(lr, fake):
    "The concept page GET does no search of the sources: the pool finds the links, and the next visit shows them."
    import threading
    from abhyasa.app import mk_app
    from starlette.testclient import TestClient
    from walk_data import wait_for
    asked = []
    class Notes:
        name = 'notes'
        def search(self, q, k=4):
            asked.append(threading.current_thread().name)
            return [passage('vault:notes', 'n1', 'My ranking notes', 'Ranking orders items by score.', url='https://example.org/notes')]
    cl = TestClient(mk_app(lr, fake, names=['concepts'], sources=[Notes()], hosts=('testserver',)))
    t = cl.get('/c/ranking').text
    assert 'Ranking' in t and wait_for(lambda: lr.concept('ranking').get('seen_in') or None)[0]['src'] == 'vault:notes'
    assert asked and all(n.startswith('ThreadPoolExecutor') for n in asked), asked   # the pool of the app, not the thread of the request
    t = cl.get('/c/ranking').text
    assert 'Seen in your work' in t and 'My ranking notes' in t and 'https://example.org/notes' in t

def test_due_json(mk, lr):
    cl = mk(['today'])
    assert cl.get('/due.json').json() == dict(due=0)
    lr.update('ranking', seen=1, due=1.)
    lr.update('reciprocal-rank-fusion', seen=1, due=4e9)
    assert cl.get('/due.json').json() == dict(due=1)
