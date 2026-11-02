"The old engine module names of 0.0.16 are gone: no alias, no view. Each name that an old module exported is in its new module."
import importlib, json, pytest
from pathlib import Path

OLD = json.loads((Path(__file__).parent/'data'/'old_names.json').read_text())   # the `__all__` of each old module in 0.0.16
NEW = dict(settings='learner', prompts='learner', store='learner', model='learner', method='learner', profile='learner', jobs='learner',
           llm='models', voice='models', ground='sources', sources='sources', detect='sources', tutor='tutor', nb='tutor', journey='path',
           walk='path', edit='path', course='path', research='path', guide='show', demo='show', talk='show')
MOVED = {('profile', 'LABELS'): 'learner.PROFILE_LABELS', ('method', 'LABELS'): 'learner.METHOD_LABELS', ('detect', 'source_of'): 'sources.kind_of',
         ('detect', 'fold'): 'sources.fold_trim', ('research', 'pick_prompt'): 'sources.passage_prompt', ('research', 'PICK_SP'): 'sources.PASSAGE_SP',
         ('guide', 'KINDS'): 'show.GUIDE_KINDS', ('demo', 'KINDS'): 'show.DEMO_KINDS'}   # a name that means another thing in the new module

def home(mod, name) -> tuple:
    "The new module and the new name of the old `abhyasa.<mod>.<name>`."
    return tuple(MOVED[mod, name].split('.')) if (mod, name) in MOVED else (NEW[mod], name)

@pytest.mark.parametrize('mod', [m for m in NEW if NEW[m] != m])
def test_old_module_is_gone(mod):
    "`import abhyasa.<old>` fails, so no code and no monkeypatch goes through an old name."
    with pytest.raises(ModuleNotFoundError): importlib.import_module(f'abhyasa.{mod}')

@pytest.mark.parametrize('mod', OLD)
def test_each_old_name_is_in_its_new_module(mod):
    "Each name in the `__all__` of an old module is in its new module, with its new name when `MOVED` gives one."
    assert not [n for n in OLD[mod].split() if not hasattr(importlib.import_module(f'abhyasa.{home(mod, n)[0]}'), home(mod, n)[1])]

def test_a_moved_name_is_not_the_same_name():
    "The new module has the moved name, and its plain name, if any, is another thing (for example `sources.source_of` is not `kind_of`)."
    import abhyasa.sources as s, abhyasa.path as p, abhyasa.show as w
    assert s.source_of is not s.kind_of and s.fold is not s.fold_trim and p.pick_prompt is not s.passage_prompt and w.DEMO_KINDS is not w.GUIDE_KINDS
