"A concept such as `x` with the statement `x`: no tool can file a new one, and one that an older tool filed stays in the vault but out of the lists. `C` is an idea, and `Bias` with the statement `x` stays out of the lists."
from abhyasa.store import STATE, concept_text, _src

def stray(lr):
    "File the concept `x` as the old ramabana tool did, past the name check of `put`."
    m = dict(STATE, name='x', statement='x', subject='code', slug='x', prereqs=[], related=[], aliases=[], provenance=[dict(src='ramabana')], questions=[])
    lr.v.add(concept_text(m), title='x', source=_src('concept', 'x'), kind='concept', meta=m)

def test_a_stray_concept_stays_out_of_the_lists(mk, lr):
    "The stray concept stays in the vault, and its page opens, but Library and the graph leave it out. A new concept named `x` is refused."
    import pytest
    stray(lr); cl = mk()
    assert lr.concept('x').name == 'x' and cl.get('/c/x').status_code == 200
    assert 'href="/c/x"' not in cl.get('/library').text and 'href="/c/ranking"' in cl.get('/library').text
    assert 'x' not in {n['id'] for n in cl.get('/graph.json').json()['nodes']}
    for name, said in (('y', 'y'), ('z', 'z is a letter for a value.')):
        with pytest.raises(ValueError, match='not the name of an idea'): lr.put(name, said, 'code')
    assert lr.put('C', 'C is a compiled systems language.', 'code').name == 'C' and lr.put('Bias', 'x', 'ml').name == 'Bias'
    lib, ids = cl.get('/library').text, {n['id'] for n in cl.get('/graph.json').json()['nodes']}
    assert 'href="/c/c"' in lib and 'c' in ids   # an idea named with one capital letter is listed
    assert 'href="/c/bias"' not in lib and 'bias' not in ids   # a statement of one word is not listed
