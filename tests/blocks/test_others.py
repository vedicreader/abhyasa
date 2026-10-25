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
    assert 'Vault shelves' in t and 'Index ramabana sessions' in t

def test_concept_seen_in_your_work(mk, lr):
    t = mk(['concepts']).get('/c/ranking').text
    assert 'Seen in your work' in t and 'My ranking notes' in t and 'https://example.org/notes' in t
    assert lr.concept('ranking').seen_in[0]['src'] == 'vault:notes'
