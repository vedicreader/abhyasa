"The figure of a walk step: its alt is the caption of the paper when the data has it."
from abhyasa.blocks.walk.ui import fig_caption
from walk_data import walk

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

def test_a_missing_figure_draws_no_image(mk, lr, walk_fake):
    "A step whose figure file is not in the vault assets draws no image; with the file there, the image shows and loads."
    from pathlib import Path
    cl = mk(); jid = walk(cl, lr)
    lr.walk_step(jid, 0, read={**(lr.journey(jid).steps[0].get('read') or {}), 'figure': 'figs/gone.png'})
    page = cl.get(f'/w/{jid}/0').text
    assert f'/w/{jid}/0/img' not in page and cl.get(f'/w/{jid}/0/img').status_code == 404
    p = Path(lr.vault.assets())/'figs'/'gone.png'; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'\x89PNG\r\n\x1a\n')
    assert f'/w/{jid}/0/img' in cl.get(f'/w/{jid}/0').text and cl.get(f'/w/{jid}/0/img').status_code == 200
