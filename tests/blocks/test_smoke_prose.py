"The lines that the real-data smoke test found: each count agrees with the others, and each line says one thing once."
import time
from walk_data import wait_for

CK = dict(way='words', kind='short', depth=2)

def test_fading_says_it_once(mk, lr):
    "A fading idea says its state, then its recall, with no second `fading`."
    lr.update('ranking', floor=3, seen=4, stability=1., last=time.time() - 30 * 86400)
    t = mk().get('/c/ranking').text
    assert 'Fading: recall is down to' in t and 'fading: fading' not in t.lower()

def test_source_line_counts_each_idea(mk, lr):
    "The research line counts each idea of the walk that is not skipped, not only the ideas that research looked at, and one idea has a source."
    for k in range(7): lr.put(f'Part {k}', f'Part {k} is one idea.', 'ml')
    read = dict(src='vault:notes', text='Ranking orders items by score.', title='My ranking notes')
    steps = [dict(slug='ranking', status='todo', check=CK, read=read, research='found'), *[dict(slug=f'part-{k}', status='todo', check=CK, research='none' if k < 4 else None) for k in range(7)],
             dict(slug='reciprocal-rank-fusion', status='skip', check=CK)]
    lr.put_journey(dict(id='w9', title='Nine ideas', mode='walk', steps=steps, research_start=time.time() - 60, research_end=time.time()))
    t = mk().get('/w/w9').text
    assert '1 of 8 ideas has a source.' in t and 'of 5 ideas' not in t

def test_hands_line_counts_the_goal_notebooks_apart(mk, lr):
    "A notebook that builds the goal is not one of the ideas of the hands-on share, and the line says so."
    nb = dict(way='code', kind='notebook', depth=4, why='it builds your goal')
    lr.put_journey(dict(id='wg', title='Goal walk', mode='walk', steps=[dict(slug='ranking', status='todo', check=CK),
                        *[dict(slug=s, status='todo', check=nb, hands='notebook') for s in ('reciprocal-rank-fusion',)]]))
    t = mk().get('/w/wg').text
    assert 'Hands-on checks: 0 of 1 idea (0%).' in t and '1 more idea is a notebook that builds your goal.' in t

def test_home_counts_agree(mk, lr):
    "Home counts an idea that you answered on as started, and a walk row counts a shaky idea, so the counts agree with Progress and the outline."
    lr.update('ranking', seen=1, floor=1)
    lr.put_journey(dict(id='ws', title='Shaky walk', mode='walk', started=1., steps=[dict(slug='ranking', status='todo', check=CK, done=dict(outcome='fragile', at=1.)),
                        dict(slug='reciprocal-rank-fusion', status='todo', check=CK)]))
    t = mk().get('/').text
    assert '0 of 2 ideas learned · 1 started' in t and '0 of 2 ideas · 1 shaky' in t and 'Now: Reciprocal rank fusion' in t

def test_plan_has_no_meta_lead(mk, lr):
    "The plan has no line about how the editor works, and the line about the other ideas of the source is short."
    lr.put_journey(dict(id='wm', title='More walk', mode='walk', more=['part-a', 'part-b'], steps=[dict(slug='ranking', status='todo', check=CK)]))
    t = mk().get('/w/wm').text
    assert 'Each idea has one check' not in t and 'The source has 2 more ideas. Learn one in a side walk when you need it.' in t

def test_concept_source_names_the_walk(mk, lr):
    "A concept that a walk added names the goal of the walk, or links to the walk, not only `A walk`."
    lr.put('Tokens', 'A token is a piece of text.', 'ml', provenance=[dict(src='journey', goal='learn how LLMs work')])
    lr.put('Heads', 'A head is one attention.', 'ml', provenance=[dict(src='journey', journey='w1')])
    assert 'The plan for your goal: learn how LLMs work' in mk().get('/c/tokens').text
    assert 'href="/w/w1">The walk that added it' in mk().get('/c/heads').text
