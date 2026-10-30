"The figure of a walk step: its alt is the caption of the paper when the data has it."
from abhyasa.blocks.walk.ui import fig_caption

def test_the_caption_comes_from_the_data_or_the_passage():
    assert fig_caption(dict(figure='images/f.png', caption='Figure 1: The model')) == 'Figure 1: The model'
    text = 'We compute the dot products.\n\n![Figure 2: Scaled Dot-Product Attention](images/fig2.png)'
    assert fig_caption(dict(figure='images/fig2.png', text=text)) == 'Figure 2: Scaled Dot-Product Attention'
    assert fig_caption(dict(figure='images/other.png', text=text)) == ''   # the image of another figure is not its caption

def test_the_step_title_names_its_concept(mk, walk_fake, lr):
    "The title of a walk step carries the slug of its idea, so the screen guide can send it."
    import re
    from walk_data import walk
    cl = mk(); jid = walk(cl, lr); cl.post(f'/w/{jid}/start')
    j = lr.journey(jid)
    h = cl.get(f'/w/{jid}/0').text
    assert re.search(r'<h1[^>]*class="idea"[^>]*data-concept="%s"|<h1[^>]*data-concept="%s"[^>]*class="idea"' % ((j.steps[0]['slug'],) * 2), h)

def test_a_board_hint_shows_its_count_and_its_maths():
    "After a reload, a hint from the board says its count of the ladder, and a bare W_Q in its words is maths."
    from fasthtml.common import to_xml
    from abhyasa.blocks.walk.ui import Turn, bare_tex
    from abhyasa.tutor import HINTS
    h = to_xml(Turn(dict(who='tutor', kind='hint', via='board', text='Look at W_Q and d_{k}.'), 2))
    assert f'Hint 2 of {len(HINTS)} (from the board)' in h and '<span class="math inline">W_Q</span>' in h
    assert bare_tex('a file_name, a_b_c and $x_i$ and W_Q') == 'a file_name, a_b_c and $x_i$ and W_Q'   # text with $ stays; long names are not maths
