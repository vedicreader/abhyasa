"Leela imports these. Remove one only with a Leela change."
import importlib, pytest

NAMES = {'store': 'Learning slugify', 'sources': 'WEB source_of', 'journey': 'walk_state', 'stagekit': 'is_local room_spec',
         'contract': 'validate_nb_spec vault_key handoff read_handoff run_ok RUN_IMAGES LEELA_ROUTE HANDOFF_CASES HANDOFF_BAD NB_SPEC_CASES RUN_CASES',
         'model': 'recall understanding update', 'method': 'METHODS TEXT_WAYS', 'prompts': 'PROMPTS prompt register set_prompt',
         'tutor': 'HINTS TUTOR_SP', 'walk': 'run_ok', 'guide': 'explain norm_tex stream_board', 'ground': 'VaultSource',
         'llm': 'Router route_ask', 'talk': 'TALK_SCHEMA TALK_CASES check_talk new_run', 'core.stage': 'STAGE_V STAGE_TYPES STAGE_CASES',
         'demo': '', 'settings': ''}

@pytest.mark.parametrize('mod', NAMES)
def test_leela_names_import(mod):
    m = importlib.import_module(f'abhyasa.{mod}')
    assert not [n for n in NAMES[mod].split() if not hasattr(m, n)]

def test_leela_learning_methods():
    "`abhyasa.journey` and `abhyasa.demo` add these to `Learning`."
    import abhyasa.journey, abhyasa.demo  # noqa: F401
    from abhyasa.store import Learning
    assert all(hasattr(Learning, n) for n in 'journey put_journey demo demos put_demo record_prediction'.split())
