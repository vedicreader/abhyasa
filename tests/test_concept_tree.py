"The tree on the Concepts page: groups under each subject, the find box, the sort by the model, and a move by hand."
import re, threading, time
import pytest

SORT = 'Return JSON: {"places"'

@pytest.fixture
def jy(lr):
    "The `lr` concepts (ml, with no group, as in an old vault) and three jyotisha concepts, two of them in groups."
    lr.put('Ashvini', 'The first nakshatra.', 'jyotisha', group=['nakshatras'], group_by='model')
    lr.put('Magha', 'The tenth nakshatra.', 'jyotisha', aliases=['Maghā'], group=['nakshatras', 'pitri gana'], group_by='model')
    lr.put('Mesha', 'The first rasi.', 'jyotisha')
    return lr

def details(t, cls):
    "The opening tags of the `details` with the class `cls`."
    return re.findall(rf'<details[^>]*class="tree {cls}"[^>]*>', t)

def summary(t, name, n):
    "Whether the page has a summary for the branch `name` with the count `n`."
    return re.search(rf'<summary[^>]*><span class="name">{re.escape(name)}</span><span class="n">\s*·\s*{n}</span>(?:(?!</summary>).)*</summary>', t, re.S) is not None

# The tree

def test_old_vault_sits_in_not_sorted_yet(mk):
    "Concepts with no group are under their subject, in an open `Not sorted yet` part. The subject is open."
    t = mk().get('/concepts').text
    assert summary(t, 'ML', 2) and summary(t, 'Not sorted yet', 2) and 'Ranking' in t and 'Reciprocal rank fusion' in t
    assert all(' open' in d for d in details(t, 'subj')) and all(' open' in d for d in details(t, 'loose'))

def test_tree_has_counts_and_closed_groups(mk, jy):
    t = mk().get('/concepts').text
    assert summary(t, 'Jyotisha', 3) and summary(t, 'Nakshatras', 2) and summary(t, 'Pitri gana', 1) and summary(t, 'ML', 2)
    assert all(' open' not in d for d in details(t, 'grp'))                       # quiet: groups start closed
    assert t.index('Nakshatras') < t.index('Not sorted yet') < t.index('Mesha')      # the groups, then the concepts with no group
    assert '4 concepts' not in t and re.search(r'5 concepts · 2 subjects · 3 not sorted yet', t)

def test_find_opens_the_branch_of_a_deep_concept(mk, jy):
    "With `q`, the page keeps the concepts that match, in any case and without marks, and opens each branch above them."
    t = mk().get('/concepts', params=dict(q='MAGH')).text
    assert 'Magha' in t and 'Ashvini' not in t and 'Ranking' not in t
    assert summary(t, 'Jyotisha', 1) and summary(t, 'Pitri gana', 1)
    assert details(t, 'grp') and all(' open' in d for d in details(t, 'grp'))
    assert 'value="MAGH"' in t
    assert 'Magha' in mk().get('/concepts', params=dict(q='maghā')).text           # an alias with a mark matches too

def test_find_with_no_match_points_to_search(mk, jy):
    t = mk().get('/concepts', params=dict(q='zzz')).text
    assert 'No concept matches “zzz”.' in t and 'href="/search?q=zzz"' in t

def test_rows_carry_the_words_to_find(mk, jy):
    "The find box filters in the page as you type (concepts.js): each row has its folded name and aliases."
    t = mk().get('/concepts').text
    assert 'data-find="magha magha"' in t and 'concepts.js' in t and 'id="find"' in t

# A move by hand

def test_group_field_moves_a_concept_by_hand(mk, jy):
    cl = mk()
    r = cl.post('/c/mesha/group', data=dict(group=' Rasis /  Fire signs '))
    assert r.status_code == 200 and 'Moved.' in r.text and 'value="Rasis / Fire signs"' in r.text
    c = jy.concept('mesha')
    assert (c.group, c.group_by) == (['Rasis', 'Fire signs'], 'hand')
    t = cl.get('/c/mesha').text
    assert 'id="group-field"' in t and 'value="Rasis / Fire signs"' in t and 'You set this group.' in t
    assert '<option value="nakshatras / pitri gana">' in t                              # the groups of the subject to pick from

def test_group_field_checks_the_input(mk, jy):
    cl = mk()
    for bad, said in (('a / b / c', 'two levels at most'), ('x' * 41, '40 characters at most'), ('!!! / ???', 'letters or digits'), ('y' * 300, '40 characters at most')):
        r = cl.post('/c/mesha/group', data=dict(group=bad))
        assert r.status_code == 200 and said in r.text and 'req-err' in r.text, bad
        assert jy.concept('mesha').get('group') is None, bad
    cl.post('/c/mesha/group', data=dict(group='Stars & planets!'))
    assert jy.concept('mesha').group == ['Stars planets']                             # marks go; the name stays
    cl.post('/c/mesha/group', data=dict(group='jyotisha / rasis'))
    assert jy.concept('mesha').group == ['rasis']                                     # the subject is not a group
    cl.post('/c/mesha/group', data=dict(group=''))
    assert (jy.concept('mesha').group, jy.concept('mesha').group_by) == ([], 'hand')  # empty: out of the group, and the tutor does not sort it again
    assert 'You keep this concept out of the groups.' in cl.get('/c/mesha').text
    assert cl.post('/c/nope/group', data=dict(group='x')).status_code == 404

def test_group_shows_who_set_it(mk, jy):
    assert 'The tutor set this group.' in mk().get('/c/magha').text

# Sort my concepts

def sorter(gate=None):
    "A sort reply that puts Mesha in Rasis and each other concept in Stars, after `gate` opens."
    def f(p, sp):
        if gate: gate.wait(5)
        return dict(places=[dict(slug=s, group=['Rasis'] if s == 'mesha' else ['Stars']) for s in re.findall(r'^- ([a-z0-9-]+):', p, re.M)])
    return f

def settled(cl, n=250):
    "The sort part after the job is done."
    for _ in range(n):
        t = cl.get('/concepts/sort').text
        if 'is sorting' not in t: return t
        time.sleep(.02)
    raise AssertionError('the sort did not end')

def sort_id(t): return re.search(r'name="sort" value="([0-9a-f]+)"', t).group(1)

def test_sort_runs_in_the_background_and_saves_only_on_accept(mk, jy, fake):
    gate = threading.Event()
    fake.rules[SORT] = sorter(gate)
    jy.set_group('magha', ['mine'])                                                   # moved by hand: the sort never changes it
    cl = mk()
    t = cl.post('/concepts/sort').text
    assert 'The tutor is sorting your concepts' in t and 'hx-get="/concepts/sort"' in t
    assert 'The tutor is sorting your concepts' in cl.get('/concepts').text          # the page reads the state of the job
    gate.set()
    t = settled(cl)
    assert 'Accept this tree' in t and 'Cancel' in t and summary(t, 'Rasis', 1) and summary(t, 'Stars', 2)
    assert 'Mine' not in t and 'Ashvini' not in t                                   # only the new concepts show
    assert 'The tutor moves 3 concepts.' in t and '1 concept that you moved by hand stays where it is.' in t
    assert not any('- magha:' in p for p, _ in fake.calls if SORT in p)
    assert jy.concept('mesha').get('group') is None                                   # nothing is saved before the accept
    assert 'Accept this tree' in cl.get('/concepts').text                             # the page shows the proposal until you choose
    r = cl.post('/concepts/sort/accept', data=dict(sort='0' * 8))
    assert 'This sort is old' in r.text and jy.concept('mesha').get('group') is None
    r = cl.post('/concepts/sort/accept', data=dict(sort=sort_id(t)))
    assert r.headers.get('HX-Redirect') == '/library'
    assert (jy.concept('mesha').group, jy.concept('mesha').group_by) == (['Rasis'], 'sort')
    assert jy.concept('magha').group == ['mine'] and jy.concept('ashvini').group == ['nakshatras']   # a concept with a group never moves
    t = cl.get('/concepts').text
    assert 'Accept this tree' not in t and summary(t, 'Rasis', 1) and 'sort-form' not in t       # nothing is new: no button

def settled_in(cl, subject, n=250):
    "The sort part of `subject` after the job is done."
    for _ in range(n):
        t = cl.get('/concepts/sort', params=dict(subject=subject)).text
        if 'is sorting' not in t: return t
        time.sleep(.02)
    raise AssertionError('the sort did not end')

def test_sort_of_one_subject(mk, jy, fake):
    fake.rules[SORT] = sorter()
    cl = mk()
    cl.post('/concepts/sort', data=dict(subject='ml'))
    t = settled_in(cl, 'ml')
    assert summary(t, 'ML', 2) and 'Jyotisha' not in t
    cl.post('/concepts/sort/accept', data=dict(sort=sort_id(t), subject='ml'))
    assert jy.concept('ranking').group == ['Stars'] and jy.concept('mesha').get('group') is None

def test_cancel_saves_nothing(mk, jy, fake):
    fake.rules[SORT] = sorter()
    cl = mk()
    cl.post('/concepts/sort')
    t = settled(cl)
    r = cl.post('/concepts/sort/cancel', data=dict(sort=sort_id(t)))
    assert 'Sort 3 new concepts' in r.text and 'Accept this tree' not in r.text
    assert jy.concept('mesha').get('group') is None and 'Accept this tree' not in cl.get('/concepts').text
    assert 'No sort is running' in cl.post('/concepts/sort/accept', data=dict(sort=sort_id(t))).text

def test_get_only_reads(mk, jy, fake):
    "A GET never starts a sort and never asks the model."
    fake.rules[SORT] = sorter()
    cl = mk()
    n = len(fake.calls)
    assert 'No sort is running' in cl.get('/concepts/sort').text
    assert 'Sort 3 new concepts' in cl.get('/concepts').text and 'is sorting' not in cl.get('/concepts').text
    assert len(fake.calls) == n

def test_a_failed_sort_shows_a_plain_line(mk, jy, fake):
    def boom(p, sp): raise RuntimeError('litellm.APIError: secret words')
    fake.rules[SORT] = boom
    cl = mk()
    cl.post('/concepts/sort')
    t = settled(cl)
    assert 'The tutor could not sort your concepts. Try again.' in t and 'secret words' not in t and 'Sort 3 new concepts' in t

def test_changes_from_other_sites_are_refused(mk, jy, fake):
    fake.rules[SORT] = sorter()
    cl, n = mk(), len(fake.calls)
    evil = {'Origin': 'https://evil.example'}
    assert cl.post('/concepts/sort', headers=evil).status_code == 403
    assert cl.post('/c/mesha/group', data=dict(group='x'), headers=evil).status_code == 403
    assert cl.post('/concepts/sort/accept', data=dict(sort='x'), headers=evil).status_code == 403
    assert len(fake.calls) == n and jy.concept('mesha').get('group') is None

def test_label_of_a_subject_or_a_group():
    "A short name with no space is in upper case. A name in lower case gets a capital first letter. Other names show as they are."
    from abhyasa.blocks.concepts.ui import label
    assert [label(x) for x in ('ml', 'ai', 'nlp', 'jyotisha', 'iOS', 'deva gana', 'GraphQL', 'ab c', '')] == \
           ['ML', 'AI', 'NLP', 'Jyotisha', 'iOS', 'Deva gana', 'GraphQL', 'Ab c', 'General']

def test_two_subjects_do_not_mix(mk, jy, fake):
    "A sort of one subject shows only on the page of that subject, and its accept needs that subject. A second sort waits for the first one."
    gate = threading.Event()
    fake.rules[SORT] = sorter(gate)
    cl = mk()
    assert 'The tutor is sorting your concepts' in cl.post('/concepts/sort', data=dict(subject='ml')).text
    t = cl.get('/concepts').text
    assert 'is sorting' not in t and 'Jyotisha' in t                                  # the page of all subjects is not the ml sort
    assert 'is sorting' in cl.get('/concepts', params=dict(subject='ml')).text
    assert 'No sort is running' in cl.get('/concepts/sort', params=dict(subject='jyotisha')).text
    t = cl.post('/concepts/sort', data=dict(subject='jyotisha')).text
    assert 'The tutor is sorting the concepts of ml now' in t and 'is sorting your concepts' not in t
    gate.set()
    t = settled_in(cl, 'ml')
    assert 'Accept this tree' in t and 'Jyotisha' not in t and 'name="subject" value="ml"' in t
    assert 'Accept this tree' not in cl.get('/concepts').text
    r = cl.post('/concepts/sort/accept', data=dict(sort=sort_id(t)))                  # the right id, but not the subject of the sort
    assert 'This sort is old' in r.text and jy.concept('ranking').get('group') is None
    r = cl.post('/concepts/sort/accept', data=dict(sort=sort_id(t), subject='ml'))
    assert r.headers.get('HX-Redirect') == '/library?subject=ml'
    assert jy.concept('ranking').group == ['Stars'] and jy.concept('mesha').get('group') is None

# Every concept gets a place

def test_summary_counts_and_the_one_follow_up(mk, jy, fake):
    "A concept that the model leaves out is asked for again one time, then named in the line of the proposal."
    jy.set_group('magha', ['mine'])                                                   # by hand: not in the count
    def skips_mesha(p, sp):
        return dict(places=[dict(slug=s, group=['Stars']) for s in re.findall(r'^- ([a-z0-9-]+):', p, re.M) if s != 'mesha'])
    fake.rules[SORT] = skips_mesha
    cl = mk()
    cl.post('/concepts/sort')
    t = settled(cl)
    assert '2 placed. 1 left for you: Mesha.' in t and 'The tutor moves 2 concepts.' in t
    assert sum('- mesha:' in p for p, _ in fake.calls if SORT in p) == 2              # the first request and one follow-up
    assert not any('- magha:' in p for p, _ in fake.calls if SORT in p)
    cl.post('/concepts/sort/accept', data=dict(sort=sort_id(t)))
    assert jy.concept('mesha').get('group') is None and jy.concept('magha').group == ['mine']

def test_sort_gives_a_subject_to_a_concept_with_none(mk, jy, fake):
    "A concept with no subject is shown under a proposed subject and group. The accept sets the subject, then the group."
    jy.put('Attention', 'Weights on values.'); jy.put('Pinned', 'Mine.'); jy.set_group('pinned', ['mine'])
    def f(p, sp):
        return dict(places=[dict(slug=s, group=['Layers'], subject='Transformers') if s == 'attention' else dict(slug=s, group=['Stars'])
                            for s in re.findall(r'^- ([a-z0-9-]+):', p, re.M)])
    fake.rules[SORT] = f
    cl = mk()
    cl.post('/concepts/sort')
    t = settled(cl)
    assert summary(t, 'Transformers', 1) and summary(t, 'Layers', 1) and '0 left for you.' in t
    assert jy.concept('attention').subject == ''                                      # nothing is saved before the accept
    cl.post('/concepts/sort/accept', data=dict(sort=sort_id(t)))
    c = jy.concept('attention')
    assert (c.subject, c.group, c.group_by) == ('transformers', ['Layers'], 'sort')
    assert (jy.concept('pinned').subject, jy.concept('pinned').group) == ('', ['mine'])

# Saved groups are locked

def test_button_counts_the_new_concepts_and_goes_at_zero(mk, jy):
    "The button names the concepts with no group. With none, it is gone. A concept that you kept out of the groups by hand does not count."
    cl = mk()
    t = cl.get('/concepts').text
    assert 'Sort 3 new concepts' in t and 'Sort my concepts' not in t              # ranking, reciprocal rank fusion and mesha
    assert 'Sort 1 new concept<' in cl.get('/concepts', params=dict(subject='jyotisha')).text
    for s in ('ranking', 'reciprocal-rank-fusion'): jy.set_group(s, ['Lists'], by='sort')
    jy.set_group('mesha', [], by='hand')
    assert 'sort-form' not in cl.get('/concepts').text and 'Sort ' not in cl.get('/concepts').text.split('Find a concept')[1][:400]

def test_a_saved_sort_is_locked_and_the_next_sort_sends_only_new_concepts(mk, jy, fake):
    "The preview shows only the new placements. After the accept, a sorted concept never moves, and the next request has only the new concepts and the saved groups."
    fake.rules[SORT] = sorter()
    cl = mk()
    cl.post('/concepts/sort')
    t = settled(cl)
    assert 'Ashvini' not in t and 'Magha' not in t and 'The tutor moves 3 concepts.' in t and summary(t, 'Rasis', 1) and summary(t, 'Stars', 2)
    sent = [p for p, _ in fake.calls if SORT in p]
    assert not any('- ashvini:' in p or '- magha:' in p for p in sent)
    cl.post('/concepts/sort/accept', data=dict(sort=sort_id(t)))
    assert jy.concept('mesha').group_by == 'sort' and jy.saved_groups('jyotisha') == [['nakshatras'], ['nakshatras', 'pitri gana'], ['Rasis']]
    jy.put('Rohini', 'The fourth nakshatra.', 'jyotisha')
    assert 'Sort 1 new concept<' in cl.get('/concepts').text
    fake.calls.clear()
    cl.post('/concepts/sort')
    t = settled(cl)
    p = next(p for p, _ in fake.calls if SORT in p)
    assert '- rohini:' in p and '- mesha:' not in p and 'Rasis' in p and 'Groups of this subject now: nakshatras; nakshatras › pitri gana; Rasis' in p
    cl.post('/concepts/sort/accept', data=dict(sort=sort_id(t)))
    assert jy.concept('mesha').group == ['Rasis'] and jy.concept('ashvini').group == ['nakshatras']      # nothing else moved

def wait_until(f, n=250):
    "The value of `f()` when it is true, with up to `n` tries."
    for _ in range(n):
        if (v := f()): return v
        time.sleep(.02)
    raise AssertionError('it did not happen')

def test_new_concepts_are_placed_in_the_background_and_can_be_undone(mk, jy, fake):
    "A concept that comes into a subject with groups is placed on the pool, marked, and has an Undo. A failure only logs."
    jy.save_groups('jyotisha'); jy.set_group('mesha', [], by='hand')                  # kept out by hand: the tutor leaves it
    fake.rules['Return JSON: {"concepts"'] = dict(concepts=[dict(name='Bharani', statement='The second nakshatra.')])
    fake.rules[SORT] = lambda p, sp: dict(places=[dict(slug=s, group=['nakshatras']) for s in re.findall(r'^- ([a-z0-9-]+):', p, re.M)])
    cl = mk()
    r = cl.post('/add', data=dict(subject='jyotisha', text='Bharani is a nakshatra.'))
    assert r.status_code == 200 and 'Bharani' in r.text
    c = wait_until(lambda: (c := jy.concept('bharani')) and c.get('group') and c)
    assert (c.group, c.group_by) == (['nakshatras'], 'placed')
    t = cl.get('/concepts').text
    assert t.count('Placed by the tutor') == 1 and 'Undo' in t
    r = cl.post('/c/bharani/undo')
    assert r.headers.get('HX-Refresh') == 'true' and (jy.concept('bharani').group, jy.concept('bharani').group_by) == ([], 'undone')
    t = cl.get('/concepts').text
    assert 'Placed by the tutor' not in t and 'Sort ' in t and 'Bharani' in t
    cl.post('/c/ashvini/undo'); assert jy.concept('ashvini').group == ['nakshatras']      # only a placement by the tutor can be undone

class Now:
    "A pool that runs a job at once, so a test waits on nothing."
    def __init__(self, n=2): pass
    def submit(self, f, *a, **kw):
        from concurrent.futures import Future
        fu = Future()
        try: fu.set_result(f(*a, **kw))
        except BaseException as e: fu.set_exception(e)
        return fu

def test_a_failed_placement_only_logs(mk, jy, fake, monkeypatch, caplog):
    "The model fails: the request still works, the concept stays in `Not sorted yet`, and the log has a line."
    monkeypatch.setattr('abhyasa.app.ThreadPoolExecutor', Now)
    jy.save_groups('jyotisha'); jy.set_group('mesha', [], by='hand')
    fake.rules[SORT] = lambda p, sp: (_ for _ in ()).throw(RuntimeError('model down'))
    fake.rules['Return JSON: {"concepts"'] = dict(concepts=[dict(name='Rohini', statement='The fourth nakshatra.')])
    with caplog.at_level('WARNING'): r = mk().post('/add', data=dict(subject='jyotisha', text='Rohini.'))
    assert r.status_code == 200 and jy.concept('rohini').get('group') is None and 'could not place the new concepts' in caplog.text

def test_an_undone_concept_is_not_placed_again(mk, jy, fake, monkeypatch):
    "After an Undo, a later add that places new concepts leaves the undone one where it is."
    monkeypatch.setattr('abhyasa.app.ThreadPoolExecutor', Now)
    jy.save_groups('jyotisha'); jy.set_group('mesha', [], by='hand')
    fake.rules[SORT] = lambda p, sp: dict(places=[dict(slug=s, group=['nakshatras']) for s in re.findall(r'^- ([a-z0-9-]+):', p, re.M)])
    cl = mk()
    fake.rules['Return JSON: {"concepts"'] = dict(concepts=[dict(name='Bharani', statement='The second nakshatra.')])
    cl.post('/add', data=dict(subject='jyotisha', text='Bharani.'))
    assert jy.concept('bharani').group_by == 'placed'
    cl.post('/c/bharani/undo'); n = len(fake.calls)
    fake.rules['Return JSON: {"concepts"'] = dict(concepts=[dict(name='Bharani', statement='Again.', group=['nakshatras']), dict(name='Rohini', statement='The fourth nakshatra.')])
    cl.post('/add', data=dict(subject='jyotisha', text='Bharani and Rohini.'))
    assert (jy.concept('bharani').group, jy.concept('bharani').group_by) == ([], 'undone') and jy.concept('rohini').group_by == 'placed'
    assert not any('- bharani:' in p for p, _ in fake.calls[n:] if SORT in p)

def test_other_ways_to_add_concepts_place_them_too(mk, jy, fake, monkeypatch):
    "An idea that you add to a walk and an idea that you split make new concepts. The concepts block places them."
    monkeypatch.setattr('abhyasa.app.ThreadPoolExecutor', Now)
    jy.save_groups('jyotisha'); jy.set_group('mesha', [], by='hand')
    fake.rules[SORT] = lambda p, sp: dict(places=[dict(slug=s, group=['nakshatras']) for s in re.findall(r'^- ([a-z0-9-]+):', p, re.M)])
    jy.put_journey(dict(id='jj', title='Stars', goal='Stars', subject='jyotisha', mode='walk', created=0, steps=[dict(slug='ashvini', status='todo', why='', check=dict(way='words', kind='short', depth=2))]))
    cl = mk()
    fake.rules['The idea: '] = dict(name='Bharani', statement='The second nakshatra.')
    cl.post('/w/jj/edit', data=dict(act='add', name='Bharani'))
    assert (jy.concept('bharani').group, jy.concept('bharani').group_by) == (['nakshatras'], 'placed')
    fake.rules['Return JSON: {"concepts"'] = dict(concepts=[dict(name='Krittika', statement='The third nakshatra.')])
    cl.post('/w/jj/edit', data=dict(act='split', slug='ashvini'))
    assert (jy.concept('krittika').group, jy.concept('krittika').group_by) == (['nakshatras'], 'placed')

# Sort by hand (the engine)

def test_rename_group_marks_hand_and_tutor_never_moves(lr):
    for n in ('Ashvini', 'Bharani'): lr.put(n, '', 'jyotisha', group=['nakshatras'])
    lr.save_groups('jyotisha'); lr.rename_group('jyotisha', ['nakshatras'], 'Lunar mansions')
    cs = lr.concepts('jyotisha')
    assert all(c.group == ['Lunar mansions'] and c.group_by == 'hand' for c in cs)
    assert ['Lunar mansions'] in lr.hand_groups('jyotisha') and ['nakshatras'] not in lr.groups('jyotisha')
    assert not lr.unsorted('jyotisha') and not lr.place('ashvini', ['Other'])

def test_rename_into_existing_group_merges(lr):
    lr.put('Alpha', '', 's', slug='a', group=['padas']); lr.put('Beta', '', 's', slug='b', group=['Padas x'])
    lr.save_groups('s'); lr.rename_group('s', ['Padas x'], 'PADAS')
    assert [g for g in lr.groups('s') if g[0].lower() == 'padas'] == [['padas']] and lr.concept('b').group == ['padas']

def test_hand_name_survives_extract(lr):
    lr.put('Self-attention', 'x', 'ml'); lr.rename('self-attention', 'Attention over one sequence')
    lr.put('Self-attention', 'y', 'ml')
    assert lr.concept('self-attention').name == 'Attention over one sequence'

def test_sort_everything_keeps_hand_unless_unticked(lr):
    from abhyasa.llm import Fake
    from abhyasa.sources import propose_groups, apply_groups
    for n in ('H1', 'H2'): lr.put(n, '', 'ml', group=['H']); lr.set_group(n.lower(), ['H'])
    for n in ('S1', 'S2', 'S3'): lr.put(n, '', 'ml', group=['Old'], group_by='sort')
    fake = Fake({SORT: lambda p, sp: dict(places=[dict(slug=s, group=['New']) for s in re.findall(r'^- ([a-z0-9-]+):', p, re.M)])})
    p = propose_groups(lr, fake, 'ml', every=True); apply_groups(lr, p, every=True)
    assert lr.concept('h1').group == ['H'] and lr.concept('s1').group == ['New']
    p = propose_groups(lr, fake, 'ml', every=True, free=['h1', 'h2']); apply_groups(lr, p, every=True, free=['h1', 'h2'])
    assert lr.concept('h1').group == ['New'] and lr.concept('h1').group_by == 'sort'
