from pathlib import Path

JS = (Path(__file__).resolve().parents[1]/'abhyasa'/'blocks'/'talk'/'talk.js').read_text()


def test_the_presenter_clock_writes_a_text_only_when_it_changed():
    "A header write each second made End the talk unstable for a click; the tick now skips an unchanged text."
    tick = JS[JS.index('const tick = () =>'):JS.index('tick(); const ticker')]
    assert 'const put = (el, t) => { if (el.textContent !== t)' in tick
    assert '.textContent =' not in tick.replace('el.textContent = t', '')
