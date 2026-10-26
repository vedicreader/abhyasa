from abhyasa.ground import index_ramabana
import json

def test_viewer_shows_a_session_and_its_resume_command(mk, lr, tmp_path):
    (tmp_path/'agent-history.jsonl').write_text(json.dumps(dict(session='agent_1', at=1., prompt='why does rrf use ranks', reply='Scores differ in scale.', model='m')))
    index_ramabana(lr.vault, tmp_path)
    doc_id = lr.vault.shelf('ramabana').t.docs()[0]['id']
    t = mk(['vault']).get(f'/v/ramabana/{doc_id}').text
    assert 'why does rrf use ranks' in t and 'Scores differ in scale' in t
    assert 'ramabana --resume agent_1' in t and 'Learn from this' in t

def test_viewer_learns_concepts_from_a_document(mk, lr, tmp_path):
    (tmp_path/'agent-history.jsonl').write_text(json.dumps(dict(session='agent_2', at=1., prompt='what is a rank', reply='A position in a list.', model='m')))
    index_ramabana(lr.vault, tmp_path)
    doc_id = lr.vault.shelf('ramabana').t.docs()[0]['id']
    t = mk(['vault']).post(f'/v/ramabana/{doc_id}/learn').text
    assert '/c/rank' in t
    assert lr.concept('rank').provenance[0]['src'] == 'vault:ramabana'

def test_viewer_refuses_unknown_or_unsafe(mk):
    cl = mk(['vault'])
    assert 'No such document' in cl.get('/v/ramabana/nope').text
    assert 'No such document' in cl.get('/v/bad;name/x').text
