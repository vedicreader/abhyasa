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
    assert '1 of 2 ideas has a hands-on check: 1 is a notebook for your goal. You set about 33% for the other ideas.' in t

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

def test_concept_source_has_the_paper_title(mk, lr):
    "A concept from a paper that came in with its arXiv id as its title shows the title of the paper in its Source part after the repair at the start."
    import abhyasa.talk   # adds Learning.repair_id_titles
    lr.put('Self-attention', 'Each token looks at each other token.', 'ml', provenance=[dict(src='vault', shelf='store', doc_id='d1', title='1706.03762')])
    lr.put_journey(dict(id='p1', title='Attention Is All You Need', mode='walk', steps=[dict(slug='self-attention', status='todo', check=CK)],
                        source=dict(shelf='store', doc_id='d1', url='https://arxiv.org/abs/1706.03762', title='Attention Is All You Need')))
    lr.repair_id_titles()
    t = mk().get('/c/self-attention').text
    src = t[t.index('>Source<'):]
    assert 'Attention Is All You Need' in src and '1706.03762' not in src
