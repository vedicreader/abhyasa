"Lecture transcripts as sources: the kind, the tight passage, the links to the lesson, the transcript page, and the rank after a notebook."
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

def test_a_transcript_is_known_and_a_summary_is_not(lr, home):
    "The talk is a transcript with lesson 3. Its summary, the notebooks and the note are not. Nothing in the vault changes."
    ds = filed(lr, home)
    rows = {t: json.dumps(lr.vault.shelf('notebooks').doc(d.doc_id), default=str) for t, d in ds.items()}
    got = {t for t, d in ds.items() if transcript_of(lr, d.shelf, d.doc_id)}
    assert got == {'summaries/lesson03'}, got
    assert transcript_of(lr, 'notebooks', ds['summaries/lesson03'].doc_id).lesson == 3
    assert rows == {t: json.dumps(lr.vault.shelf('notebooks').doc(d.doc_id), default=str) for t, d in ds.items()}   # a read-time check only

def test_the_passage_is_a_tight_verbatim_span_with_lesson_links(lr, home):
    "A long passage from the transcript shows as 1 to 3 whole sentences on the idea, word for word, labelled, with the notebook of lesson 3 and the video."
    ds = filed(lr, home)
    t = ds['summaries/lesson03']
    long = ' '.join(TALK[:3])
    r = transcript_read(lr, dict(shelf='notebooks', doc_id=t.doc_id, title=t.title, text=long), SOFTMAX)
    assert 1 <= len(sentences(r['text'])) <= 3 and r['text'] in long and len(r['text']) < len(long) / 2
    assert r['text'].startswith('So softmax turns a list of scores into weights')
    assert r['what'] == 'Lecture transcript · Lesson 3'
    links = {l['text']: l.get('href') or l.get('url') for l in r['links']}
    assert links['Lesson notebook · 03_softmax'] == f"/v/notebooks/{ds['nbs/03_softmax'].doc_id}"   # by number: not 13_resnet, not 30_vae
    assert links['Find the video'] == SEARCH + 'Deep+Learning+for+Coders+Lesson+3'
    note = dict(shelf='notebooks', doc_id=ds['course22/notes'].doc_id, text='Softmax turns scores into weights.')
    assert transcript_read(lr, note, SOFTMAX) is note   # any other source stays as it is

def test_a_transcript_with_time_stamps_links_the_video_at_the_passage(lr, home):
    "With a YouTube link and time stamps, the video link opens at the stamp before the passage."
    ds = filed(lr, home, stamps=True)
    t = ds['summaries/lesson03']
    lr.vault.shelf('notebooks').set_meta(t.doc_id, url='https://www.youtube.com/watch?v=dQw4w9WgXcQ')   # the temp vault: a transcript that came with its link
    r = transcript_read(lr, dict(shelf='notebooks', doc_id=t.doc_id, text=f'[02:05] {TALK[2]}'), dict(name='Exponent'))
    assert dict(text='Video at 2:05', url='https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=125s') in r['links']

def test_the_transcript_page_shows_its_links_and_topics(mk, lr, home):
    "The page says Lecture transcript · Lesson 3, links the notebook, the summary and the video, lists the topics of the summary and keeps the paragraphs."
    ds = filed(lr, home)
    t = mk(['vault']).get(f"/v/notebooks/{ds['summaries/lesson03'].doc_id}").text
    assert 'Lecture transcript · Lesson 3' in t
    for x in (f"/v/notebooks/{ds['nbs/03_softmax'].doc_id}", f"/v/notebooks/{ds['summaries/lesson03-summ0'].doc_id}", 'Find the video', 'Topics, from the summary'):
        assert x in t, x
    tops = re.findall(r'<a href="#tp(\d+)">([^<]+)</a>', t)
    assert [x for _, x in tops] == ['The instructor explains how softmax turns scores into weights for attention.',
                                   'The instructor then shows the code of softmax with the exponent and the sum.',
                                   'The lesson ends with cross entropy, the loss that goes with softmax.']
    assert [int(k) for k, _ in tops] == sorted(int(k) for k, _ in tops) and all(f'id="tp{k}"' in t for k, _ in tops)
    assert t.count('id="tp') >= 3 and 'cross entropy is the loss we use' in t
    s = mk(['vault']).get(f"/v/notebooks/{ds['summaries/lesson03-summ0'].doc_id}").text
    assert 'Lecture transcript' not in s   # a summary has the plain page

def test_with_no_summary_the_topics_come_from_the_ideas(mk, lr, home):
    "A transcript with no summary lists the ideas that a walk took from it, each one at its paragraph."
    ds = filed(lr, home, summary=False)
    t = ds['summaries/lesson03']
    lr.put('Cross entropy', 'The loss that goes with softmax.', 'ml', provenance=[dict(src='vault:notebooks', doc_id=t.doc_id, passage='So cross entropy is the loss we use with softmax')])
    page = mk(['vault']).get(f'/v/notebooks/{t.doc_id}').text
    assert 'Topics, from the ideas of your walks' in page
    k = re.search(r'<a href="#tp(\d+)">Cross entropy</a>', page)[1]
    assert 'cross entropy is the loss' in re.search(rf'id="tp{k}"[^>]*>(.*?)</div>', page, re.S)[1]

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

def test_the_walk_step_shows_the_tight_passage(mk, lr, home):
    "A walk step whose passage is the long transcript text shows the tight span, the label and the notebook link; the long tail is not there."
    ds = filed(lr, home)
    t = ds['summaries/lesson03']
    lr.put('Softmax', SOFTMAX['statement'], 'ml')
    long = ' '.join(TALK[:3])
    lr.put_journey(dict(id='tw', title='Lesson 3', goal='Read lesson 3', mode='walk', source=None, started=time.time(), created=1.,
                        steps=[dict(slug='softmax', status='todo', why='', check=dict(kind='short', depth=2),
                                    read=dict(shelf='notebooks', doc_id=t.doc_id, title=t.title, text=long))]))
    page = mk().get('/w/tw/0').text
    assert 'So softmax turns a list of scores into weights' in page and 'Lecture transcript · Lesson 3' in page
    assert f"/v/notebooks/{ds['nbs/03_softmax'].doc_id}" in page and 'zoom in a bit' not in page
    assert lr.journey('tw').steps[0]['read']['text'] == long   # the walk keeps its passage
