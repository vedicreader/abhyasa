"Lecture transcripts as sources: the rank after a notebook."
import re, json, time, pytest
from pathlib import Path
from fastcore.utils import AttrDict
from fastcore.nbio import new_nb, mk_cell, write_nb
from abhyasa.sources import file_folder, transcript_of, transcript_read, sentences, passage, SEARCH
from abhyasa.path import _topic_read

TALK = ["Hi everybody and welcome to Lesson 3 of Deep Learning for Coders. Okay so, you know, today we're going to look at softmax and why we need it.",
        "I think it's kind of the heart of attention, so let's just dive in. So softmax turns a list of scores into weights that add up to one. "
        "And you know, the biggest score gets the biggest weight, so we can see what the model looks at.",
        "Okay, so that's the idea. Now I'm going to show you the code, and I'll zoom in a bit so you can see it. "
        "So we take the exponent of each score, and then we divide by the sum, you know, so it all adds up.",
        "Then we look at cross entropy. So cross entropy is the loss we use with softmax, and I'll show you why in a minute. "
        "That's it for today, so see you next week, you know, and have a play with the notebook."]
SUMM = ("In Lesson 3 of Deep Learning for Coders, the instructor explains how softmax turns scores into weights for attention.\n\n"
        "The instructor then shows the code of softmax with the exponent and the sum.\n\n"
        "The lesson ends with cross entropy, the loss that goes with softmax.")
SOFTMAX = dict(name='Softmax', statement='Softmax turns scores into weights that add up to one.')

def course(d, summary=True, stamps=False):
    "A course folder: a transcript of lesson 3 (with time stamps when `stamps`), its summary, three notebooks and a note."
    (d/'summaries').mkdir(parents=True); (d/'nbs').mkdir()
    paras = [f'[{k:02d}:05] {p}' for k, p in enumerate(TALK)] if stamps else TALK
    (d/'summaries/lesson03.txt').write_text('\n\n'.join(paras))
    if summary: (d/'summaries/lesson03-summ0.txt').write_text(SUMM)
    for n, h in (('03_softmax', 'Softmax'), ('13_resnet', 'ResNet'), ('30_vae', 'VAE')):
        write_nb(new_nb([mk_cell(f'# {h}\n\nSoftmax turns scores into weights that add up to one, as {h} shows.', 'markdown')]), d/f'nbs/{n}.ipynb')
    (d/'notes.md').write_text('# Notes\n\nSoftmax turns scores into weights. The weights add up to one. Attention uses them to mix the values of the tokens.')
    return d

@pytest.fixture
def home(tmp_path, monkeypatch):
    "A temp home folder with the course folder `course22`."
    monkeypatch.setattr(Path, 'home', lambda: tmp_path); monkeypatch.setenv('HOME', str(tmp_path))
    return tmp_path

def filed(lr, home, **kw):
    "File the course folder; give its docs by title."
    return {d.title: d for d in file_folder(lr, course(home/'course22', **kw))}

class Both:
    "A source with a transcript passage first and a notebook passage second; both name softmax."
    name = 'vault'
    def __init__(self, ds): self.ds = ds
    def search(self, q, k=4):
        t, n = self.ds['summaries/lesson03'], self.ds['nbs/03_softmax']
        return [passage('vault:notebooks', t.doc_id, t.title, TALK[1]), passage('vault:notebooks', n.doc_id, n.title, 'Softmax turns scores into weights that add up to one.')]

def test_a_notebook_passage_wins_over_a_transcript_passage(lr, home):
    "Two passages that both name the idea: the notebook passage is the source, not the transcript."
    ds = filed(lr, home)
    c = lr.put('Softmax', SOFTMAX['statement'], 'ml')
    r = _topic_read(c, [Both(ds)], lr)
    assert r['ref'] == ds['nbs/03_softmax'].doc_id, r
    only = _topic_read(c, [type('T', (), dict(name='vault', search=lambda self, q, k=4: Both(ds).search(q)[:1]))()], lr)
    assert only['ref'] == ds['summaries/lesson03'].doc_id   # with no other passage the transcript is still a source
