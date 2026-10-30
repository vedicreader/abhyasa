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
