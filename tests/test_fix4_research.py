"When research cannot search the web, the step says so and does not claim that the web is empty. Fixed fakes, no network."
from abhyasa.models import Fake
from abhyasa.path import walk_from_topic, research_step, _search, FOUND_NOTHING, NO_QUOTE

EMPTY = 'Web search returned no results; search engines may have blocked it. This step can be grounded later.'
BLOCKED = 'The web search was blocked or unavailable. This step can be grounded later.'


def one_step_walk(lr):
    "A walk with one idea and no source, and the fake that planned it."
    fake = Fake({'You plan a learning path': dict(title='Navamsa', steps=[dict(name='Nine parts in each sign', statement='Divide each sign into nine equal parts.')])})
    return fake, walk_from_topic(lr, fake, 'Learn navamsa', near=False)


def no_fetch(url): raise AssertionError(f'a test tried to fetch {url}')


def test_an_empty_search_says_that_a_block_is_possible(lr):
    "A search that returns nothing is not proof that the web has nothing: the line says that the engines may have blocked it."
    fake, j = one_step_walk(lr)
    assert research_step(lr, fake, j.id, 0, search=lambda q, n: [], fetch=no_fetch) is None
    s = lr.journey(j.id).steps[0]
    assert (s['research'], s['research_why']) == ('none', EMPTY) and FOUND_NOTHING == EMPTY
    assert 'found nothing' not in s['research_why'].lower()


def test_a_search_that_raises_says_it_was_blocked_or_unavailable(lr):
    "A search that raises is a failure, not an empty web: research keeps that status and the step says the search was blocked or unavailable."
    fake, j = one_step_walk(lr)
    asked = []
    def boom(q, n): asked.append(q); raise RuntimeError('every backend failed')
    assert research_step(lr, fake, j.id, 0, search=boom, fetch=no_fetch) is None
    s = lr.journey(j.id).steps[0]
    assert (s['research'], s['research_why']) == ('none', BLOCKED), s
    assert len(asked) == 2   # both queries were tried


def test_a_failed_search_still_gives_an_empty_list_to_other_callers(lr):
    "`_search` still returns a list for the gather tool: empty when the search fails or finds nothing."
    def boom(q, n): raise RuntimeError('no search')
    assert list(_search(boom, 'q', 5)) == [] and list(_search(lambda q, n: [], 'q', 5)) == []
    assert [h.url for h in _search(lambda q, n: [dict(title='A', href='https://example.org/a')], 'q', 5)] == ['https://example.org/a']


def test_a_search_with_results_keeps_its_other_lines(lr):
    "A search that gave results but no usable quote keeps `NO_QUOTE`, even when another query failed."
    fake, j = one_step_walk(lr)
    calls = []
    def search(q, n):
        calls.append(q)
        if len(calls) == 2: raise RuntimeError('blocked')
        return [dict(title='A page', href='https://example.org/a')]
    def fetch(url): raise OSError('timed out')
    research_step(lr, fake, j.id, 0, search=search, fetch=fetch)
    why = lr.journey(j.id).steps[0]['research_why']
    assert why not in (EMPTY, BLOCKED) and why.startswith('The page could not be read'), why