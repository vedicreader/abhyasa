"A walk, an idea, a concept, a course or a document that is not there gives a real 404, with the same friendly page."

def test_missing_objects_give_a_404(mk, lr):
    "Each missing object gives the status 404 and the page that says so, with the top bar. An old link to a missing path is a 404 too, not a redirect."
    lr.put_journey(dict(id='w1', title='One walk', mode='walk', steps=[dict(slug='ranking', status='todo', check=dict(way='words', kind='short', depth=2))]))
    cl = mk()
    for u, say in (('/w/no-such-walk', 'No such walk'), ('/w/no-such-walk/0', 'No such walk'), ('/w/w1/99', 'No such walk'), ('/path/no-such', 'No such walk'),
                   ('/c/no-such-concept', 'No such concept'), ('/course/no-such', 'No such course'), ('/v/store/no-such-doc', 'No such document')):
        r = cl.get(u, follow_redirects=False)
        assert r.status_code == 404 and say in r.text and 'aria-label="Main"' in r.text, u
    assert cl.get('/w/w1/0').status_code == 200 and cl.get('/c/ranking').status_code == 200

def test_a_missing_demo_is_one_redirect(mk):
    "A link to a demo that is not there is one 301 to the Library, not a chain through the old Concepts path."
    r = mk().get('/demo/no-such', follow_redirects=False)
    assert r.status_code == 301 and r.headers['location'] == '/library'
