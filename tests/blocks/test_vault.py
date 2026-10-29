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

PNG = b'\x89PNG\r\n\x1a\n'

def rasi(lr):
    "A PDF document with four image links: one in its assets folder, one not there, one of another document, one not an image."
    text = ('Aries is a fire sign.\n\n![Image 1 from page 2](images/page2_1.png)\n\n![Image 2 from page 2](images/page2_2.png)\n\n'
            '![Other](../attention/images/fig2.png)\n\n![Notes](images/notes.txt)')
    d = lr.vault.add([(2, text)], 'Rasi Characteristics', source='/tmp/vr/Rasi-Characteristics.pdf', kind='pdf')['doc_id']
    for f, b in (('Rasi-Characteristics/images/page2_1.png', PNG), ('Rasi-Characteristics/images/notes.txt', b'x'), ('attention/images/fig2.png', PNG)):
        p = lr.vault.assets()/f; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b)
    return d

def test_document_shows_its_images(mk, lr):
    "An image link that is in the assets folder of the document is an image from the app; the others are left out, with no empty image."
    import re
    d = rasi(lr)
    t = mk(['vault']).get(f'/v/store/{d}').text
    assert re.findall(r'<img [^>]*>', t) == [f'<img src="/v/store/{d}/img?f=images/page2_1.png" alt="Image 1 from page 2">']
    assert 'Image 2 from page 2' not in t and 'Other' not in t and 'Aries is a fire sign' in t

def test_document_image_route_is_safe(mk, lr, monkeypatch):
    "The image route sends only an image of that document, from its assets folder, under the size cap."
    d = rasi(lr)
    cl = mk(['vault'])
    r = cl.get(f'/v/store/{d}/img?f=images/page2_1.png')
    assert r.status_code == 200 and r.content == PNG and r.headers['content-type'] == 'image/png'
    for bad in ('images/page2_2.png', 'images/notes.txt', '../attention/images/fig2.png', '..%2Fattention%2Fimages%2Ffig2.png',
                '%2Fetc%2Fhosts', '../../../../etc/hosts', 'images/../../attention/images/fig2.png'):
        assert cl.get(f'/v/store/{d}/img?f={bad}').status_code == 404, bad
    assert cl.get(f'/v/store/{d}/img').status_code == 404
    assert cl.get('/v/store/nope/img?f=images/page2_1.png').status_code == 404
    assert cl.get(f'/v/bad;name/{d}/img?f=images/page2_1.png').status_code == 404
    monkeypatch.setattr('abhyasa.blocks.vault.app.IMG_MAX', 4)
    assert cl.get(f'/v/store/{d}/img?f=images/page2_1.png').status_code == 404   # larger than the cap
