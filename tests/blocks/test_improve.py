"The box that changes the walk: your words, the changes that the tutor makes at once with the ops of the editor, a short list of what changed, and one Undo."
import re, time
from fastcore.basics import AttrDict
from fastcore.foundation import L
from walk_data import walk
from flows import change
import abhyasa.blocks.walk.app as W

PROPOSE = 'You propose changes to one learning walk'
URL = 'https://example.org/attention'

def depths(lr, jid): return [s['check'].get('depth', 2) for s in lr.journey(jid).steps]
def slugs(lr, jid): return [s['slug'] for s in lr.journey(jid).steps]

def test_one_box_at_the_top_and_no_forms_on_each_idea(mk, walk_fake, lr):
    "The walk page has one box before the plan, which Enter sends. Each idea has only Lock and the ⋯ menu with Skip and Remove: no rewrite form, no split, merge or add."
    cl = mk(); jid = walk(cl, lr)
    t = cl.get(f'/w/{jid}').text
    box = re.search(r'<textarea[^>]*id="change-words"[^>]*>', t)[0]
    assert 'data-enter="1"' in box and t.index('id="change"') < t.index('id="plan"') and 'Enter sends. Shift+Enter starts a new line.' in t
    assert t.count('data-lock="1"') == 3 and t.count('class="more-menu row-menu"') == 3 and t.count('>Skip ') == 3 and t.count('>Remove ') == 3
    for gone in ('Rewrite with the tutor', 'Merge with next', 'Split', 'Add an idea', 'Improve the walk', 'Pick another passage', 'Apply the kept changes'): assert gone not in t, gone

def test_simpler_makes_easier_checks_at_once_with_one_undo(mk, walk_fake, lr):
    "Simpler: the tutor makes easier checks at once. The list says what changed; the idea that you did keeps its progress, and Undo takes all back."
    walk_fake.rules[PROPOSE] = dict(changes=[dict(op='easier', idea=s, why='The check asks less.') for s in ('softmax', 'scaling-by-the-root-of-dk')])
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    lr.walk_step(jid, 0, done=dict(outcome='solid', at=time.time()))
    was = depths(lr, jid)
    r = change(cl, jid, 'Make the walk simpler.')
    assert depths(lr, jid) == [was[0], max(1, was[1] - 1), max(1, was[2] - 1)] and lr.journey(jid).steps[0]['done']['outcome'] == 'solid'
    assert 'Made the check of “Softmax” easier.' in r.text and 'What changed' in r.text and 'id="steps"' in r.text and 'hx-swap-oob' in r.text
    assert 'Make the walk simpler.' in walk_fake.calls[-1][0]
    eid = lr.edits('walk', jid)[0].id
    assert f'{{"step": "{eid}"}}' in r.text.replace('&quot;', '"')   # Undo takes back this change
    cl.post(f'/w/{jid}/undo', data=dict(step=eid))
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
    r = change(cl, jid, f'Add attention, from {URL}')
    assert f'Added “Attention” as idea 2, from {URL}.' in r.text and f'The links that the learner gave: {URL}' in walk_fake.calls[-2][0]
    assert f'link:{URL}' in lr.journey(jid).chips   # the link joins the sources of the walk
    s = lr.journey(jid).steps[1]
    assert s['slug'] == 'attention' and s['read']['url'] == URL and s['read']['text'].startswith('Attention mixes the values by weights.')

def test_the_box_merges_rewrites_changes_a_kind_and_asks_for_a_source(mk, walk_fake, lr):
    "Merge, rewrite, the kind of a check and a source from the web: one change by the tutor. A source change starts research on that idea."
    walk_fake.rules.update({PROPOSE: dict(changes=[dict(op='rewrite', idea='sequential-computation', text='simpler', why='x'), dict(op='kind', idea='softmax', kind='demo', why='x'),
                                                   dict(op='source', idea='sequential-computation', why='x'), dict(op='merge', idea='softmax', why='x')]),
                            'Rewrite these fields': dict(note='A short note.')})
    cl = mk(); jid = walk(cl, lr)
    r = change(cl, jid, 'make idea 1 simpler, a demo for idea 2, sources for idea 1, merge idea 2 with idea 3')
    j = lr.journey(jid)
    assert slugs(lr, jid) == ['sequential-computation', 'softmax'] and j.steps[0]['note'] == 'A short note.' and j.steps[1]['check']['kind'] == 'demo'
    assert 'Merged “Softmax” with the next idea.' in r.text and 'Looks for a source for “Sequential computation”.' in r.text

def test_a_locked_idea_stays_and_empty_words_ask_for_words(mk, walk_fake, lr):
    "The box never changes a locked idea. Empty words change nothing and ask for words. Nothing to change says so."
    cl = mk(); jid = walk(cl, lr)
    cl.post(f'/w/{jid}/edit', data=dict(slug='softmax', act='lock'))
    walk_fake.rules[PROPOSE] = dict(changes=[dict(op='remove', idea='softmax', why='x')])
    assert 'The tutor found nothing to change.' in change(cl, jid, 'drop softmax').text and 'softmax' in slugs(lr, jid)
    assert 'Write what should change.' in cl.post(f'/w/{jid}/improve', data=dict(words='  ')).text

def test_the_head_and_the_box_follow_a_change_and_its_undo(mk, walk_fake, lr):
    "After a box change, the head line of the walk (ideas and minutes) comes again out of band, so it is not old. Undo sends it again and clears What changed."
    walk_fake.rules[PROPOSE] = dict(changes=[dict(op='remove', idea='softmax', why='x')])
    cl = mk(); jid = walk(cl, lr)
    size = lambda t: re.search(r'<span[^>]*id="walk-size"[^>]*>([^<]*)</span>', t)
    assert size(cl.get(f'/w/{jid}').text)[1].startswith('3 ideas')
    r = change(cl, jid, 'drop softmax')
    got = size(r.text)
    assert got and 'hx-swap-oob="true"' in got[0] and got[1].startswith('2 ideas')
    u = cl.post(f'/w/{jid}/undo', data=dict(step=lr.edits('walk', jid)[0].id)).text
    assert size(u)[1].startswith('3 ideas') and re.search(r'<div[^>]*id="change-out"[^>]*></div>', u) and 'hx-swap-oob' in re.search(r'<div[^>]*id="change-out"[^>]*>', u)[0]
