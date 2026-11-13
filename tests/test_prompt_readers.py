import importlib, inspect

from abhyasa.learner import PROMPTS

MODULES = [importlib.import_module(f'abhyasa.{m}') for m in ('learner', 'tutor', 'path', 'sources', 'show')]

# prompt key -> the functions whose own source reads it (`module.qualname`). A name that is nested in another function is given by the outer one.
READERS = {
    'ways': ['abhyasa.learner.way'],
    'profile.onboard': ['abhyasa.learner.onboard'],
    'profile.observe': ['abhyasa.learner.observe'],
    'teach.human': ['abhyasa.learner.teach_sp'],
    'depths': ['abhyasa.tutor.depth_ask'],
    'tutor': ['abhyasa.tutor.Tutor.ask_on', 'abhyasa.tutor.Tutor.hint', 'abhyasa.tutor.Tutor._lesson'],
    'question': ['abhyasa.tutor.question_prompt'],
    'grade': ['abhyasa.tutor.Tutor._grade', 'abhyasa.show.grade_why'],
    'hints': ['abhyasa.tutor.hints'],
    'lesson': ['abhyasa.tutor.teach_prompt'],
    'core': ['abhyasa.sources.understand'],
    'extract': ['abhyasa.sources._read'],
    'concepts.sort': ['abhyasa.sources.propose_groups'],
    'research.pick': ['abhyasa.sources.pick_passage'],
    'walk.plan': ['abhyasa.path.plan'],
    'walk.pick': ['abhyasa.path.main_steps'],
    'walk.map': ['abhyasa.path.walk_map'],
    'primer': ['abhyasa.path.topic_slug', 'abhyasa.path.name_gaps'],
    'walk.note': ['abhyasa.path.tutor_note'],
    'walk.note_topic': ['abhyasa.path.tutor_note'],
    'walk.code': ['abhyasa.path.write_code'],
    'walk.notebook': ['abhyasa.path.nb_spec'],
    'walk.gloss': ['abhyasa.path.term_line'],
    'edit.rewrite': ['abhyasa.path.rewrite'],
    'edit.improve': ['abhyasa.path.propose'],
    'edit.fix': ['abhyasa.path.propose'],
    'course.level': ['abhyasa.path.level_questions'],
    'course.stages': ['abhyasa.path.plan_stages'],
    'research.lead': ['abhyasa.path.gather'],
    'research.more': ['abhyasa.path._more_queries'],
    'guide.figure': ['abhyasa.show.figure_labels'],
    'guide.board': ['abhyasa.show.explain'],
    'demo.feedback': ['abhyasa.show.feedback_line'],
    'lesson.feedback': ['abhyasa.show.feedback_line'],
    'demo.order': ['abhyasa.show.make_demo'],
    'demo.simpler': ['abhyasa.show.make_demo'],
    'demo.images': ['abhyasa.show.make_demo'],
    'demo.asked': ['abhyasa.show.make_demo', 'abhyasa.show.explainer_prompt'],
    'demo.values': ['abhyasa.show.make_demo'],
    'demo.explainer': ['abhyasa.show.explainer_sp'],
    'demo.gates': ['abhyasa.show.explainer_prompt'],
    'demo.gave': ['abhyasa.show.explainer_for'],
    'talk.choice': ['abhyasa.show.ask_from_check'],
    'talk.slide': ['abhyasa.show.fill_slide'],
    'talk.poll': ['abhyasa.show.poll_slide'],
    'build.agent': ['abhyasa.blocks.build.app.connect'],
}

# keys that the reader builds instead of writing: the text of the reader that stands for them
BUILT = {'demo.feedback': '.feedback', 'lesson.feedback': '.feedback', 'demo.order': 'AIMS', 'demo.simpler': 'AIMS'}

def reader(name):
    parts = name.split('.')
    for i in range(len(parts) - 1, 0, -1):
        try: o = importlib.import_module('.'.join(parts[:i]))
        except ModuleNotFoundError: continue
        for p in parts[i:]: o = getattr(o, p)
        return o

def bound(key):
    "The names of the module constants that hold the default text of `key`."
    return [n for m in MODULES for n, v in vars(m).items() if n.isupper() and v is PROMPTS[key].dflt]

def test_every_prompt_has_readers_that_mention_it():
    problems = [f'{k}: not in READERS' for k in PROMPTS if k not in READERS] + [f'{k}: not a registered prompt' for k in READERS if k not in PROMPTS]
    for k, names in READERS.items():
        for n in names:
            if (f := reader(n)) is None: problems.append(f'{k}: {n} does not exist'); continue
            src = inspect.getsource(f)
            if not any(w in src for w in (f"'{k}'", f'"{k}"', *bound(k), *([BUILT[k]] if k in BUILT else []))): problems.append(f'{k}: {n} does not mention it')
    assert not problems, problems
    from abhyasa.show import AIMS
    assert AIMS == dict(order='demo.order', simpler='demo.simpler')