"Walk dependencies and passages use the idea, not just its display title."
from abhyasa.models import Fake
import json
import pytest
from abhyasa.path import walk_from_topic, _plan_order, step_read
from abhyasa.sources import VaultSource, main_words


def test_capstone_follows_its_prerequisites(lr):
    steps = [dict(name='Compute a whole navamsa chart', statement='Map every longitude to its navamsa sign.',
                  needs=['Nine parts in each sign', 'Starting sign by element']),
             dict(name='Nine parts in each sign', statement='Divide each sign into nine equal parts.'),
             dict(name='Starting sign by element', statement='The element sets the first navamsa sign.', needs=['Nine parts in each sign'])]
    fake = Fake({'You plan a learning path': dict(title='Navamsa', steps=steps), 'You choose passages': dict(choices=[None, None, None])})
    j = walk_from_topic(lr, fake, 'Learn navamsa', near=False)
    saved = lr.journey(j.id)
    assert [s['slug'] for s in saved.steps] == ['nine-parts-in-each-sign', 'starting-sign-by-element', 'compute-a-whole-navamsa-chart']
    assert lr.concept(saved.steps[-1]['slug']).prereqs == ['nine-parts-in-each-sign', 'starting-sign-by-element']
    assert len(fake.calls) == 1   # no idea has a candidate passage, so there is no judge call
    independent = [dict(name='Capstone', needs=[' Base ']), dict(name='Other'), dict(name='Base'), dict(name=None)]
    assert [s['name'] for s in _plan_order(independent)] == ['Other', 'Base', 'Capstone']
    loop = [dict(name='A', needs=['B']), dict(name='B', needs=['A']), dict(name='C')]
    assert [s['name'] for s in _plan_order(loop)] == ['A', 'B', 'C']


def test_whole_game_step_opens_the_walk(lr):
    steps = [dict(name='Latent diffusion', statement='A U-Net removes noise from VAE latents.', needs=['Noise prediction']),
             dict(name='Noise prediction', statement='A network learns to predict the noise in an image.'),
             dict(name='Run Stable Diffusion', statement='A diffusers pipeline turns a text prompt into an image.', whole=True,
                  needs=['Latent diffusion', 'Noise prediction'], hands='notebook', makes='four images from a prompt')]
    assert [s['name'] for s in _plan_order(steps)] == ['Run Stable Diffusion', 'Noise prediction', 'Latent diffusion']
    assert [(s['name'], s['whole']) for s in _plan_order([dict(name='B', needs=['A'], whole=True), dict(name='A', whole=True)])] == [('B', True), ('A', False)]
    fake = Fake({'You plan a learning path': dict(title='Diffusion', steps=steps), 'You choose passages': dict(choices=[None, None, None])})
    saved = lr.journey(walk_from_topic(lr, fake, 'Make images with diffusion', near=False).id)
    assert [s.get('whole', False) for s in saved.steps] == [True, False, False]
    assert saved.steps[0]['check']['kind'] == 'notebook'
    assert lr.concept(saved.steps[0]['slug']).prereqs == []


def test_folder_passage_teaches_the_idea(lr, tmp_path):
    folder = tmp_path/'navamsa'
    folder.mkdir()
    texts = {
        'nakshatra-stories.md': r'''# Nakshatra stories

Giri covers the first nine nakshatras. Each nakshatra has a past-life story, read through the navamsa. The stories describe a person's past birth and karma, not a calculation. A planet has the same sign in these stories about fate.
''',
        'nakshatra-methods.md': r'''# Nakshatra methods

## Calculation

Divide each zodiac sign into nine equal parts of 3 degrees 20 minutes. To compute a navamsa chart, take each planet's longitude, find its part, and count from the starting sign for its element. The resulting sign is the planet's D9 sign.
'''}
    for name, text in texts.items():
        path = folder/name
        path.write_text(text)
        lr.vault.shelf('notebooks').add(text, title=path.stem, source=str(path), kind='md', meta=dict(root=folder.name, path=str(path)))
    fake = Fake({'You plan a learning path': dict(title='Navamsa', steps=[
        dict(name='Nine parts in each sign', statement='Divide each zodiac sign into nine equal parts of 3 degrees 20 minutes.', doc='nakshatra-stories'),
        dict(name='Compute a whole navamsa chart', statement="Take each planet's longitude, find its part and count from the starting sign for its element.", doc=''),
        dict(name='Vargottama strength', statement='A vargottama planet has the same sign in D1 and D9.', doc='')])})
    j = walk_from_topic(lr, fake, 'Learn navamsa', sources=[VaultSource(lr)], chips=[f'folder:{folder}'], near=False)
    for step in lr.journey(j.id).steps[:2]:
        assert step['read'] and step['read']['title'] == 'nakshatra-methods'
        assert '3 degrees 20 minutes' in step['read']['text']
        assert 'past-life' not in step['read']['text']
    assert j.steps[2]['read'] is None
    assert len(fake.calls) == 2


def test_meaning_candidates_and_none_are_saved(lr, tmp_path):
    folder = tmp_path/'navamsa'
    folder.mkdir()
    teaching = 'Split the zodiac sector into equal slices, all spanning 3 degrees 20 minutes. A full sector spans 30 degrees, so it holds 9 such slices.'
    topic_only = 'Vargottama strength is a topic in these past-life stories. The teacher tells stories about karma, but gives no rule for how to find or measure it.'
    for title, text in [('celestial-method', teaching), ('stories', topic_only)]:
        path = folder/(title + '.md')
        path.write_text(text)
        lr.vault.shelf('notebooks').add(text, title=title, source=str(path), meta=dict(root=folder.name, path=str(path)))
    lr.vault.shelf('notebooks').add('Outside material that must not enter the folder candidates. ' * 3, title='outside', meta=dict(root='elsewhere'))
    ideas = [dict(name='Nine parts in each sign', statement='Divide a zodiac sector into equal slices of 3 degrees 20 minutes.'),
             dict(name='Vargottama strength', statement='A planet in the same zodiac sector in D1 and D9 has vargottama strength.')]
    seen = []
    def judge(p, sp):
        payload = json.loads(p.split('<source title="ideas">')[1].split('</source>')[0])
        seen.append(payload)
        pick = next(c['number'] for c in payload[0]['candidates'] if teaching in c['text'])
        return dict(choices=[pick, None])
    fake = Fake({'You plan a learning path': dict(title='Divisions', steps=ideas), 'You choose passages': judge})
    j = walk_from_topic(lr, fake, 'Learn navamsa', sources=[VaultSource(lr)], chips=[f'folder:{folder}'], near=False)
    saved = lr.journey(j.id)
    assert len(seen) == 1 and len(seen[0]) == 2
    assert all(len(i['candidates']) <= 4 for i in seen[0])
    assert all(len(c['text']) <= 1600 and c['title'] != 'outside' for i in seen[0] for c in i['candidates'])
    assert any(topic_only in c['text'] for c in seen[0][1]['candidates'])
    assert not set(main_words(ideas[0]['name'])) & set(main_words(teaching))
    assert saved.steps[0]['read']['text'] == teaching
    assert saved.steps[1]['read'] is None
    assert len(fake.calls) == 2
    assert step_read(lr, j.id, saved.steps[0]['slug'], [VaultSource(lr)]) is None
    assert step_read(lr, j.id, saved.steps[1]['slug'], [VaultSource(lr)]) is None
    assert lr.journey(j.id).steps == saved.steps
    assert len(fake.calls) == 2


@pytest.mark.parametrize('reply', ['not JSON', dict(choices=[True]), dict(choices=[99]), dict(choices=[]), RuntimeError('judge unavailable')])
def test_bad_judge_falls_back_and_saves(lr, tmp_path, caplog, reply):
    folder = tmp_path/'notes'
    folder.mkdir()
    text = 'Ranking orders items by a score. Compare the scores and put the largest score first, then the next largest, until all items have a place.'
    path = folder/'ranking.md'
    path.write_text(text)
    lr.vault.shelf('notebooks').add(text, title='ranking', source=str(path), meta=dict(root=folder.name, path=str(path)))
    def judge(p, sp):
        if isinstance(reply, Exception): raise reply
        return reply
    fake = Fake({'You plan a learning path': dict(title='Scores', steps=[dict(name='Ranking', statement='Order items by a score.')]), 'You choose passages': judge})
    j = walk_from_topic(lr, fake, 'Rank items', sources=[VaultSource(lr)], chips=[f'folder:{folder}'], near=False)
    assert lr.journey(j.id).steps[0]['read']['text'] == text
    assert len(fake.calls) == 2
    assert 'word-based' in caplog.text
