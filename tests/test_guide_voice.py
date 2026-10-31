"The natural voice on a real page, in a headless browser: guide.js asks `/guide/say` for each line, plays it, lights the words at their times, and falls back to the browser voice."
import base64, io, json, wave, pytest
from test_guide_page import page, sse, _chromium   # the page fixture: one headless page of the app, with a fake ask route

pytestmark = pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")

SAY = dict(say='Noise goes in slowly.', strokes=[dict(op='box', at='passage')])

def wav(secs=.2) -> str:
    b = io.BytesIO()
    with wave.open(b, 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(b'\0\0' * int(8000 * secs))
    return base64.b64encode(b.getvalue()).decode()

# No sound in a test: `play` only says that it plays, and ends 0.1 s later. The browser voice has no voices, so it times the words by their letters.
SILENT = """() => { window.played = [];
  HTMLMediaElement.prototype.play = function () { played.push(this.src); setTimeout(() => this.dispatchEvent(new Event('playing')), 10);
                                                  setTimeout(() => this.dispatchEvent(new Event('ended')), 100); return Promise.resolve(); };
  speechSynthesis.getVoices = () => [];
  abhyasaGuide.info.out = {engine: 'pocket', model: 'Pocket TTS', where: 'on this Mac', who: ''}; }"""

def natural(page, reply):
    "The page with the natural voice on, and `/guide/say` answered by `reply(body)` -> (status, json). Return the texts that it asked for."
    asked = []
    def answer(route):
        d = json.loads(route.request.post_data); asked.append(d['text'])
        status, body = reply(d)
        route.fulfill(status=status, content_type='application/json', body=json.dumps(body))
    page.route('**/guide/say', answer)
    page.evaluate(SILENT)
    return asked

def test_the_page_speaks_each_line_with_the_route(page):
    "Each step asks the route for its line. The page plays the audio, lights each word, and the board goes on. The strip names the voice and where it runs."
    asked = natural(page, lambda d: (200, dict(audio=wav(), words=[0, .05, .1, .15], engine='pocket', where='on this Mac')))
    page.reply = sse(dict(step=SAY, k=1, tier='tutor'), dict(board=dict(tier='tutor', steps=[SAY], sources=[], end='')))
    page.evaluate("abhyasaGuide.ask('what is this')")
    page.wait_for_function("window.played.length === 1 && [...document.querySelectorAll('#guide-strip .board-say span')].every(s => s.classList.contains('on'))", timeout=5000)
    assert asked[0] == 'Noise goes in slowly.' and page.evaluate('played[0]').startswith('blob:')
    assert page.evaluate("document.querySelector('#guide-strip .board-voice-at').textContent") == 'Pocket TTS'
    assert 'on this Mac' in page.evaluate("document.querySelector('#guide-strip .board-keys').textContent")
    assert not page.evaluate("document.querySelector('#guide-strip .board-notice')")

def test_a_failed_route_falls_back_to_the_browser_voice(page):
    "The route fails: the board speaks with the browser voice, the words still light up, and the strip says so in one quiet line."
    natural(page, lambda d: (502, dict(error='The natural voice could not say this line.')))
    page.reply = sse(dict(board=dict(tier='tutor', steps=[SAY], sources=[], end='')))
    page.evaluate("abhyasaGuide.ask('what is this')")
    page.wait_for_function("[...document.querySelectorAll('#guide-strip .board-say span')].every(s => s.classList.contains('on'))", timeout=5000)
    assert page.evaluate('played') == []
    n = page.evaluate("document.querySelector('#guide-strip .board-notice').textContent")
    assert n.startswith('The natural voice did not answer. The browser voice reads the steps now.')

def test_stop_ends_the_natural_voice(page):
    "Stop while the line plays: the audio stops, and the board is gone."
    natural(page, lambda d: (200, dict(audio=wav(), words=[0, .05, .1, .15])))
    page.evaluate("() => { HTMLMediaElement.prototype.play = function () { played.push(this.src); window.audio = this; setTimeout(() => this.dispatchEvent(new Event('playing')), 10); return Promise.resolve(); }; }")   # it never ends
    page.reply = sse(dict(board=dict(tier='tutor', steps=[SAY], sources=[], end='')))
    page.evaluate("abhyasaGuide.ask('what is this')")
    page.wait_for_function("window.played.length === 1")
    page.click('#guide-strip .board-stop')
    assert page.evaluate('abhyasaBoard.state') is None and page.evaluate("!window.audio.getAttribute('src')")

def test_the_browser_voice_offers_the_natural_voice_once(page):
    "With the browser voice, the first board says one time that a natural voice can read the steps, with a link to Settings."
    page.evaluate("speechSynthesis.getVoices = () => []; localStorage.removeItem('guide-voice-offered')")
    page.reply = sse(dict(board=dict(tier='tutor', steps=[SAY], sources=[], end='')))
    page.evaluate("abhyasaGuide.ask('what is this')")
    page.wait_for_function("document.querySelector('#guide-strip .board-notice')")
    assert page.evaluate("document.querySelector('#guide-strip .board-notice a').getAttribute('href')") == '/settings#g-voice'
    page.evaluate("abhyasaBoard.stop(); abhyasaGuide.ask('and this')")
    page.wait_for_function("abhyasaBoard.state")
    assert not page.evaluate("document.querySelector('#guide-strip .board-notice')")
