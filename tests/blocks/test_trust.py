"Trust (decision 6 of 0.0.13): every passage has one source line with a label, the tutor's words have a dashed rule and no link, and the recap lists each source once."
import re, time
from fasthtml.common import to_xml
from abhyasa.core import SourceLine, TutorWords, Cites, source_of
from abhyasa.llm import Fake
from abhyasa.settings import set_val
from abhyasa.talk import talk_from_walk, new_run, log_go, recap_html, asset_resolver
from talk_data import make_talk, talk_walk, TALK_RULES
from walk_data import walk as paper_walk

WEB = dict(src='web', shelf='store', doc_id='d9', title='Softmax explained', site='example.org', url='https://example.org/softmax',
           text='The softmax function turns a list of scores into weights.', section='', page=None, at=time.time())

def web_walk(lr):
    "A walk with one step whose passage comes from the web; return its id."
    lr.put('Softmax', 'Softmax turns scores into weights.', 'ml')
    return lr.put_journey(dict(id='softmax-web1', title='Softmax', goal='Learn softmax', subject='ml', mode='walk', source=None, started=time.time(),
                               steps=[dict(slug='softmax', status='todo', why='', read=dict(WEB), check=dict(way='words', kind='short', depth=2, why=''))])).id

def topic_walk(lr):
    "A walk with one step that has no passage; return its id."
    return lr.put_journey(dict(id='ranking-t1', title='Ranking', goal='Learn ranking', subject='ml', mode='walk', source=None, started=time.time(),
                               steps=[dict(slug='ranking', status='todo', why='', read=None, check=dict(way='words', kind='short', depth=2, why=''))])).id

def section(h, sel):
    "The element of page `h` with the id in `sel` (`#passage`), up to the next element with an id that the step page has after it."
    i = h.index(f'id="{sel[1:]}"')
    start = h.rindex('<', 0, i)
    return h[start:h.index('id="note"', i)]

def start_run(cl, tid):
    "Start a run of talk `tid`; return the key of the audience window."
    cl.post(f'/t/{tid}/start')
    return re.search(rf'/t/{tid}/audience\?k=([0-9a-f]+)', cl.get(f'/t/{tid}/present').text).group(1)

def recap_of_a_run(lr):
    "The recap file of a run that showed every slide of a talk on the paper. The talk has its own title, so the paper title shows only in the sources."
    t = talk_from_walk(lr, Fake(TALK_RULES), talk_walk(lr))
    t = {**t, 'title': 'A talk on attention'}
    run = new_run(t, now=0.)
    for k, s in enumerate(t['slides'], 1): log_go(run, s['id'], 1, float(k))
    return recap_html(t, run, asset_resolver(lr))

def test_vault_passage_has_your_source_line(mk, lr, walk_fake):
    "A passage of a paper in your vault: the label, the title, the section and the page, and a link to the document."
    cl = mk(); jid = paper_walk(cl, lr); cl.post(f'/w/{jid}/start')
    h = cl.get(f'/w/{jid}/0').text
    assert '>your source<' in h and 'Open in your vault' in h and 'From the paper' not in h
    part = section(h, '#passage')
    assert 'Attention Is All You Need' in part and '<span>section 1 · p. 1</span>' in part and 'data-pane="/v/store/' in part

def test_web_passage_has_from_the_web_line(mk, lr):
    "A passage from the web: the label, the site, the day it was read, and the page in a new tab."
    jid = web_walk(lr)
    h = mk().get(f'/w/{jid}/0').text
    assert '>from the web<' in h and 'Open the page' in h and 'target="_blank"' in h
    part = section(h, '#passage')
    assert '<span>example.org</span>' in part and 'read on ' in part and 'rel="noopener noreferrer"' in part and 'data-pane="/v/store/d9?pane=1"' in part

def test_tutor_text_has_no_link(mk, lr):
    "A step with no passage, with research off: the tutor's words, with the dashed rule and no link."
    set_val('research.on', False)
    try:
        jid = topic_walk(lr)
        h = mk().get(f'/w/{jid}/0').text
    finally: set_val('research.on', True)
    part = section(h, '#passage')
    assert "In the tutor's words" in part and 'class="stated' in part and '<a ' not in part.split('find-source')[0]
    assert 'src-line' not in part

def test_note_and_speaker_note_labels(mk, lr, walk_fake, talk_fake):
    "The tutor note has its label. The presenter window labels the speaker note `Your note`."
    cl = mk(); jid = paper_walk(cl, lr); cl.post(f'/w/{jid}/start')
    n = cl.get(f'/w/{jid}/0/note').text
    assert "The tutor's note" in n and 'class="stated note"' in n
    tid = make_talk(cl, jid); cl.post(f'/t/{tid}/start')
    assert 'Your note' in cl.get(f'/t/{tid}/present').text

def test_room_sees_the_source_line_but_no_link(mk, lr, talk_fake):
    "The audience window shows the label, the title and the place of a passage, with no link."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr)); key = start_run(cl, tid)
    h = cl.get(f'/t/{tid}/audience', params=dict(k=key)).text
    assert '>your source<' in h and 'Open in your vault' not in h and 'class="src-line room"' in h
    assert '/v/store/' not in h

def test_editor_row_names_the_source(mk, lr, talk_fake):
    "The talk editor row names the source of the passage of the slide and links to it."
    cl = mk(); tid = make_talk(cl, paper_walk(cl, lr))
    ed = cl.get(f'/t/{tid}').text
    assert '>your source<' in ed and 'Attention Is All You Need' in ed and 'Open in your vault' in ed

def test_plan_row_shows_the_label(mk, lr, walk_fake):
    "The plan shows the label of the passage of each idea in small type."
    cl = mk(); jid = paper_walk(cl, lr)
    assert '<small class="src-lbl">your source</small>' in cl.get(f'/w/{jid}').text

def test_recap_lists_each_source_once(lr):
    "The recap file ends with one list of sources: each source once, with its places, and still no script."
    html = recap_of_a_run(lr)
    assert html.count('Sources') == 1 and html.count('Attention Is All You Need') == 1
    assert html.rindex('<h2>Sources</h2>') > html.rindex('<blockquote>') and 'section 1' in html and '<script' not in html.lower()

def test_source_line_parts():
    "The line keeps its parts safe: a bad web link is not a link, a cite gets a label pill, and the tutor's words have no link."
    h = to_xml(SourceLine(source_of(dict(WEB, url='javascript:alert(1)', shelf=None, doc_id=None))))
    assert 'javascript' not in h and 'Open the page' not in h and '<span>Softmax explained</span>' in h
    c = to_xml(Cites([dict(title='Notes', src='vault:store', ref='d1'), dict(WEB)]))
    assert c.count('class="pill"') == 2 and '>your source<' in c and '>from the web<' in c
    t = to_xml(TutorWords('A [link](https://example.org) in the words.'))
    assert "In the tutor's words" in t and 'class="stated"' in t
    assert source_of(dict(text='')).label == 'tutor' and SourceLine(None) == ''
