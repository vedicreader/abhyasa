"Improve the walk: your words, the changes that the tutor proposes with the ops of the editor, Keep or Skip on each, and one Undo."
import re, time
from fastcore.basics import AttrDict
from fastcore.foundation import L
from walk_data import walk
from flows import improve as ask, key_of
import abhyasa.blocks.walk.app as W

PROPOSE = 'You propose changes to one learning walk'
URL = 'https://example.org/attention'

def depths(lr, jid): return [s['check'].get('depth', 2) for s in lr.journey(jid).steps]

def test_the_fold_is_quiet_with_one_box_and_its_chips(mk, walk_fake, lr):
    "The walk page has one fold, Improve the walk, closed, with one box and three chips. A finished walk has a fourth chip: From your weak ideas."
    cl = mk(); jid = walk(cl, lr)
    t = cl.get(f'/w/{jid}').text
    head, fold = re.search(r'(<details[^>]*id="improve"[^>]*>)(.*?)</details>', t, re.S).groups()
    assert ' open' not in head and 'What should change?' in fold and 'https://…' in fold   # closed until you open it
    assert [c for c in ('Simpler', 'Harder', 'Add an idea', 'From your weak ideas') if f'>{c}</button>' in fold] == ['Simpler', 'Harder', 'Add an idea']
    cl.post(f'/w/{jid}/start')
    for i in range(3): lr.walk_step(jid, i, done=dict(outcome='fragile' if i else 'solid', at=time.time()))
    assert '>From your weak ideas</button>' in cl.get(f'/w/{jid}').text

def test_simpler_gives_easier_checks_with_one_undo(mk, walk_fake, lr):
    "Simpler: the tutor proposes easier checks, each with its reason. Apply makes them easier as one change; the idea that you did keeps its progress, and Undo takes all back."
    walk_fake.rules[PROPOSE] = dict(changes=[dict(op='easier', idea=s, why='The check asks less.') for s in ('softmax', 'scaling-by-the-root-of-dk')])
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 0, done=dict(outcome='solid', at=time.time()))
    was = depths(lr, jid)
    p = ask(cl, jid, 'Make the walk simpler.')
    assert 'Make the check of “Softmax” easier.' in p and 'The check asks less.' in p and 'Apply the kept changes' in p
    assert 'Make the walk simpler.' in walk_fake.calls[-1][0]
    r = cl.post(f'/w/{jid}/improve/apply', data=dict(key=key_of(p)))
    assert depths(lr, jid) == [was[0], max(1, was[1] - 1), max(1, was[2] - 1)] and lr.journey(jid).steps[0]['done']['outcome'] == 'solid'
    assert 'Improved the walk: 2 changes.' in r.text and 'Applied 2 changes.' in r.text and 'id="steps"' in r.text
    cl.post(f'/w/{jid}/undo')
    assert depths(lr, jid) == was and lr.journey(jid).steps[0]['done']['outcome'] == 'solid'

def test_a_link_becomes_an_idea_with_that_source(mk, walk_fake, lr, monkeypatch):
    "A link in the words is filed as a source of the walk, and the idea that the tutor adds from it has its passage, word for word."
    def filed(lr_, u, pages=None):
        d = lr_.vault.add([(0, 'Attention mixes the values by weights. The weights come from the scores of each query against each key.')], 'Attention notes', source=u, kind='web')
        return L([AttrDict(shelf='store', doc_id=d['doc_id'], title='Attention notes', url=u)])
    monkeypatch.setattr(W, 'file_link', filed)
    walk_fake.rules.update({PROPOSE: dict(changes=[dict(op='add', name='Attention', link=URL, to=2, why='You asked for it.')]),
                            'The idea: ': dict(name='Attention', statement='Attention mixes values by weights.')})
    cl = mk(); jid = walk(cl, lr)
    p = ask(cl, jid, f'Add attention, from {URL}')
    assert f'Add “Attention” as idea 2, from {URL}.' in p and f'The links that the learner gave: {URL}' in walk_fake.calls[-1][0]
    assert f'link:{URL}' in lr.journey(jid).chips   # the link joins the sources of the walk
    cl.post(f'/w/{jid}/improve/apply', data=dict(key=key_of(p), c0='keep'))
    s = lr.journey(jid).steps[1]
    assert s['slug'] == 'attention' and s['read']['url'] == URL and s['read']['text'].startswith('Attention mixes the values by weights.')

def test_skip_leaves_a_change_out(mk, walk_fake, lr):
    "Skip on a row leaves that change out; the kept one is made. When you skip each change, nothing changes."
    walk_fake.rules[PROPOSE] = dict(changes=[dict(op='remove', idea='sequential-computation', why='You know it.'), dict(op='harder', idea='softmax', why='A real test.')])
    cl = mk(); jid = walk(cl, lr)
    ss, was = [s['slug'] for s in lr.journey(jid).steps], depths(lr, jid)
    p = ask(cl, jid, 'Harder, and drop what I know.')
    assert 'Remove “Sequential computation”.' in p and 'Make the check of “Softmax” harder.' in p
    cl.post(f'/w/{jid}/improve/apply', data=dict(key=key_of(p), c0='skip', c1='keep'))
    assert [s['slug'] for s in lr.journey(jid).steps] == ss and depths(lr, jid)[1] == min(4, was[1] + 1)
    p = ask(cl, jid, 'Harder again.')
    r = cl.post(f'/w/{jid}/improve/apply', data=dict(key=key_of(p), c0='skip', c1='skip'))
    assert 'You skipped each change. Nothing changed.' in r.text and len(lr.edits('walk', jid)) == 1
