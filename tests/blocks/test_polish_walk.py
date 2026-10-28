"Task 19b, design polish of the walk, the side pane and the end of a walk: the layout, the way beside, the copy, and the magic touches."
import re
from pathlib import Path
from walk_data import *

ROOT = Path(__file__).parents[2]/'abhyasa'
def css(p): return (ROOT/p).read_text()

def needs_gradients(lr):
    lr.put('Derivatives and gradients', 'The slope of a function at a point, one for each input.', 'ml', slug='gradients')
    lr.update('scaling-by-the-root-of-dk', prereqs=['softmax', 'gradients'])

# F7: the step page lines up

def test_step_page_lines_up():
    "The crumbs start where the outline starts, the layout fits a 1000 px window, and the outline goes under 1040 px."
    w = css('blocks/walk/walk.css')
    assert re.search(r'main\.wide:has\(\.walk-layout\) > \.crumbs \{[^}]*max-width: 984px[^}]*margin-inline: auto', w)
    assert 'grid-template-columns: 220px minmax(0, 720px); gap: var(--s7)' in w
    assert '@media (max-width: 1040px) { .walk-layout' in w and '900px' not in w
