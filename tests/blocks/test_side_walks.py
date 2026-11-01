"A side walk (its `parent` is set) belongs only to the idea that opened it: it is not on the concept page, not a target of Open it in, and not a place for Continue."
import time

def walks(lr, parent=None):
    "A walk `wk1` of two ideas, and a side walk `side1` on its first idea, opened from its second idea and used after it."
    now = time.time()
    lr.put_journey(dict(id='wk1', title='Softmax walk', mode='walk', goal='learn softmax', started=now - 600, here=dict(step=1, at=now - 600),
                        steps=[dict(slug='ranking', status='todo'), dict(slug='reciprocal-rank-fusion', status='todo')]))
    lr.put_journey(dict(id='side1', title='Side walk on ranking', mode='walk', depth=1, started=now, here=dict(step=0, at=now),
                        steps=[dict(slug='ranking', status='todo')], parent=parent or dict(walk='wk1', step=1, idea='reciprocal-rank-fusion')))

def top(page): return page.split('id="continue"')[0].rsplit('<a ', 1)[1] + page.split('id="continue"')[1].split('</a>')[0]

def card(page): return page.split('class="continue-card"')[1].split('</div>')[0]

def test_the_concept_page_shows_only_your_own_walks(mk, lr):
    "In your walks lists the walk, not the side walk, and Open it in goes to the idea in the walk, though the side walk is newer."
    walks(lr)
    page = mk().get('/c/ranking').text
    assert 'In your walks' in page and 'href="/w/wk1/0"' in page and '/w/side1' not in page
    btn = page.split('data-act="open-in-walk"')[0].rsplit('<a ', 1)[1] + page.split('data-act="open-in-walk"')[1].split('</a>')[0]
    assert 'Open it in Softmax walk' in btn and 'href="/w/wk1/0"' in btn

def test_a_concept_only_in_a_side_walk_has_no_walk_on_its_page(mk, lr):
    "A concept that only a side walk has: no In your walks list and no Open it in."
    walks(lr); lr.put_journey({**lr.journey('wk1'), 'steps': [dict(slug='reciprocal-rank-fusion', status='todo')]})
    lr.put_journey({**lr.journey('side1'), 'parent': dict(walk='wk1', step=0, idea='reciprocal-rank-fusion')})
    page = mk().get('/c/ranking').text
    assert 'In your walks' not in page and 'open-in-walk' not in page and '/w/side1' not in page

def test_continue_in_a_side_walk_names_its_parent_walk(mk, lr):
    "The side walk is the newest place, but the top bar and the Home card continue the idea of the walk that opened it."
    from abhyasa.path import last_place
    walks(lr); cl = mk()
    p = last_place(lr)
    assert (p.walk, p.step, p.title) == ('wk1', 1, 'Softmax walk')
    t = top(cl.get('/w/side1/0').text)
    assert 'Continue: Softmax walk' in t and 'href="/w/wk1/1"' in t
    c = card(cl.get('/').text)
    assert 'Softmax walk' in c and 'href="/w/wk1/1"' in c and 'side1' not in c and 'Side walk' not in c
    assert 'id="continue"' not in cl.get('/w/wk1/1').text   # on the place itself, the top bar has no Continue

def test_a_side_walk_with_no_parent_step_is_no_place(mk, lr):
    "A side walk whose walk is gone, or that Leela opened, is never what Continue picks."
    from abhyasa.path import last_place
    for parent in (dict(walk='gone', step=0), dict(leela='lesson-1')):
        walks(lr, parent)
        assert last_place(lr).walk == 'wk1', parent
        lr.drop_journey('wk1')
        assert last_place(lr) is None, parent
        assert 'continue-card' not in mk().get('/').text, parent   # Home has no Continue card
