import threading
from abhyasa.learner import PROMPTS, prompt, saved
from abhyasa.models import Fake
from abhyasa.blocks.settings import tryit

DRAFT = '\n'.join(f'Draft hint {i}.' for i in range(1, 7))
ECHO = lambda p, sp: p.split('of 6: ')[1].split('\n')[0]   # the reply is the hint line that the prompt asked for

def test_a_draft_changes_only_its_own_call():
    from abhyasa.learner import use_prompts
    inside, outside, seen, go = [], [], threading.Event(), threading.Event()
    def other(): seen.wait(); outside.append(prompt('hints')); go.set()
    t = threading.Thread(target=other); t.start()
    with use_prompts(dict(hints=DRAFT)):
        inside.append(prompt('hints')); seen.set(); go.wait()
    t.join()
    assert inside == [DRAFT] and outside == [PROMPTS['hints'].dflt] and prompt('hints') == PROMPTS['hints'].dflt
    with use_prompts(dict(hints=DRAFT)), use_prompts(dict(grade='x')): assert prompt('hints') == DRAFT   # a nested draft keeps the outer one

def test_try_it_for_hints_gives_both_columns_and_saves_nothing(mk, fake):
    tryit._cache.clear()
    fake.rules['Give hint level'] = ECHO
    r = mk().post('/settings/prompt/try', data=dict(name='hints', text=DRAFT))
    assert r.status_code == 200 and 'Your draft' in r.text and 'The default' in r.text
    assert 'Draft hint 1.' in r.text and PROMPTS['hints'].dflt.splitlines()[0] in r.text
    assert 'hints' not in saved()

def test_the_default_is_served_from_the_cache_on_the_second_run(lr, fake):
    tryit._cache.clear()
    fake.rules['Give hint level'] = ECHO
    first = tryit.try_it('hints', DRAFT, fake, lr)
    n = len(fake.calls)
    second = tryit.try_it('hints', DRAFT.replace('1', 'one'), fake, lr)
    assert len(fake.calls) == n + 1 and not first.default.cached and second.default.cached and second.default.text == first.default.text

def test_every_prompt_has_a_runner_or_a_screen():
    from abhyasa.blocks.settings.ui import registry
    assert not [n for n in registry() if n not in tryit.RUNNERS and n not in tryit.SCREENS]
    assert not set(tryit.RUNNERS) & set(tryit.SCREENS) and not [n for n in {*tryit.RUNNERS, *tryit.SCREENS} if n not in registry()]

def test_each_runner_calls_its_real_reader(lr, fake):
    from abhyasa.learner import PROMPTS
    fake.rules['Give hint level'] = ECHO
    for n in tryit.RUNNERS:
        tryit._cache.clear()
        r = tryit.try_it(n, PROMPTS[n].dflt, fake, lr)
        assert 'err' not in r.draft and 'err' not in r.default, (n, r)

def test_a_prompt_with_no_runner_names_its_screen(mk):
    page = mk().get('/settings').text
    item = page.split('id="pr-build-agent"')[1].split('</details>')[0]
    assert 'No Try it here' in item and 'Try it</button>' not in item
    item = page.split('id="pr-hints"')[1].split('</details>')[0]
    assert 'Try it</button>' in item and 'hx-target="#try-pr-hints"' in item and 'id="try-pr-hints"' in item and 'hx-indicator="#wait-pr-hints"' in item and 'id="wait-pr-hints"' in item
