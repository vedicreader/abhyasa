"Sort by hand on the Concepts page: rename a group, make a group, \"Move to…\" and the drop, Undo, and \"Sort everything again\" with its preview."
import json, re, time
import pytest

SORT = 'Return JSON: {"places"'

@pytest.fixture
def jy(lr):
    "The `lr` concepts (ml, no group) and three jyotisha concepts: two in `nakshatras`, sorted by the tutor, and one with no group."
    for n in ('Ashvini', 'Bharani'): lr.put(n, f'{n}.', 'jyotisha', group=['nakshatras'], group_by='sort')
    lr.put('Mesha', 'The first rasi.', 'jyotisha')
    lr.save_groups('jyotisha')
    return lr

def step(t): return re.search(r'name="step" value="([0-9a-f]+)"', t).group(1)

def test_move_to_and_new_group_routes(mk, jy):
    cl = mk()
    t = cl.get('/concepts').text
    assert 'Move to…' in t and 'New group' in t and 'Rename' in t and 'class="handle"' in t and 'data-drop="nakshatras"' in t
    assert '<option' in cl.get('/c/mesha/move', params=dict(at='')).text and 'Not in a group' in cl.get('/c/mesha/move').text
    t = cl.post('/concepts/group/new', data=dict(subject='jyotisha', path='Rasis', at='')).text
    assert 'Made the group “Rasis”.' in t and 'undo-bar' in t and ['Rasis'] in jy.hand_groups('jyotisha')
    assert re.search(r'data-drop="Rasis"', t)                                         # an empty group shows, so you can drop on it
    t = cl.post('/c/mesha/group', data=dict(group='Rasis', back='tree', at='')).text
    c = jy.concept('mesha')
    assert (c.group, c.group_by) == (['Rasis'], 'hand') and 'Moved “Mesha” to Rasis.' in t and 'id="concepts-view"' not in t
    assert re.search(r'<details(?=[^>]*\bopen\b)[^>]*class="tree grp"[^>]*>\s*<summary[^>]*data-drop="Rasis"', t)   # the group it went in is open
    assert 'Moved.' in cl.post('/c/ashvini/group', data=dict(group='Rasis')).text       # the concept page keeps its own answer

def test_rename_group_route_and_undo(mk, jy):
    cl = mk()
    f = cl.get('/concepts/group/rename', params=dict(subject='jyotisha', path='nakshatras', at='')).text
    assert 'value="nakshatras"' in f and 'name="path"' in f
    t = cl.post('/concepts/group/rename', data=dict(subject='jyotisha', path='nakshatras', name='Lunar mansions', at='')).text
    assert 'Renamed the group “nakshatras” to “Lunar mansions”.' in t
    assert {(tuple(jy.concept(s).group), jy.concept(s).group_by) for s in ('ashvini', 'bharani')} == {(('Lunar mansions',), 'hand')}
    t = cl.post('/concepts/undo', data=dict(step=step(t), at='')).text
    assert jy.concept('ashvini').group == ['nakshatras'] and jy.concept('ashvini').group_by == 'sort'
    assert ['Lunar mansions'] not in jy.groups('jyotisha') and 'undo-bar' not in t
    assert 'Nothing to undo' in cl.post('/concepts/undo', data=dict(step='0' * 8, at='')).text
    t = cl.post('/concepts/group/rename', data=dict(subject='jyotisha', path='nakshatras', name='!!!', at='')).text
    assert 'letters or digits' in t and jy.concept('ashvini').group == ['nakshatras']

def test_rename_a_concept_on_its_page(mk, jy):
    cl = mk()
    assert 'id="name-field"' in cl.get('/c/mesha').text
    t = cl.post('/c/mesha/rename', data=dict(name='Aries')).text
    assert 'Renamed “Mesha” to “Aries”.' in t and 'id="concept-name"' in t and jy.concept('mesha').named_by == 'hand'
    r = cl.post('/concepts/undo', data=dict(step=step(t)))
    assert r.headers.get('HX-Refresh') == 'true' and jy.concept('mesha').name == 'Mesha'
    assert 'two letters' in cl.post('/c/mesha/rename', data=dict(name='x')).text and jy.concept('mesha').name == 'Mesha'

def settled(cl, n=250):
    for _ in range(n):
        t = cl.get('/concepts/sort').text
        if 'is sorting' not in t: return t
        time.sleep(.02)
    raise AssertionError('the sort did not end')

def test_sort_everything_preview_saves_nothing(mk, jy, fake):
    fake.rules[SORT] = lambda p, sp: dict(places=[dict(slug=s, group=['Stars']) for s in re.findall(r'^- ([a-z0-9-]+):', p, re.M)])
    jy.new_group('jyotisha', 'Rasis'); jy.set_group('mesha', ['Rasis'])
    jy.new_group('jyotisha', 'Mine')
    cl = mk()
    t = cl.get('/concepts').text
    assert 'Sort everything again' in t and 'Untick a group to let the tutor sort it too.' in t and t.count('name="keep"') == 2
    keep = json.dumps(['jyotisha', 'Mine'])                                            # Rasis is unticked: the tutor sorts Mesha too
    cl.post('/concepts/sort', data=dict(every='1', keep=[keep]))
    t = settled(cl)
    assert 'Accept this tree' in t and '1 group that you made stays.' in t and 'Ashvini' in t
    assert jy.concept('ashvini').group == ['nakshatras'] and jy.concept('mesha').group == ['Rasis']   # nothing is saved before the accept
    assert any('Sort all these concepts again' in p and '- mesha:' in p for p, _ in fake.calls if SORT in p)
    cl.post('/concepts/sort/accept', data=dict(sort=re.search(r'name="sort" value="([0-9a-f]+)"', t).group(1)))
    assert jy.concept('ashvini').group == ['Stars'] and (jy.concept('mesha').group, jy.concept('mesha').group_by) == (['Stars'], 'sort')
    assert jy.hand_groups('jyotisha') == [['Mine']] and ['nakshatras'] not in jy.groups('jyotisha')

def test_sort_again_and_sort_new_do_not_mix(mk, jy, fake):
    import threading
    gate = threading.Event()
    def slow(p, sp): gate.wait(5); return dict(places=[])
    fake.rules[SORT] = slow
    cl = mk()
    cl.post('/concepts/sort', data=dict(every='1'))
    assert 'Try again when it is done' in cl.post('/concepts/sort').text
    gate.set(); settled(cl)

# Fix round 1

def test_names_lose_control_characters(mk, jy):
    cl = mk()
    t = cl.post('/c/mesha/rename', data=dict(name='Ar\x00ies\x1b[31m' + 'y' * 300)).text
    n = jy.concept('mesha').name
    assert '\x00' not in n and '\x1b' not in n and len(n) <= 120 and n.startswith('Ar ies [31m') and '\x1b' not in t
    cl.post('/concepts/group/rename', data=dict(subject='jyotisha', path='nakshatras', name='Lunar\x00 mansions\x1b', at=''))
    assert jy.concept('ashvini').group == ['Lunar mansions']

def test_group_routes_check_the_subject(mk, jy):
    cl = mk()
    for bad in ('nope', 'jyotisha\x00', 'x' * 300):
        assert 'No such subject.' in cl.post('/concepts/group/new', data=dict(subject=bad, path='Rasis', at='')).text, bad
        assert 'No such subject.' in cl.post('/concepts/group/rename', data=dict(subject=bad, path='nakshatras', name='Stars', at='')).text, bad
        assert 'No such subject.' in cl.get('/concepts/group/new', params=dict(subject=bad)).text, bad
    assert jy.saved_groups('nope') is None and jy.concept('ashvini').group == ['nakshatras']

def test_buttons_name_their_concept_or_group(mk, jy):
    t = mk().get('/concepts').text
    assert 'aria-label="Move “Mesha” to a group"' in t and 'aria-label="Rename the group “Nakshatras”"' in t and 'aria-label="Make a new group in Jyotisha"' in t

def test_undo_of_a_first_group_list_leaves_no_list(mk, lr):
    cl = mk()
    assert lr.saved_groups('ml') is None
    t = cl.post('/concepts/group/new', data=dict(subject='ml', path='Heads', at='')).text
    cl.post('/concepts/undo', data=dict(step=step(t), at=''))
    assert lr.saved_groups('ml') is None

def test_a_failed_accept_changes_nothing(mk, jy, fake, monkeypatch):
    fake.rules[SORT] = lambda p, sp: dict(places=[dict(slug=s, group=['Stars']) for s in re.findall(r'^- ([a-z0-9-]+):', p, re.M)])
    jy.new_group('jyotisha', 'Rasis'); jy.set_group('mesha', ['Rasis'])
    cl = mk()
    cl.post('/concepts/sort', data=dict(every='1'))                                   # Rasis unticked
    t = settled(cl)
    from abhyasa.store import Learning
    real = Learning.save_groups
    def boom(self, *a, **k): raise RuntimeError('the disk is full')
    monkeypatch.setattr(Learning, 'save_groups', boom)
    r = cl.post('/concepts/sort/accept', data=dict(sort=re.search(r'name="sort" value="([0-9a-f]+)"', t).group(1)))
    monkeypatch.setattr(Learning, 'save_groups', real)
    assert 'Nothing changed' in r.text and 'disk is full' not in r.text
    assert (jy.concept('mesha').group, jy.concept('mesha').group_by) == (['Rasis'], 'hand') and jy.concept('ashvini').group == ['nakshatras']
    assert jy.hand_groups('jyotisha') == [['Rasis']]

def test_preview_opens_and_marks_the_moves(mk, jy, fake):
    fake.rules[SORT] = lambda p, sp: dict(places=[dict(slug=s, group=['Stars']) for s in re.findall(r'^- ([a-z0-9-]+):', p, re.M) if s != 'ranking'])
    cl = mk()
    cl.post('/concepts/sort', data=dict(every='1'))
    t = settled(cl)
    assert 'from nakshatras → Stars' in t and 'from Not sorted yet → Stars' in t
    assert re.search(r'<details(?=[^>]*\bopen\b)[^>]*class="tree grp"[^>]*>\s*<summary[^>]*><span class="name">Stars', t)
    assert 'left for you: Ranking. They stay in Not sorted yet.' in t
    assert re.search(r'<details(?=[^>]*\bopen\b)[^>]*class="tree loose"', t)

def test_page_title_is_the_display_name(mk, jy):
    t = mk().get('/concepts', params=dict(subject='ml')).text
    assert '<h1>ML</h1>' in t or re.search(r'<h1[^>]*>ML</h1>', t)
