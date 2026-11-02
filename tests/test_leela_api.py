"Leela imports these. Remove one only with a Leela change."
import importlib, pytest

NAMES = {'learner': 'Learning slugify recall understanding update METHODS TEXT_WAYS PROMPTS prompt register set_prompt',
         'sources': 'WEB source_of VaultSource', 'path': 'walk_state', 'stagekit': 'is_local room_spec',
         'contract': 'validate_nb_spec vault_key handoff read_handoff run_ok path_why RUN_IMAGES LEELA_ROUTE HANDOFF_CASES HANDOFF_BAD NB_SPEC_CASES RUN_CASES '
                     'SAFE_NAMES SAFE_NODES safe_test check_exercise',
         'tutor': 'HINTS TUTOR_SP', 'show': 'explain norm_tex stream_board show_reply TALK_SCHEMA TALK_CASES check_talk new_run',
         'models': 'Router route_ask', 'core.stage': 'STAGE_V STAGE_TYPES STAGE_CASES'}

@pytest.mark.parametrize('mod', NAMES)
def test_leela_names_import(mod):
    m = importlib.import_module(f'abhyasa.{mod}')
    assert not [n for n in NAMES[mod].split() if not hasattr(m, n)]

def test_leela_learning_methods():
    "`abhyasa.path` and `abhyasa.show` add these to `Learning`."
    import abhyasa.path, abhyasa.show  # noqa: F401
    from abhyasa.learner import Learning
    assert all(hasattr(Learning, n) for n in 'journey put_journey demo demos put_demo record_prediction'.split())
