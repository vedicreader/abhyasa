"The Tree layout of the graph. `graphtree.js` has pure functions (no page, no d3), so node runs them here: the tree, the status words, a cycle, collapse and the arrow keys."
import json, shutil, subprocess, pytest
from pathlib import Path

JS = Path(__file__).parents[1]/'abhyasa/blocks/graph/graphtree.js'
NOW = 1_000_000
node = pytest.mark.skipif(not shutil.which('node'), reason='node is not installed')

def run(expr, **data):
    "The JSON value of `expr`, with `T` the module and `D` the data. A hang fails after 10 s."
    code = f"const T = require({json.dumps(str(JS))}); const D = {json.dumps(data)}; process.stdout.write(JSON.stringify({expr}))"
    r = subprocess.run(['node', '-e', code], capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)

def c(id, subject, floor=0, seen=0, due=None, name=None): return dict(id=id, name=name or id.replace('-', ' '), subject=subject, floor=floor, seen=seen, due=due)
def pre(*chain): return [dict(source=a, target=b, kind='prereq') for a, b in zip(chain, chain[1:])]

THERMO = [c('temperature', 'thermodynamics', 5, 4), c('heat', 'thermodynamics', 3, 2), c('first-law', 'thermodynamics', 2, 1),
          c('entropy', 'thermodynamics', 1, 1), c('second-law', 'thermodynamics')]
JYO = [c('rasi', 'jyotisha', 4, 3), c('graha', 'jyotisha', 2, 2), c('bhava', 'jyotisha')]
LINKS = pre('temperature', 'heat', 'first-law', 'entropy', 'second-law') + pre('rasi', 'graha', 'bhava')

def rows(nodes, links, collapsed=(), ready=3):
    "`[key, depth]` of each row in order."
    return run("T.rows(T.build(D.nodes, D.links, {ready: D.ready, now: D.now}), new Set(D.collapsed)).map(r => [r.item.key, r.depth])",
               nodes=nodes, links=links, collapsed=list(collapsed), ready=ready, now=NOW)

@node
def test_roots_are_subjects_and_each_concept_sits_under_what_it_builds_on():
    "Two subjects make two roots, in name order; each chain goes one step deeper for each prereq."
    assert rows(THERMO + JYO, LINKS) == [['s:jyotisha', 0], ['rasi', 1], ['graha', 2], ['bhava', 3],
                                         ['s:thermodynamics', 0], ['temperature', 1], ['heat', 2], ['first-law', 3], ['entropy', 4], ['second-law', 5]]

@node
def test_a_concept_with_several_prereqs_sits_under_the_deepest_and_the_others_are_cross_links():
    "The second law needs entropy, the first law and temperature: it sits under entropy, the deepest; the two other links are cross-links."
    links = LINKS + [dict(source='first-law', target='second-law', kind='prereq'), dict(source='temperature', target='second-law', kind='gap')]
    t = run("(t => ({parent: t.byKey.get('second-law').parent, cross: t.cross.map(l => [l.source, l.target]).sort()}))(T.build(D.nodes, D.links))", nodes=THERMO, links=links)
    assert t == {'parent': 'entropy', 'cross': [['first-law', 'second-law'], ['temperature', 'second-law']]}

@node
def test_status_words_use_the_ready_depth_and_the_due_rule_of_the_graph():
    "Depth 0 is not started, under the ready depth is under way, at it or over is mastered; a seen concept whose review time has come is review due."
    ns = [c('a', 's'), c('b', 's', 1, 1), c('c', 's', 2, 1), c('d', 's', 3, 1), c('e', 's', 5, 3), c('f', 's', 4, 2, due=NOW - 5),
          c('g', 's', 2, 1, due=NOW + 86400), c('h', 's', 0, 0, due=NOW - 5)]
    st = "(t => Object.fromEntries(D.nodes.map(n => [n.id, T.WORDS[t.byKey.get(n.id).status]])))(T.build(D.nodes, [], {ready: D.ready, now: D.now}))"
    assert run(st, nodes=ns, ready=3, now=NOW) == dict(a='not started', b='under way', c='under way', d='mastered', e='mastered', f='review due', g='under way', h='not started')
    assert run(st, nodes=ns, ready=4, now=NOW)['d'] == 'under way'   # the ready depth comes from the data, not from the script

@node
def test_a_cycle_does_not_hang_or_drop_a_node():
    "a, b and c need each other in a ring, and d needs c: the build ends, each concept is in the tree once, and each link is a branch or a cross-link."
    ns, links = [c(x, 's') for x in 'abcd'], pre('a', 'b', 'c', 'a') + pre('c', 'd')
    got = rows(ns, links)
    assert sorted(k for k, _ in got) == ['a', 'b', 'c', 'd', 's:s'] and len(got) == 5
    n = run("(t => [...t.byKey.values()].filter(i => i.parent && i.kind !== 'subject' && i.parent !== 's:' + i.subject).length + t.cross.length)(T.build(D.nodes, D.links))", nodes=ns, links=links)
    assert n == len(links)

@node
def test_a_self_link_a_double_link_and_a_link_to_a_hidden_concept_are_left_out():
    "Only links between two shown concepts count, once each."
    links = pre('heat', 'heat') + pre('heat', 'entropy') * 2 + pre('gone', 'heat')
    t = run("(t => [t.byKey.get('entropy').parent, t.byKey.get('heat').parent, t.cross.length])(T.build(D.nodes, D.links))", nodes=THERMO, links=links)
    assert t == ['heat', 's:thermodynamics', 0]

@node
def test_a_prereq_in_another_subject_is_a_cross_link():
    "A concept stays in its own subject: a prereq in another subject is a cross-link, not a parent."
    links = LINKS + [dict(source='rasi', target='heat', kind='prereq')]
    t = run("(t => [t.byKey.get('heat').parent, t.cross.map(l => l.source + '>' + l.target)])(T.build(D.nodes, D.links))", nodes=THERMO + JYO, links=links)
    assert t == ['temperature', ['rasi>heat']]

@node
def test_collapse_hides_the_branch_and_counts_what_it_hides():
    "A closed branch keeps its own row, hides the rows under it and says how many there are."
    assert [k for k, _ in rows(THERMO, LINKS, ['heat'])] == ['s:thermodynamics', 'temperature', 'heat']
    assert run("T.build(D.nodes, D.links).byKey.get('heat').size", nodes=THERMO, links=LINKS) == 3
    assert [k for k, _ in rows(THERMO + JYO, LINKS, ['s:jyotisha'])][:2] == ['s:jyotisha', 's:thermodynamics']

@node
def test_arrow_keys_move_to_the_parent_the_first_child_and_the_siblings():
    "Parent, child, previous and next sibling; a move with nowhere to go stays; a closed branch has no child to move to."
    links = LINKS + pre('heat', 'work')
    ns = THERMO + JYO + [c('work', 'thermodynamics')]
    mv = "(t => D.moves.map(([k, d, shut]) => T.move(t, k, d, new Set(shut || []))))(T.build(D.nodes, D.links))"
    moves = [['graha', 'parent'], ['graha', 'child'], ['rasi', 'parent'], ['s:jyotisha', 'next'], ['s:thermodynamics', 'prev'],
             ['first-law', 'next'], ['work', 'prev'], ['work', 'next'], ['heat', 'child', ['heat']], [None, 'next'], ['bhava', 'child']]
    assert run(mv, nodes=ns, links=links, moves=moves) == ['rasi', 'bhava', 's:jyotisha', 's:thermodynamics', 's:jyotisha',
                                                             'work', 'first-law', 'work', 'heat', 's:jyotisha', 'bhava']

def test_the_data_carries_the_ready_depth_of_the_path(mk):
    "The page gets the depth at which a concept is ready from `abhyasa.path.READY`, so the Tree's mastered word uses the real threshold."
    from abhyasa.path import READY
    assert mk().get('/graph.json').json()['ready'] == READY

def test_the_levers_offer_the_tree_and_its_list(mk):
    "The Layout section has Tree on key 5, a tick that shows the tree as a list, and a place for the list beside the canvas; the page loads the tree script before the graph."
    t = mk().get('/library/graph').text
    assert 'value="tree"' in t and '<kbd>5</kbd>' in t and 'name="asList"' in t and 'class="outline"' in t
    assert t.index('/assets/graphtree.js') < t.index('/assets/graph.js')
