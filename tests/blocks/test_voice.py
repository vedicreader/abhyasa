"Continuous dictation: segments in, text out in order over server-sent events."
import json
from abhyasa.blocks.voice.app import hint_for

def events(cl, did):
    with cl.stream('GET', f'/voice/events/{did}') as r:
        assert r.headers['content-type'].startswith('text/event-stream')
        return [json.loads(l[5:]) for l in r.iter_lines() if l.startswith('data:')]

def test_segments_stream_in_order(mk):
    cl = mk(['voice'])
    st = cl.post('/voice/start?concept=reciprocal-rank-fusion').json()
    did = st['id']
    assert st['segment'] is True
    for seq, body in ((2, b'cc'), (0, b'a'), (1, b'bbbb'), (1, b'bbbb')):   # out of order, and one sent two times
        assert cl.post(f'/voice/seg/{did}?seq={seq}', content=body).json()['ok']
    cl.post(f'/voice/stop/{did}?n=3')
    out = events(cl, did)
    assert [o.get('seq') for o in out] == [0, 1, 2, None] and out[-1] == dict(done=True)
    assert out[0]['text'] == '1 bytes about Reciprocal rank fusion, Ranking'   # the hint: the name and the prerequisite
    assert out[1]['text'].startswith('4 bytes')
    assert cl.get(f'/voice/events/{did}').status_code == 404                   # a finished dictation is gone

def test_unknown_dictation(mk):
    cl = mk(['voice'])
    assert cl.post('/voice/seg/nope?seq=0', content=b'x').status_code == 404
    assert cl.post('/voice/stop/nope?n=0').status_code == 404

def test_empty_dictation_ends(mk):
    cl = mk(['voice'])
    did = cl.post('/voice/start').json()['id']
    cl.post(f'/voice/stop/{did}?n=0')
    assert events(cl, did) == [dict(done=True)]

def test_hint_has_iast_terms(lr):
    lr.put('Anumana', 'Inference: the hetu proves the sādhya, as in Nyāya.', 'darshana', aliases=['anumāna'])
    h = hint_for(lr, 'anumana')
    assert h.startswith('Anumana, anumāna') and 'sādhya' in h and 'Nyāya' in h and 'hetu' not in h
    assert hint_for(lr, '') == '' and hint_for(lr, 'nope') == ''

def test_mic_button_assets(mk):
    cl = mk()
    sid = cl.post('/start', follow_redirects=False).headers['location'].split('/')[-1]
    page = cl.get(f'/s/{sid}').text
    assert 'data-vad="/assets/vad.js?v=' in page and '/assets/voice.css?v=' in page and 'data-concept="ranking"' in page
    assert 'registerProcessor' in cl.get('/assets/vad.js').text
