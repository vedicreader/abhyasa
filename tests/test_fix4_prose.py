"Fix slice 4 prose: a topic-neutral change-box example, maths in a walk passage, and a model reply that is not prose is no note."
import re
from fasthtml.common import to_xml
from fastcore.basics import AttrDict
from abhyasa import path
from abhyasa.models import Fake
from abhyasa.blocks.walk import ui


# 2. the example under the change box
def test_change_box_example_names_no_model_or_noise_schedule():
    assert not re.search(r'noise|schedule|u-net|diffusion|model', ui.CHANGE_SAY, re.I), ui.CHANGE_SAY
    assert ui.CHANGE_SAY.startswith('What should change? For example:')


# 3. maths in the passage of a walk step
def _passage(text, also=()):
    j = AttrDict(id='w1', title='Thermodynamics')
    s = dict(slug='first-law', read=dict(text=text, title='LibreTexts', src='vault:notebooks', also=list(also)))
    return to_xml(ui.Passage(j, s, AttrDict(statement='The first law.', moves=[])))


def test_parenthesis_latex_in_a_passage_is_drawn_as_maths():
    h = _passage(r'The change in energy is \(\Delta U\) when heat flows in.')
    assert 'class="math' in h and r'\Delta U' in h, h
    assert '(\\Delta' not in h and '((' not in h, h   # not the raw text with its brackets


def test_double_backslash_latex_and_bracket_display_in_a_passage():
    h = _passage('So \\\\(Q = W\\\\) holds, and \\[\\Delta U = Q - W\\]')
    assert h.count('class="math') == 2 and '(Q' not in h, h


STORED = 'the change in its internal energy ((\\Delta U)) is equal to the heat (*Q*) added to the system.'   # as walk.json of the thermo rehearsal holds it


def test_stored_double_bracket_maths_is_drawn_as_maths():
    h = _passage(STORED)
    assert 'class="math' in h and '((' not in h and '))' not in h, h
    assert '(<em>Q</em>)' in h, h   # a bracket of prose stays


def test_tex_dollars_fixes_double_brackets_around_a_tex_command_only():
    from abhyasa.core import tex_dollars
    assert tex_dollars('energy ((\\Delta U)) is') == 'energy $\\Delta U$ is'
    assert tex_dollars('a ((very) odd) case and ((b)) too') == 'a ((very) odd) case and ((b)) too'


def test_prose_brackets_and_words_in_a_passage_stay():
    h = _passage('The cost (about 5 dollars) and the ((double) bracket) of prose, with d_model and x.')
    assert 'math' not in h and '(about 5 dollars)' in h and '((double) bracket)' in h and 'd_model' in h, h


def test_second_passage_of_a_merge_is_drawn_as_maths_too():
    h = _passage('First part.', also=[dict(text=r'It is \(\Delta U\).', title='B', src='vault:notebooks')])
    assert 'class="math' in h and '((' not in h, h


# 7. a reply of `{}` is not a note
SAID = 'Energy is conserved when heat and work are counted together.'


class _Lr:
    "The few things `tutor_note` asks of a learning store, with one step."
    def __init__(self, read=None):
        self.step = dict(slug='first-law', read=read)
        self.j = AttrDict(id='w1', title='Thermo', goal='learn thermodynamics', steps=[self.step])
        self.saved = []
    def journey(self, jid): return self.j
    def concept(self, slug): return AttrDict(name='First law', statement=SAID, slug=slug)
    def level_of(self, c, missing=None): return 'Level: new to this.'
    def walk_slug(self, jid, slug, **kw): self.saved.append(kw)


def _note(monkeypatch, lr, ask):
    monkeypatch.setattr(path, 'walk_needs', lambda *a, **k: [])
    monkeypatch.setattr(path, 'concept_grounds', lambda *a, **k: [])
    return path.tutor_note(lr, ask, lr.j, 0)


def test_empty_json_reply_is_no_note_without_a_passage(monkeypatch):
    lr = _Lr()
    assert _note(monkeypatch, lr, Fake()) == 'The tutor could not write a note for this idea. You can ask again later.'
    assert lr.saved[-1]['note'] == '' and not lr.saved[-1].get('note_none'), lr.saved   # not saved: a later visit asks the tutor again


def test_empty_json_reply_gives_the_statement_with_a_passage(monkeypatch):
    lr = _Lr(read=dict(text='Heat added to a gas raises its energy unless the gas does work.'))
    got = _note(monkeypatch, lr, Fake())
    assert got == SAID and '{' not in got, got
    assert lr.saved[-1]['note'] == SAID


def test_a_real_prose_note_is_kept(monkeypatch):
    lr = _Lr()
    ask = Fake({'You write a short note': 'A hot cup warms your hands while it cools. That is energy moving on.'})
    assert _note(monkeypatch, lr, ask).startswith('A hot cup warms your hands')


def test_a_prose_note_that_opens_with_a_link_is_kept(monkeypatch):
    lr = _Lr()
    ask = Fake({'You write a short note': '[Joule](https://example.org/j) showed that work turns into heat in a fixed ratio.'})
    assert _note(monkeypatch, lr, ask).startswith('[Joule]')
