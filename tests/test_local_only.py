"The app answers only itself: no foreign Host, no cross-site request, no foreign Origin on a change."

def test_foreign_host_is_refused(mk):
    r = mk().get('/', headers={'Host': 'evil.example'})
    assert r.status_code == 403 and 'only on this Mac' in r.text

def test_cross_site_start_is_refused(mk):
    cl = mk()
    r = cl.get('/start?subject=ml', headers={'Sec-Fetch-Site': 'cross-site'}, follow_redirects=False)
    assert r.status_code == 403
    assert not cl.app.state.svc['sessions']                       # no session, so no model call

def test_same_origin_start_still_works(mk):
    r = mk().get('/start?subject=ml', headers={'Sec-Fetch-Site': 'same-origin'}, follow_redirects=False)
    assert r.status_code in (302, 303)

def test_foreign_origin_post_is_refused(mk):
    cl = mk()
    r = cl.post('/settings/key', data=dict(key='sk-evil'), headers={'Origin': 'https://evil.example'})
    assert r.status_code == 403 and 'other web sites' in r.text
    assert cl.post('/settings/model', data=dict(task='grade', model=''), headers={'Origin': 'http://testserver'}).status_code == 200

def test_loopback_hosts_pass(mk):
    for host in ('127.0.0.1:5077', 'localhost:5077', '[::1]:5077'):
        from abhyasa.app import LocalOnly
        assert LocalOnly(None).refuse(dict(method='GET', headers=[(b'host', host.encode())])) == '', host
