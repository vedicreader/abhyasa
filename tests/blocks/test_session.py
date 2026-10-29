import re

def start(cl, **data):
    r = cl.post('/start', data=data, follow_redirects=False)
    return r.headers['location'].split('/')[-1]

def test_struggle_then_pass(mk):
    cl = mk()
    sid = start(cl)
    page = cl.get(f'/s/{sid}').text
    assert 'What does a rank tell you?' in page and 'Its position' not in page   # the model answer stays hidden
    assert 'Ranking' in page                                                      # rrf waits for its prereq
    assert 'Not yet' in cl.post(f'/s/{sid}/answer', data=dict(answer='a score', confidence=70)).text
    assert 'Think about positions' in cl.post(f'/s/{sid}/hint').text
    r = cl.post(f'/s/{sid}/answer', data=dict(answer='its rank position', confidence=70)).text
    assert 'Right, but shaky' in r
    assert 'What does a rank tell you?' in cl.post(f'/s/{sid}/next').text        # fetched ahead

def test_shaky_pass_can_ask_for_a_lesson(mk, lr):
    "A shaky pass offers 'Teach me this'; the lesson comes on request and the outcome stays."
    import re, json
    cl = mk()
    sid = start(cl)
    cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/answer', data=dict(answer='a score', confidence=70))
    r = cl.post(f'/s/{sid}/answer', data=dict(answer='its rank position', confidence=70)).text
    assert 'Right, but shaky' in r and 'Teach me this' in r and 'floor unseen' not in r
    assert 'Not at a level yet. Next review' in r
    qid = json.loads(re.search(r'hx-vals=\'([^\']+)\'', r)[1])['qid']
    before = dict(lr.concept('ranking'))
    t = cl.post(f'/s/{sid}/teach', data=dict(qid=qid)).text
    assert 'Lesson' in t and 'Teach me this' not in t
    assert dict(lr.concept('ranking')) == before
    assert cl.post(f'/s/{sid}/teach', data=dict(qid='nope')).status_code == 204
    page = cl.get(f'/s/{sid}?q={qid}').text                         # the page drawn again: the lesson once, no old button
    assert page.count('Teach me this') == 0 and page.count('class="lesson"') == 1 and page.count('Another way') == 1

def test_another_way_after_a_lesson(mk):
    "A lesson after a miss offers 'Another way'; it writes a new lesson and offers one more."
    import re, json
    cl = mk()
    sid = start(cl)
    page = cl.get(f'/s/{sid}').text
    assert 'class="way"' in page                                      # the question says its method
    r = cl.post(f'/s/{sid}/giveup', data=dict(dont_know=1)).text
    assert 'Another way' in r
    qid = json.loads(re.search(r'hx-vals=\'([^\']+another[^\']+)\'', r)[1])['qid']
    t = cl.post(f'/s/{sid}/teach', data=dict(qid=qid, another=1)).text
    assert 'Lesson' in t and 'Another way' in t

def test_no_confidence_counts_the_answer_only(mk):
    "An untouched picker (or a spoken answer) sends no confidence; a clean pass is then solid."
    cl = mk()
    sid = start(cl)
    page = cl.get(f'/s/{sid}').text
    assert 'checked' not in page.split('id="conf"')[1].split('</div>')[0]
    assert 'Solid' in cl.post(f'/s/{sid}/answer', data=dict(answer='its rank position')).text

def test_dont_know_teaches(mk):
    cl = mk()
    sid = start(cl)
    cl.get(f'/s/{sid}')
    r = cl.post(f'/s/{sid}/giveup', data=dict(dont_know=1)).text
    assert 'A gap' in r and 'Check:' in r

def test_focus_and_end(mk, lr):
    cl = mk()
    lr.update('ranking', floor=3)
    sid = start(cl, focus='reciprocal-rank-fusion')
    assert 'Reciprocal rank fusion' in cl.get(f'/s/{sid}').text
    assert 'This session is over' not in cl.get(f'/s/{sid}/end').text
    assert cl.get(f'/s/{sid}', follow_redirects=False).status_code in (302, 303)

def test_today_and_concept_hooks(mk):
    cl = mk()
    today = cl.get('/').text
    assert re.search(r'Next: \w+ Ranking\.', today) and 'action="/start"' in today and '>Subjects<' not in today   # the subjects are on Your learning
    c = cl.get('/c/ranking').text
    assert 'Learn this' in c and 'See in the graph' in c

def test_mic_on_card_from_voice_block(mk):
    cl = mk()
    sid = start(cl)
    assert 'abhyasaMic' in cl.get(f'/s/{sid}').text
    cl2 = mk(names=['concepts', 'session', 'today'])   # without the voice block: no mic, nothing breaks
    sid = start(cl2)
    assert 'abhyasaMic' not in cl2.get(f'/s/{sid}').text

def test_feedback_cites_sources_after_close(mk):
    cl = mk()
    sid = start(cl)
    assert 'My ranking notes' not in cl.get(f'/s/{sid}').text          # hidden while you work
    r = cl.post(f'/s/{sid}/answer', data=dict(answer='its rank position', confidence=80)).text
    assert 'From your sources' in r and 'My ranking notes' in r

def test_chat_keeps_each_turn_in_order(mk):
    cl = mk()
    sid = start(cl)
    cl.get(f'/s/{sid}')
    r1 = cl.post(f'/s/{sid}/answer', data=dict(answer='add the scores', thinking='they are numbers', confidence=70)).text
    assert 'add the scores' in r1 and 'Not yet' in r1 and 'First error' in r1
    assert 'id="left"' in r1 and 'Two more tries' in r1 and 'Teach me' in r1    # the composer learns the tries left, by oob swaps
    h1 = cl.post(f'/s/{sid}/hint').text
    cl.post(f'/s/{sid}/answer', data=dict(answer='scale them first', confidence=50))
    h2 = cl.post(f'/s/{sid}/hint').text
    assert 'Hint 1' in h1 and 'Hint 2' in h2
    r3 = cl.post(f'/s/{sid}/answer', data=dict(answer='the rank position', confidence=90)).text
    assert 'Right, but shaky' in r3 and 'id="composer"' in r3 and 'hx-swap-oob' in r3   # the composer now holds Next
    page = cl.get(f'/s/{sid}').text                    # a reload shows one question: the next one; the closed one is in the list
    assert page.count('class="check qa"') == 1 and 'Earlier questions · 1' in page and 'add the scores' not in page
    import re
    old = re.search(r'href="(/s/[^"?]+\?q=[0-9a-f]+)"', page).group(1)
    view = cl.get(old).text                            # the closed question opens read only, its turns in order
    assert 'Right, but shaky' in view.split('id="chat"')[0]   # the list shows each outcome
    view = view.split('id="chat"')[1]
    order = ['add the scores', 'Not yet', 'Hint 1', 'scale them first', 'Hint 2', 'the rank position', 'Right, but shaky']
    at = [view.index(x) for x in order]
    assert at == sorted(at), dict(zip(order, at))
    assert view.count('class="m you"') == 3 and view.count('class="m tutor fb no"') == 2
    assert 'Back to the current question' in view and 'id="composer"></div>' in view   # no composer on a past question

def test_follow_up_only_and_composer_empties(mk, fake):
    cl = mk()
    sid = start(cl)
    cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/answer', data=dict(answer='add the scores', confidence=70))
    cl.post(f'/s/{sid}/answer', data=dict(answer='then sort them', confidence=70))
    p = [c[0] for c in fake.calls if 'You grade' in c[1]][-1]
    assert p.index('Learner: add the scores') < p.index("Learner's answer: then sort them")   # the thread, then only the follow-up
    page = cl.get(f'/s/{sid}').text
    composer = page[page.index('id="composer"'):]
    assert 'then sort them' not in composer           # the message is in the chat, not in the box

def test_next_twice_does_not_repeat(mk):
    cl = mk()
    sid = start(cl)
    cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/answer', data=dict(answer='the rank position', confidence=90))
    assert 'class="check qa"' in cl.post(f'/s/{sid}/next').text
    assert cl.post(f'/s/{sid}/next').status_code == 204
    assert cl.post(f'/s/{sid}/hint').status_code in (200, 204)

def test_viewer_shows_the_conversation_of_an_attempt(mk, lr):
    import json
    cl = mk()
    sid = start(cl)
    cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/answer', data=dict(answer='add the scores', confidence=70))
    cl.post(f'/s/{sid}/answer', data=dict(answer='the rank position', confidence=70))
    final = next(r for r in lr._docs('attempt') if json.loads(r['meta']).get('final'))
    t = cl.get(f"/v/learning/{final['id']}").text
    assert 'The conversation' in t and t.index('add the scores') < t.index('the rank position')

def test_choice_options_sit_in_the_question(mk, lr, fake):
    import random
    random.seed(0)
    fake.dflt = dict(question='Which keeps its scale?', options=[dict(text='the rank', misconception=''),
                     dict(text='the raw score', misconception='scores are comparable')], correct=0, answer='', rubric=[])
    lr.update('ranking', floor=0, ceiling=2)
    cl = mk()
    sid = start(cl, focus='ranking')
    page = cl.get(f'/s/{sid}').text
    assert 'class="opt"' in page and 'id="ans"' not in page and 'id="think"' in page   # options in the chat; the composer keeps thinking
    wrong = page.split('the raw score')[0].rsplit('value="', 1)[1].split('"')[0]
    right = str(1 - int(wrong))
    r = cl.post(f'/s/{sid}/answer', data=dict(answer=wrong, confidence=50)).text
    assert 'class="opt tried"' in r and 'Not yet' in r
    r = cl.post(f'/s/{sid}/answer', data=dict(answer=right, confidence=50)).text
    assert 'class="opt right"' in r and 'disabled' in r

def test_teach_me_after_a_near_try_is_shaky(mk, fake, lr):
    "A try graded 8 is the best try: 'Teach me.' closes as shaky with a lesson, not as a miss, and the concept keeps its ceiling."
    fake.rules['You grade one answer'] = dict(correct=False, grade=8, first_error='You name no method.', misconception='', feedback='Say it in words.')
    cl = mk()
    sid = start(cl)
    cl.get(f'/s/{sid}')
    assert 'Not yet' in cl.post(f'/s/{sid}/answer', data=dict(answer='x1 w1 + b, so z = b', confidence=70)).text
    r = cl.post(f'/s/{sid}/giveup').text
    assert 'Right, but shaky' in r and 'Lesson' in r and 'A gap' not in r
    c = lr.concept('ranking')
    assert (c.ceiling, c.misses) == (6, 0)

def test_your_answer_shows_markdown_and_math(mk):
    "The YOU bubble uses the same renderer as the tutor: dollar maths becomes a maths carrier, and raw HTML cannot run."
    cl = mk()
    sid = start(cl)
    cl.get(f'/s/{sid}')
    data = dict(answer=r'$z = 2\cdot4 + 1$ <img src=x onerror="alert(1)">', thinking='I add `b` first. <script>alert(2)</script>', confidence=50)
    for html in (cl.post(f'/s/{sid}/answer', data=data).text, cl.get(f'/s/{sid}').text):   # as sent, and drawn again from the thread
        assert 'class="md said"' in html and r'<span class="math inline">z = 2\cdot4 + 1</span>' in html
        assert '<code>b</code>' in html and 'onerror' not in html and 'alert(2)</script>' not in html

def test_text_cannot_make_the_page_fetch(mk, fake):
    "A relative, protocol-relative or remote URL in the question or in your answer makes no request: no src, no href."
    bad = '![](/s/start?subject=x) [x](//evil.com) ![t](https://tracker.example/p.png)'
    fake.dflt = dict(question=f'What does a rank tell you? {bad}', answer='Its position.', rubric=['position'])
    cl = mk()
    sid = start(cl)
    cl.get(f'/s/{sid}')
    for html in (cl.post(f'/s/{sid}/answer', data=dict(answer=f'a score {bad}', confidence=50)).text, cl.get(f'/s/{sid}').text):
        assert 'subject=x' not in html and 'evil.com' not in html and 'tracker.example' not in html
    assert '<img alt="t">' in html

class VaultNotes:
    "A source with one passage in a vault document, and one in vedicreader."
    name = 'vault'
    def search(self, q, k=4):
        from abhyasa.ground import passage
        return [passage('vault:store', 'd1#3', 'Rasi Characteristics', 'Ranking orders items by score.', url='/tmp/rasi.pdf'),
                passage('vedicreader', 'ashtadhyayi:1', 'Ashtadhyayi 1 2 · 1.2.63', 'Ranking orders a list of verses.')]

def test_vault_source_opens_in_the_side_pane(lr, fake):
    "A link to a vault document under a lesson opens the side pane; it is still a real link to a new tab. A vedicreader passage stays text."
    from starlette.testclient import TestClient
    from abhyasa.app import mk_app
    cl = TestClient(mk_app(lr, fake, sources=[VaultNotes()], hosts=('testserver',)))
    sid = start(cl)
    cl.get(f'/s/{sid}')   # the page waits for the question that is fetched ahead
    r = cl.post(f'/s/{sid}/answer', data=dict(answer='its rank position', confidence=80)).text
    a = re.search(r'<a [^>]*>Rasi Characteristics</a>', r).group(0)
    assert 'href="/v/store/d1"' in a and 'data-pane="/v/store/d1?pane=1"' in a and 'target="_blank"' in a and 'data-title="Rasi Characteristics"' in a
    assert 'Ashtadhyayi 1 2 · 1.2.63' in r and not re.search(r'<a [^>]*>Ashtadhyayi', r)

def test_composer_boxes_keep_a_draft_by_question(mk):
    "The boxes of the composer are empty, and the form names the question, so core.js can keep a draft of each box."
    import re
    cl = mk(); sid = start(cl)
    cl.get(f'/s/{sid}')
    cl.post(f'/s/{sid}/answer', data=dict(answer='add the scores', thinking='they look alike', confidence=70))
    page = cl.get(f'/s/{sid}').text
    composer = page[page.rindex('<form', 0, page.index('id="composer"')):]
    assert re.search(r'data-qid="[^"]+"', composer.split('>')[0])
    for k in ('ans', 'think'):
        m = re.search(rf'(<textarea[^>]*id="{k}"[^>]*>)(.*?)</textarea>', composer, re.S)
        assert m and m[2] == '' and 'data-draft' in m[1], k
    assert 'add the scores' not in composer and 'they look alike' not in composer

def test_session_question_survives_a_restart(mk, lr):
    cl = mk(); sid = start(cl)
    cl.get(f'/s/{sid}')
    assert 'Not yet' in cl.post(f'/s/{sid}/answer', data=dict(answer='a score', confidence=70)).text
    assert 'Think about positions' in cl.post(f'/s/{sid}/hint').text
    cl2 = mk()                                                                      # a restart: a new app on the same vault
    page = cl2.get(f'/s/{sid}').text
    assert 'What does a rank tell you?' in page and 'Think about positions' in page and 'Its position' not in page
    r = cl2.post(f'/s/{sid}/answer', data=dict(answer='its rank position', confidence=70)).text
    assert 'Right, but shaky' in r                                                  # the wrong try and the hint still count

def test_second_answer_to_a_closed_question_is_204(mk, fake):
    import threading, time, pytest
    from conftest import grader
    def slow(p, sp): time.sleep(.2); return grader(p, sp)
    fake.rules['You grade one answer'] = slow
    cl = mk(); sid = start(cl); cl.get(f'/s/{sid}')
    out = []
    def send(): out.append(cl.post(f'/s/{sid}/answer', data=dict(answer='its rank position', confidence=70)).status_code)
    ts = [threading.Thread(target=send) for _ in range(2)]
    for t in ts: t.start()
    for t in ts: t.join()
    assert sorted(out) == [200, 204], out                                           # the second caller finds it closed

def test_other_key_errors_are_not_hidden(mk, fake):
    import pytest
    def broken(p, sp): raise KeyError('a bug in the grader')
    fake.rules['You grade one answer'] = broken
    cl = mk(); sid = start(cl); cl.get(f'/s/{sid}')
    with pytest.raises(KeyError): cl.post(f'/s/{sid}/answer', data=dict(answer='x'))   # only a closed question gives 204
