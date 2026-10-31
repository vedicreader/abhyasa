"A walk to a goal from the sources that it names: the notebook first in a search, the chips on Start, and sources for a path."
import re, time
from abhyasa.ground import VaultSource

GOAL = 'fine-tune my own diffusion model to make a Ramayana comic from the vedicreader episodes'
NBS = [('nbs/15_DDPM', '# Denoising diffusion\n\nDDPM training: we add noise to each image, and the noise schedule sets how much noise we add at each step t.'),
       ('nbs/17_DDPM_v2', '# DDPM, the second version\n\nA cleaner training loop for the same model, with callbacks for each part of the work.'),
       ('nbs/26_diffusion_unet', '# A diffusion U-net\n\nThe U-net takes a noisy image and the step t, and it predicts the noise in the image.')]
PLAN = dict(title='Diffusion comic', subject='ml', steps=[dict(name='Noise schedule', statement='', doc='15_DDPM', why='The base.'),
                                                          dict(name='Captions from the episodes', statement='', hands='notebook', makes='captions.jsonl', data=['EPISODES'])])

def course(lr):
    "File three notebooks of course22p2 on the notebooks shelf."
    for t, x in NBS: lr.vault.shelf('notebooks').add(x, title=t, source=f'/tmp/course22p2/{t}.ipynb', kind='notebook', meta=dict(root='course22p2'))

def wait_for_walk(cl, r, tries=200):
    "Ask the pending card again until the walk opens; give the redirect."
    for _ in range(tries):
        if 'HX-Redirect' in r.headers: return r.headers['HX-Redirect']
        m = re.search(r'hx-get="([^"]+)"', r.text); assert m, r.text
        time.sleep(.05); r = cl.get(m[1].replace('&amp;', '&'))
    raise AssertionError('the walk did not open')

def test_notebook_beats_web_page_for_ddpm(lr):
    "A web page on one shelf and 3 notebooks on another: the hits are sorted by score across shelves, so the DDPM notebook comes first."
    lr.vault.add('Dogs need daily training and walks. A web page about pets and their training at home.', 'Pet training tips', source='https://example.com/pets', kind='web')
    course(lr)
    ps = VaultSource(lr).search('DDPM training')
    assert ps[0].src == 'vault:notebooks' and 'DDPM' in ps[0].title and 'Pet training tips' in [p.title for p in ps]

def test_goal_on_start_uses_the_chips(mk, lr, walk_fake):
    "Start with a goal and a vault chip: the planner sees the documents, and the step reads its paragraph from the notebook that it names."
    course(lr)
    walk_fake.rules['You plan a learning path'] = PLAN
    cl = mk()
    url = wait_for_walk(cl, cl.post('/walk/new', data=dict(q=GOAL, sources=['vault:course22p2'], chips='1')))
    j = lr.journey(url.split('/')[-1])
    assert j.goal == GOAL and j.mode == 'walk' and j.chips == ['vault:course22p2']
    r = j.steps[0]['read']
    assert (r['title'], r['root'], r['shelf']) == ('15_DDPM', 'course22p2', 'notebooks') and 'noise schedule' in r['text']
    assert j.steps[1]['check']['kind'] == 'notebook' and j.steps[1]['makes'] == 'captions.jsonl'
    plan_prompt = next(p for p, sp in walk_fake.calls if 'You plan a learning path' in sp)
    assert '<source title="course22p2">- 15_DDPM: Denoising diffusion' in plan_prompt
    cl.post(f'{url}/start')
    h = cl.get(f'{url}/0').text
    assert '15_DDPM' in h and 'the noise schedule sets how much noise' in h   # the step page shows the passage and its source line

def test_weak_match_is_no_source(lr):
    "A README in a named folder names only some words of the idea: it is not a source, so the step has no passage."
    from abhyasa.journey import _topic_read
    lr.vault.shelf('notebooks').add('Run training on a pool of local GPUs. The stable releases are on PyPI.', title='pytorch-image-models/README',
                                    source='/tmp/course22/pytorch-image-models/README.md', kind='md', meta=dict(root='course22'))
    assert _topic_read(dict(slug='s', name='Run Stable Diffusion 1.5 on your Mac'), [VaultSource(lr)], lr, roots=['course22']) is None

def test_an_old_path_link_makes_it_a_walk(mk, lr, fake):
    "An old link to a path makes it a walk with a passage from your sources and a check on each step, then opens the walk page."
    fake.rules['You plan a learning path'] = dict(title='Ranks', subject='ml', steps=[dict(name='Ranking', slug='ranking', statement='', why='')])
    from abhyasa.journey import plan
    j = plan(lr, fake, 'learn to rank')
    cl = mk()
    assert cl.get(f'/path/{j.id}', follow_redirects=False).headers['location'] == f'/w/{j.id}'
    w = lr.journey(j.id)
    assert w.mode == 'walk' and w.goal == 'learn to rank'
    assert w.steps[0]['read']['title'] == 'My ranking notes' and w.steps[0]['check']
    assert 'Start the walk' in cl.get(f'/w/{j.id}').text
