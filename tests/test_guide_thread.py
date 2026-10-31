"The thread of a page, in a headless browser: a follow-up question sends the last questions of the page, and Start fresh, a new page or 10 minutes with no question clear them."
import pytest
from test_board_js import _chromium
from test_guide_page import page, sse

pytestmark = pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")

def board(*says, tier='tutor'):
    return dict(board=dict(tier=tier, steps=[dict(say=s, strokes=[dict(op='box', at='passage')]) for s in says], sources=[], end="In the tutor's own words. No source found."))

def ask(page, said):
    "Ask `said`, and wait until its body is posted and its board came."
    n = len(page.asked)
    page.evaluate("s => { abhyasaGuideQuiet = true; return abhyasaGuide.ask(s); }", said)
    assert len(page.asked) == n + 1
    return page.asked[-1]

line = lambda page: page.evaluate("(() => { const p = document.querySelector('#guide-form .guide-thread'); return p.hidden ? null : p.querySelector('.guide-thread-said').textContent; })()")

def test_a_second_question_sends_the_first_in_its_thread(page):
    "The first body has no thread. The second has the first question with the lines of its board and its tier; the third has both, the oldest first."
    page.reply = sse(board('Alpha bar is the share that is left.', 'It falls as t grows.'))
    assert 'thread' not in ask(page, "I don't get alpha bar")
    page.reply = sse(board('Less and less of the picture stays.', tier='vault'))
    assert ask(page, 'say that more simply')['thread'] == [dict(said="I don't get alpha bar", says=['Alpha bar is the share that is left.', 'It falls as t grows.'], t='tutor')]
    assert [t['said'] for t in ask(page, 'why?')['thread']] == ["I don't get alpha bar", 'say that more simply']
    assert page.asked[-1]['thread'][1]['t'] == 'vault'

def test_the_thread_keeps_the_last_three_turns(page):
    page.reply = sse(board('A line.'))
    for k in range(5): ask(page, f'question {k}')
    assert [t['said'] for t in page.asked[-1]['thread']] == ['question 1', 'question 2', 'question 3']
    assert [t['said'] for t in page.evaluate('abhyasaGuide.thread()')] == ['question 2', 'question 3', 'question 4']

def test_start_fresh_clears_the_thread(page):
    "The box shows the last question under it, with × Start fresh. A click clears the thread, hides the line and keeps the box in focus."
    page.reply = sse(board('Alpha bar is the share that is left.'))
    ask(page, "I don't get alpha bar")
    page.evaluate('abhyasaGuide.open()')
    assert line(page) == "Follows up on: I don't get alpha bar"
    assert page.get_attribute('#guide-form .guide-fresh', 'aria-label') == 'Start fresh'
    page.click('#guide-form .guide-fresh')
    assert line(page) is None and page.evaluate('abhyasaGuide.thread()') == []
    assert page.evaluate("document.activeElement.id") == 'guide-box' and page.is_visible('#guide-form')
    assert 'thread' not in ask(page, 'say that more simply')

def test_a_question_with_no_board_adds_no_turn(page):
    page.reply = sse(dict(error='The tutor could not answer. Try again.'))
    ask(page, "I don't get alpha bar")
    page.evaluate('abhyasaGuide.open()')
    assert page.evaluate('abhyasaGuide.thread()') == [] and line(page) is None

def test_a_new_page_clears_the_thread(page):
    "A link of the app swaps the main page (hx-boost): the next question has no thread, and the box shows no line."
    page.reply = sse(board('Alpha bar is the share that is left.'))
    ask(page, "I don't get alpha bar")
    page.evaluate("document.querySelector('nav a.nav-search').click()")   # a boosted link; at this width the pane hides it
    page.wait_for_function("location.pathname === '/search' && !document.querySelector('#passage')")
    assert page.evaluate('window.abhyasaGuide.thread()') == []   # the same script: the page did not load again
    page.evaluate('abhyasaGuide.open()')
    assert line(page) is None
    page.keyboard.press('Escape')
    assert 'thread' not in ask(page, 'say that more simply')

def test_ten_minutes_with_no_question_clear_the_thread(page):
    page.reply = sse(board('Alpha bar is the share that is left.'))
    ask(page, "I don't get alpha bar")
    page.evaluate("(() => { const now = Date.now.bind(Date), at = now(); Date.now = () => now() + 9 * 60000; })()")
    assert len(page.evaluate('abhyasaGuide.thread()')) == 1   # 9 minutes: it stays
    page.evaluate("(() => { const now = Date.now; Date.now = () => now() + 2 * 60000; })()")
    assert page.evaluate('abhyasaGuide.thread()') == []
