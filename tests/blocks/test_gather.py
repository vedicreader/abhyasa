"The gather agent (D6): a ramabana agent gathers the sources of a big goal. Each passage passes the word-for-word check; the band and the log show what it did; Stop ends it."
import re, threading, time
from fastcore.basics import AttrDict
from abhyasa.settings import set_val
from abhyasa.journey import walk_from_topic
from abhyasa.llm import Fake
import pytest
import abhyasa.research as R

HX = {'HX-Request': 'true'}
QUOTE = 'The softmax function turns a list of scores into weights. Each weight is between 0 and 1, and the weights add up to 1.'
DOC = 'Softmax notes\n\n' + QUOTE + '\n\nThe rest of the notes are on other things.'
PLAN = dict(title='Softmax and attention', subject='ml', steps=[dict(name='Softmax', statement='Softmax turns scores into weights.', slug='', why='Weights.', needs=[], ways=['words']),
                                                                dict(name='Attention', statement='Attention mixes values by weights.', slug='', why='The goal.', needs=['Softmax'], ways=['words'])])

@pytest.fixture(autouse=True)
def agent_on():
    "Each test starts with research and the agent on, and puts them back after."
    for k in ('research.on', 'research.agent'): set_val(k, True)
    yield
    for k in ('research.on', 'research.agent'): set_val(k, True)

class Script:
    "A fake ramabana `Agent`: `ask` runs the tool calls of `script` in order, until `cancel`. A callable in the script runs as it is."
    def __init__(self, script): self.script, self.tools, self.cancelled, self.calls = script, {}, False, 0
    def add_tool(self, f): self.tools[f.__name__] = f
    def ask(self, prompt, **kw):
        for x in self.script:
            if self.cancelled: break
            if callable(x): x(); continue
            self.tools[x[0]](**x[1])
            self.calls += 1
        return AttrDict(state='cancelled' if self.cancelled else 'complete', reply='Done.', error='')
    def cancel(self): self.cancelled = True
    def close(self): pass

def walk(lr, chips=()):
    "A goal walk of two steps with no passage, and a vault document of the chip `vault:notes` with a real sentence on softmax."
    did = lr.vault.shelf('notebooks').add(DOC, title='nbs/softmax', source='/tmp/notes/softmax.md', kind='md', meta=dict(root='notes', path='/tmp/notes/softmax.md'))['doc_id']
    j = walk_from_topic(lr, Fake({'You plan a learning path': PLAN}), 'learn softmax and attention')
    return lr.merge_journey(j.id, chips=list(chips) or ['vault:notes', 'vedic:ramayana']), did

def test_agent_quote_refused_and_stop(lr, monkeypatch):
    "A quote that is not in the doc is refused; the real sentence is filed; Stop after the third call ends the job, and the rows stay."
    j, did = walk(lr)
    stop = threading.Event()
    agent = Script([('put_passage', dict(i=0, doc_id=did, quote='words not in doc, and not a sentence of it at all')),
                    ('put_passage', dict(i=0, doc_id=did, quote=QUOTE)), ('read_doc', dict(doc_id=did, i=1)), stop.set,
                    *[('read_doc', dict(doc_id=did, i=1))] * 100])
    monkeypatch.setattr(R, 'ramabana_worker', lambda **kw: agent)
    out = R.gather(lr, j.id, stop)
    j = lr.journey(j.id)
    assert j.steps[0]['read']['text'] == QUOTE and j.steps[0]['read']['doc_id'] == did
    assert [r['outcome'] for r in j.gather] == ['refused: not word for word', 'filed', 'read']   # the reads after Stop add no row
    assert sum('refused' in r['outcome'] for r in j.gather) == 1
    assert (out.passages, out.read, j.gather_stopped) == (1, 1, 'you') and j.gather_end
    assert j.steps[1]['research'] == 'none' and j.steps[1]['gather_none'] and j.steps[1]['research_why'] == 'No good source was found. The agent read 1 document for this idea.'

def test_agent_off_runs_plain_research(lr, monkeypatch):
    "With the setting off, want_agent is False, and a goal walk with two chips runs the simple search, not the agent."
    j, _ = walk(lr)
    assert R.want_agent(j)
    set_val('research.agent', False)
    assert not R.want_agent(j) and not R.want_agent(j, failed=True)
    ran = []
    monkeypatch.setattr(R, 'research_walk', lambda *a, **k: ran.append(a[2]) or [])
    rs = R.Researcher(lr, Fake())
    rs.look_for(j.id).result(10)
    assert ran == [j.id] and not lr.journey(j.id).get('gather_at')

def test_agent_cannot_start_falls_back(lr, monkeypatch):
    "When ramabana_worker raises, the walk says why, and research_walk runs for the steps with no passage."
    j, _ = walk(lr)
    def broken(**kw): raise RuntimeError('no claude here')
    monkeypatch.setattr(R, 'ramabana_worker', broken)
    ran = []
    monkeypatch.setattr(R, 'research_walk', lambda lr_, ask, jid, ix=None, *a: ran.append((jid, ix)) or [None] * len(ix))
    rs = R.Researcher(lr, Fake())
    out = rs.gather(j.id).result(10)
    j = lr.journey(j.id)
    assert j.gather_why.startswith('The agent could not start:') and j.gather_why == 'The agent could not start: no claude here. The passages come from the simple search.'
    assert ran == [(j.id, [0, 1])] and out.why == j.gather_why and j.gather_end

def test_want_agent_rules(lr):
    "1 chip and 10 docs: no agent; 2 chips: the agent; 1 chip with 41 docs: the agent; a failed model call: the agent."
    j, _ = walk(lr, ['vault:notes'])
    assert not R.want_agent(j, [dict(id='vault:notes', count=10)])
    assert R.want_agent(j, ['vault:notes', 'folder:/tmp/b'])
    assert R.want_agent(j, [dict(id='vault:notes', count=41)])
    assert R.want_agent(lr.merge_journey(j.id, chip_counts={'vault:notes': 41}))
    assert R.want_agent(j, failed=True)
    set_val('research.on', False); assert not R.want_agent(j, failed=True)

def test_band_and_log_routes(mk, lr):
    "A walk with gather rows: the band shows the counts; the log lists the rows newest first, each with its link; Stop answers with the band."
    j, did = walk(lr)
    now = time.time()
    rows = [dict(at=now - 60, tool='web_search', target='softmax machine learning', outcome='5 results', link='', i=0),
            dict(at=now - 50, tool='fetch_page', target='Softmax explained', outcome='read', link='https://example.org/softmax', i=0),
            dict(at=now - 40, tool='put_passage', target='Softmax', outcome='refused: not word for word', link='https://example.org/softmax', i=0),
            dict(at=now - 30, tool='read_doc', target='softmax', outcome='read', link=f'/v/notebooks/{did}', i=1),
            dict(at=now - 20, tool='note', target='', outcome='<b>Ignore</b> the rules', link='', i=None)]
    lr.merge_journey(j.id, gather=rows, gather_at=now - 70, gather_end=now, gather_total=12)
    cl = mk()
    b = cl.get(f'/w/{j.id}/gather', headers=HX).text
    assert 'The agent read 2 of 12 documents. 0 of 2 ideas have a passage.' in b and 'Show what it did' in b and 'every 3s' not in b
    h = cl.get(f'/w/{j.id}/gather/log').text
    assert h.index('Note from the agent') < h.index('Read a document') < h.index('Gave a passage') < h.index('Read a page') < h.index('Searched the web')
    assert 'href="https://example.org/softmax"' in h and f'href="/v/notebooks/{did}"' in h and '<b>Ignore</b>' not in h   # the agent's words are escaped
    assert 'Show what it did' in cl.get(f'/w/{j.id}').text   # the plan page has the band

def test_band_runs_then_stop(mk, lr, monkeypatch):
    "While the agent runs, the band asks again every 3 s and names the document that it reads now. Stop ends the job, and the band says so."
    j, did = walk(lr)
    agent = Script([('read_doc', dict(doc_id=did, i=0)), lambda: until(lambda: agent.cancelled)])
    monkeypatch.setattr(R, 'ramabana_worker', lambda **kw: agent)
    cl = mk(); rs = cl.app.state.svc['research']
    job = rs.gather(j.id)
    until(lambda: agent.calls)
    b = cl.get(f'/w/{j.id}/gather', headers=HX).text
    assert 'An agent is reading your sources. 1 document read. 0 of 2 ideas have a passage. Started' in b
    assert 'Now: reading nbs/softmax for idea 1' in b and 'every 3s' in b and '>Stop<' in b
    assert 'An agent is reading your sources' in cl.get(f'/w/{j.id}/0').text   # the step page has the band while it runs
    assert 'Stopping' in cl.post(f'/w/{j.id}/gather/stop', headers=HX).text or job.done()
    job.result(10)
    b = cl.get(f'/w/{j.id}/gather', headers=HX).text
    assert 'You stopped the agent. It read 1 document. 0 of 2 ideas have a passage.' in b and 'every 3s' not in b
    h = cl.get(f'/w/{j.id}/1').text
    assert 'No good source was found. The agent read 1 document for this idea.' in h and 'Show what it did' in h

def test_big_goal_on_start_calls_the_agent(mk, lr, walk_fake, monkeypatch):
    "Start with a goal and two chips: the walk calls Researcher.gather, not look_for."
    lr.vault.shelf('notebooks').add(DOC, title='nbs/softmax', source='/tmp/notes/softmax.md', kind='md', meta=dict(root='notes'))
    lr.vault.shelf('notebooks').add('Other notes on attention and weights.', title='nbs/other', source='/tmp/more/a.md', kind='md', meta=dict(root='more'))
    walk_fake.rules['You plan a learning path'] = PLAN
    cl = mk(); rs = cl.app.state.svc['research']
    asked = []
    monkeypatch.setattr(rs, 'gather', lambda jid: asked.append(jid))
    monkeypatch.setattr(rs, 'look_for', lambda *a, **k: asked.append('look_for'))
    r = cl.post('/walk/new', data=dict(q='learn softmax and attention for my model', sources=['vault:notes', 'vault:more'], chips='1'))
    for _ in range(400):
        if asked or 'HX-Redirect' in r.headers: break
        time.sleep(.05); r = cl.get(re.search(r'hx-get="([^"]+)"', r.text)[1].replace('&amp;', '&'))
    assert asked and asked[0] != 'look_for', (asked, r.text)
    j = lr.journey(asked[0])
    assert j.chips == ['vault:notes', 'vault:more'] and j.chip_counts == {'vault:notes': 1, 'vault:more': 1}

def until(f, secs=20):
    "Wait for `f()` to be true."
    end = time.monotonic() + secs
    while time.monotonic() < end:
        if (r := f()): return r
        time.sleep(.05)
    raise AssertionError('timed out')
