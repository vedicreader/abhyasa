"⌥D (Speak) on a real page, in a headless browser: a held key sends many keydown events with `repeat`. Only the first one counts."
import pytest
from test_guide_page import page, _chromium   # the page fixture: one headless page of the app

pytestmark = pytest.mark.skipif(not _chromium(), reason="Playwright's Chromium is not installed")

# A box with its own mic, in focus. The mic never opens: getUserMedia counts the starts and never answers. A MutationObserver counts each
# change of the class of the mic button, and each time the button is replaced.
SETUP = """() => {
  const t = document.createElement('textarea'); t.id = 'answer'; t.dataset.mic = '1'; document.querySelector('main').prepend(t);
  abhyasaMics(); t.focus();
  window.starts = 0; navigator.mediaDevices.getUserMedia = () => { starts++; return new Promise(() => {}); };
  window.mic = document.querySelector('.mic[data-into="answer"]'); window.ons = [];
  new MutationObserver(() => { const on = document.querySelector('.mic[data-into="answer"]').classList.contains('on'); if (ons.at(-1) !== on) ons.push(on); })
    .observe(document.querySelector('main'), {subtree: true, attributes: true, attributeFilter: ['class'], childList: true});
}"""

def test_a_held_speak_key_starts_once_and_types_nothing(page):
    "Hold ⌥D with 20 repeats: the mic starts one time and stays on, the button is the same element, and no ∂ goes into the box. The next press stops it."
    page.evaluate(SETUP)
    page.keyboard.down('Alt')
    for _ in range(21): page.keyboard.down('KeyD')   # the first keydown, then 20 with repeat = true
    page.keyboard.up('KeyD'); page.keyboard.up('Alt')
    assert page.evaluate('starts') == 1 and page.evaluate('ons') == [True]
    assert page.evaluate("document.getElementById('answer').value") == ''
    assert page.evaluate("document.querySelector('.mic[data-into=\"answer\"]') === mic")
    page.keyboard.press('Alt+KeyD')   # the design is a toggle: one press starts, the next press stops
    page.wait_for_function("ons.length === 2")
    assert page.evaluate('starts') == 1 and page.evaluate('ons') == [True, False] and page.evaluate("document.getElementById('answer').value") == ''
