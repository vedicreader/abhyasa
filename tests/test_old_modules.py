"The old engine modules stay importable for one or two releases: each name in their `__all__`, and each monkeypatch target of the tests."
import importlib, json, pytest
from pathlib import Path

OLD = json.loads((Path(__file__).parent/'data'/'old_names.json').read_text())   # the `__all__` of each old module in 0.0.16

@pytest.mark.parametrize('mod', OLD)
def test_old_names_import(mod):
    "`from abhyasa.<old> import <name>` works for each name that the old module exported."
    m = importlib.import_module(f'abhyasa.{mod}')
    assert not [n for n in OLD[mod].split() if not hasattr(m, n)]

REACH = [('research', 'web_search', 'research_step'), ('research', 'web_fetch', 'gather_tools'), ('research', 'ramabana_lead', 'gather'),
         ('research', 'ramabana_worker', 'gather'), ('research', '_ended', '_gather_end'), ('sources', 'gh_public', 'clone_repo'),
         ('sources', 'read_arxiv_html', 'file_link'), ('sources', 'arxiv_title', 'file_link'), ('sources', 'public_url', 'file_link'),
         ('sources', '_final', 'file_link'), ('llm', 'catalog', 'model_label'), ('llm', '_on_mac', 'model_label'), ('voice', 'cached', 'fetch'),
         ('voice', 'speak', 'Speaker'), ('voice', 'model_size', 'search_models'), ('voice', 'http_post', '_openai'),
         ('voice', '_pocket_load', '_pocket'), ('walk', 'nb_spec', 'leela_found'), ('journey', 'hands_most', 'cap_hands'),
         ('journey', 'walk_from_topic', 'cap_hands'), ('settings', 'val', 'set_val')]

def _globals(f): return f.__globals__ if hasattr(f, '__globals__') else vars(importlib.import_module(f.__module__))

@pytest.mark.parametrize('mod,name,user', REACH)
def test_old_monkeypatch_reaches_the_code(monkeypatch, mod, name, user):
    "A monkeypatch on `abhyasa.<old>.<name>` changes the name that the code which calls it reads."
    m, mark = importlib.import_module(f'abhyasa.{mod}'), object()
    monkeypatch.setattr(m, name, mark)
    assert _globals(getattr(m, user))[name] is mark
