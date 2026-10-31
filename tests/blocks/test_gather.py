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

class Host:
    "A fake ramabana host: `gather_tools` puts its `read_url`, `web_search` and `read` on it."
    def add_root(self, p, readonly=False): pass

class Script:
    """A fake ramabana `Agent`: `ask` runs the tool calls of `script` in order, until `cancel`. A callable in the script runs as it is.
    A tool that abhyasa does not add is a read of ramabana's host: `fetch_page`, `read_file` and `web_search`."""
    def __init__(self, script): self.script, self.tools, self.cancelled, self.calls, self.host, self.said = script, {}, False, 0, Host(), []
    def add_tool(self, f): self.tools[f.__name__] = f
    def call(self, name, kw):
        "Run one tool call, and keep what it said in `said`."
        if name in self.tools: out = self.tools[name](**kw)
        elif name == 'fetch_page': out = self.host.read_url(kw['url'], idea=kw.get('idea', 0)).text
        elif name == 'read_file': out = self.host.read(kw['file'], idea=kw.get('idea', 0))
        elif name == 'web_search': out = self.host.web_search(kw['query'])
        else: raise KeyError(name)
        self.said.append((name, out))
        return out
    def ask(self, prompt, **kw):
        for x in self.script:
            if self.cancelled: break
            if callable(x): x(); continue
            self.call(*x)
            self.calls += 1
        return AttrDict(state='cancelled' if self.cancelled else 'complete', reply='Done.', error='')
    def cancel(self): self.cancelled = True
    def close(self): pass

def lead(agent, seen=None):
    "A fake `ramabana_lead` that gives `agent` and its host, and keeps what it was asked in `seen`."
    def mk(read_roots=(), tools=(), **kw):
        if seen is not None: seen.update(kw, read_roots=list(read_roots), tools=list(tools))
        return agent, agent.host
    return mk

def walk(lr, chips=()):
    "A goal walk of two steps with no passage, and a vault document of the chip `vault:notes` with a real sentence on softmax."
    did = lr.vault.shelf('notebooks').add(DOC, title='nbs/softmax', source='/tmp/notes/softmax.md', kind='md', meta=dict(root='notes', path='/tmp/notes/softmax.md'))['doc_id']
    j = walk_from_topic(lr, Fake({'You plan a learning path': PLAN}), 'learn softmax and attention')
    return lr.merge_journey(j.id, chips=list(chips) or ['vault:notes', 'vedic:ramayana']), did

def test_agent_quote_refused_and_stop(lr, monkeypatch):
    "A quote that is not in the doc is refused; the real sentence is filed; Stop after the third call ends the job, and the rows stay."
    j, did = walk(lr)
    stop = threading.Event()
    agent = Script([('put_passage', dict(idea=1, doc_id=did, quote='words not in doc, and not a sentence of it at all')),
                    ('put_passage', dict(idea=1, doc_id=did, quote=QUOTE)), ('read_doc', dict(doc_id=did, idea=2)), stop.set,
                    *[('read_doc', dict(doc_id=did, idea=2))] * 100])
    monkeypatch.setattr(R, 'ramabana_lead', lead(agent))
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
    "When ramabana_lead raises, the walk says why, and research_walk runs for the steps with no passage."
    j, _ = walk(lr)
    def broken(*a, **kw): raise RuntimeError('no claude here')
    monkeypatch.setattr(R, 'ramabana_lead', broken)
    ran = []
    monkeypatch.setattr(R, 'research_walk', lambda lr_, ask, jid, ix=None, *a: ran.append((jid, ix)) or [None] * len(ix))
    rs = R.Researcher(lr, Fake())
    out = rs.gather(j.id).result(10)
    j = lr.journey(j.id)
    assert j.gather_why == R.NO_START_ANY and 'no claude here' not in j.gather_why   # no known cause: the general line, with no raw error
    assert ran == [(j.id, [0, 1])] and out.why == j.gather_why and j.gather_end

def test_a_start_that_is_not_signed_in_says_what_to_do(mk, lr, monkeypatch):
    "The Claude command is not signed in: the research line says so in plain words and what to do. The raw error is only in Show what it did."
    j, _ = walk(lr)
    class ClaudeError(Exception): pass
    def not_in(*a, **kw): raise ClaudeError('claude failed: Not logged in')
    monkeypatch.setattr(R, 'ramabana_lead', not_in)
    monkeypatch.setattr(R, 'research_walk', lambda lr_, ask, jid, ix=None, *a: [None] * len(ix))
    R.Researcher(lr, Fake()).gather(j.id).result(10)
    cl = mk()
    b = cl.get(f'/w/{j.id}/gather', headers=HX).text
    assert ('The research agent could not start: the Claude command is not signed in. Run claude in Terminal and sign in, '
            'or pick another model in Settings &gt; Models.') in b
    assert 'ClaudeError' not in b and 'Not logged in' not in b and 'Show what it did' in b
    t = cl.get(f'/w/{j.id}/gather/log').text
    assert 'Could not start the agent' in t and 'ClaudeError: claude failed: Not logged in' in t

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
    rows = [dict(at=now - 60, tool='web_search', target='softmax machine learning', outcome='5 results', link='', idea='softmax'),
            dict(at=now - 50, tool='fetch_page', target='Softmax explained', outcome='read', link='https://example.org/softmax', idea='softmax'),
            dict(at=now - 40, tool='put_passage', target='Softmax', outcome='refused: not word for word', link='https://example.org/softmax', idea='softmax'),
            dict(at=now - 30, tool='read_doc', target='softmax', outcome='read', link=f'/v/notebooks/{did}', idea='attention'),
            dict(at=now - 20, tool='note', target='', outcome='<b>Ignore</b> the rules', link='', idea=None)]
    lr.merge_journey(j.id, gather=rows, gather_at=now - 70, gather_end=now, gather_total=12)
    cl = mk()
    b = cl.get(f'/w/{j.id}/gather', headers=HX).text
    assert '0 of 2 ideas have a source. Research ended at' in b and 'abhyasa left out 1 quote that did not match the source word for word.' in b and 'Show what it did' in b and 'every 3s' not in b
    assert 'Find sources again' in b
    h = cl.get(f'/w/{j.id}/gather/log').text
    assert h.index('Note from the agent') < h.index('Read a document') < h.index('Gave a passage') < h.index('Read a page') < h.index('Searched the web')
    assert 'href="https://example.org/softmax"' in h and f'href="/v/notebooks/{did}"' in h and '<b>Ignore</b>' not in h   # the agent's words are escaped
    assert 'Show what it did' in cl.get(f'/w/{j.id}').text   # the plan page has the band

def test_band_runs_then_stop(mk, lr, monkeypatch):
    "While the agent runs, the band asks again every 3 s and names the document that it reads now. Stop ends the job, and the band says so."
    j, did = walk(lr)
    agent = Script([('read_doc', dict(doc_id=did, idea=1)), lambda: until(lambda: agent.cancelled)])
    monkeypatch.setattr(R, 'ramabana_lead', lead(agent))
    cl = mk(); rs = cl.app.state.svc['research']
    job = rs.gather(j.id)
    until(lambda: lr.journey(j.id).get('gather'))   # the watch writes the rows that wait within 2 s
    b = cl.get(f'/w/{j.id}/gather', headers=HX).text
    assert 'Reads nbs/softmax for idea 1. 0 of 2 ideas have a source.' in b and 'Last step' in b
    assert 'idea 1' in cl.get(f'/w/{j.id}/gather/log').text and 'every 3s' in b and '>Stop<' in b
    assert '0 of 2 ideas have a source' in cl.get(f'/w/{j.id}/0').text   # the step page has the line while it runs
    p = cl.get(f'/w/{j.id}?plan=1').text   # the plan and the line can be reached after the start
    assert 'You can start now.' in p and 'id="gather"' in p
    assert 'Stopping' in cl.post(f'/w/{j.id}/gather/stop', headers=HX).text or job.done()
    job.result(10)
    b = cl.get(f'/w/{j.id}/gather', headers=HX).text
    assert '0 of 2 ideas have a source. You stopped research at' in b and 'every 3s' not in b
    h = cl.get(f'/w/{j.id}/1').text
    assert 'No good source was found. The agent read 0 documents for this idea.' in h and 'Show what it did' in h   # its one read was for idea 1

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

def test_crash_goes_back_to_find_a_source(mk, lr, monkeypatch):
    "When the agent crashes, each step with no passage goes back to Find a source, with a plain reason, and the band says why."
    j, did = walk(lr)
    def boom(): raise RuntimeError('the model process died')
    monkeypatch.setattr(R, 'ramabana_lead', lead(Script([('read_doc', dict(doc_id=did, idea=1)), boom])))
    out = R.gather(lr, j.id, threading.Event())
    assert out.why == 'The agent stopped with an error: the model process died.'
    cl = mk(); cl.post(f'/w/{j.id}/start')
    h = cl.get(f'/w/{j.id}/0').text
    assert R.CRASHED in h and 'Find a source' in h and 'Look again' not in h
    assert 'The agent stopped with an error: the model process died.' in cl.get(f'/w/{j.id}/gather', headers=HX).text

def test_spend_estimated_in_the_log(mk, lr, monkeypatch):
    "When the model gives no cost, the worker estimates it from the tokens, and the log says so."
    j, did = walk(lr)
    agent = Script([('read_doc', dict(doc_id=did, idea=1))]); agent.estimated = 1.234
    monkeypatch.setattr(R, 'ramabana_lead', lead(agent))
    R.gather(lr, j.id, threading.Event())
    assert 'spend estimated: about $1.23' in lr.journey(j.id).gather[-1]['outcome']
    assert 'Spend' in mk().get(f'/w/{j.id}/gather/log').text

def test_worker_names_its_tools(lr, monkeypatch):
    "gather names each tool that it adds when it makes the worker, so ramabana's only_tools offers those tools and no other."
    j, did = walk(lr)
    agent, seen = Script([]), {}
    monkeypatch.setattr(R, 'ramabana_lead', lead(agent, seen))
    R.gather(lr, j.id, threading.Event())
    assert seen['tools'] and sorted(seen['tools']) == sorted(agent.tools)
    assert {'put_passage', 'read_doc', 'note'} <= set(seen['tools'])

def test_reorder_keeps_the_idea(lr, monkeypatch):
    "The learner moves a step while the agent runs: the passage goes to the idea that the agent named, not to the step at its old place."
    j, did = walk(lr)
    agent = Script([lambda: lr.journey_step(j.id, 'softmax', 'down'), ('put_passage', dict(idea=1, doc_id=did, quote=QUOTE))])
    monkeypatch.setattr(R, 'ramabana_lead', lead(agent))
    R.gather(lr, j.id, threading.Event())
    ss = lr.journey(j.id).steps
    assert [s['slug'] for s in ss] == ['attention', 'softmax'] and ss[1]['read']['text'] == QUOTE and not (ss[0].get('read') or {}).get('text')

def test_secret_in_a_local_file_never_leaves(lr, monkeypatch, tmp_path):
    "A fake key in a local file: the model sees it masked, and it never goes out in a query or a link, nor into a log line (the PII gate of ramabana)."
    key = 'sk-test1234567890abcdefghij'
    top = tmp_path/'notes'; top.mkdir()
    monkeypatch.setenv('HOME', str(tmp_path))   # the agent reads only a folder in the home folder
    (top/'keys.md').write_text(f'# Keys\n\nMy key is {key}. Softmax notes for the comic live here too.')
    j, did = walk(lr, [f'folder:{top}', 'vault:notes'])
    sent, said = [], []
    def search(q, n): sent.append(q); return []
    def fetch(u): sent.append(u); raise AssertionError('no fetch')
    agent = Script([('read_file', dict(file='notes/keys.md', idea=1)), ('web_search', dict(query=f'softmax {key}', idea=1)),
                    ('fetch_page', dict(url=f'https://example.org/q?key={key}', idea=1)), ('note', dict(text=f'the key is {key}'))])
    monkeypatch.setattr(R, 'ramabana_lead', lead(agent))
    R.gather(lr, j.id, threading.Event(), search=search, fetch=fetch)
    said = [out for name, out in agent.said if name == 'read_file']
    assert said and key not in said[0] and '[SECRET]' in said[0]
    assert not sent and key not in str(lr.journey(j.id).gather)

def bad_roots(tmp_path, monkeypatch):
    "A temp HOME with a hidden folder `~/.config/app`, and a folder outside HOME, each with a text file on softmax. The chips for them and for /etc."
    home = tmp_path/'home'; cfg = home/'.config'/'app'; out = tmp_path/'outside'
    for d in (cfg, out): d.mkdir(parents=True); (d/'notes.md').write_text(DOC)
    monkeypatch.setenv('HOME', str(home))
    return ['folder:/etc', 'folder:~/.config/app', f'folder:{out}']

def test_agent_reads_no_refused_folder(lr, monkeypatch, tmp_path):
    "A walk that holds chips for /etc, a hidden folder in HOME and a folder outside HOME: read_file refuses each file in them."
    chips = bad_roots(tmp_path, monkeypatch)
    j, did = walk(lr, chips + ['vault:notes'])
    agent = Script([('read_file', dict(file=f, idea=1)) for f in ('etc/afpovertcp.cfg', '/etc/afpovertcp.cfg', 'app/notes.md', 'outside/notes.md')])
    monkeypatch.setattr(R, 'ramabana_lead', lead(agent))
    R.gather(lr, j.id, threading.Event())
    outs = [r['outcome'] for r in lr.journey(j.id).gather if r['tool'] == 'read_file']
    assert len(outs) == 4 and all(o.startswith('refused') for o in outs), outs

def test_prompt_names_no_refused_folder(lr, monkeypatch, tmp_path):
    "An old walk that still holds chips for /etc, a hidden folder and a folder outside HOME: the prompt to the agent names none of them."
    j, _ = walk(lr, bad_roots(tmp_path, monkeypatch) + ['vault:notes'])
    p = R.gather_prompt(lr, lr.journey(j.id))
    assert not any(n in p for n in ('etc', 'app', 'outside')), p

def test_refused_folder_chips_are_not_kept(mk, lr, walk_fake, monkeypatch, tmp_path):
    "Start a goal walk with chips for /etc, a hidden folder in HOME and a folder outside HOME: the walk keeps only the good chip, so gather never sees the others."
    chips = bad_roots(tmp_path, monkeypatch)
    lr.vault.shelf('notebooks').add(DOC, title='nbs/softmax', source='/tmp/notes/softmax.md', kind='md', meta=dict(root='notes'))
    walk_fake.rules['You plan a learning path'] = PLAN
    cl = mk(); rs = cl.app.state.svc['research']
    asked = []
    monkeypatch.setattr(rs, 'gather', lambda jid: asked.append(jid))
    monkeypatch.setattr(rs, 'look_for', lambda jid, *a, **k: asked.append(jid))
    r = cl.post('/walk/new', data=dict(q='learn softmax and attention for my model', sources=chips + ['vault:notes'], chips='1'))
    for _ in range(400):
        if asked or 'HX-Redirect' in r.headers: break
        time.sleep(.05); r = cl.get(re.search(r'hx-get="([^"]+)"', r.text)[1].replace('&amp;', '&'))
    assert 'HX-Redirect' in r.headers or asked, r.text
    assert [j.chips for j in lr.journeys()] == [['vault:notes']]
