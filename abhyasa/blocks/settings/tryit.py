"Try it: run one prompt on a small sample, once with the draft text and once with the default text, through the code that reads it."
import hashlib, json, threading, time
from fastcore.basics import AttrDict
from abhyasa.learner import PROMPTS, METHODS, use_prompts, saved, lines, ways_of, teach_sp, prompt
from abhyasa.models import for_task, ask_json

SAMPLE = dict(name='Reciprocal rank fusion', statement='Merge ranked lists by adding 1/(k + rank) for each list.',
              question='Why does reciprocal rank fusion ignore the raw scores of each list?',
              answer='Scores from different rankers are not on one scale, so it adds 1/(k + rank) from the positions instead.',
              said='Because the scores are all different, so it adds them up.', first_error='It adds the raw scores, not the positions.')

def own_item(lr) -> dict:
    "The last attempt that has a question, an answer and a concept with a statement, as a sample; else `SAMPLE`."
    for a in lr.attempts(limit=20):
        c = lr.concept(a.concept)
        if c and a.get('question') and a.get('answer') and (c.get('core') or c.get('statement')):
            return dict(name=c.name, statement=c.get('statement') or c.core, question=a.question, answer=c.get('core') or c.statement, said=a.answer, first_error=a.get('first_error') or '')
    return SAMPLE

def _changed(draft:str, old:list) -> int:
    "The index of the first of `old` that the lines of `draft` change, else 0."
    new = lines(draft)
    return next((i for i, (a, b) in enumerate(zip(new, old)) if a != b), 0) if len(new) == len(old) else 0

def _q(s:dict) -> AttrDict: return AttrDict(name=s['name'], statement=s['statement'], question=s['question'], answer=s['answer'], depth=3, hints=[], tries=[])

def hints_sample(lr, text:str) -> dict:
    from abhyasa.tutor import HINTS
    return dict(own_item(lr), level=_changed(text, HINTS))

def ways_sample(lr, text:str) -> dict:
    "The sample of a hint in the first way that the draft changes (the first way, when none changed)."
    new = ways_of(text)
    return dict(own_item(lr), level=2, method=next((m for m in METHODS if new.get(m) != METHODS[m]), next(iter(METHODS))))

def hints_run(ask, s:dict) -> str:
    from abhyasa.tutor import hint_prompt
    return for_task(ask, 'hint')(hint_prompt(AttrDict(_q(s), method=s.get('method')), s['level']), teach_sp('tutor')).strip()

def question_sample(lr, text:str) -> dict:
    from abhyasa.tutor import DEPTH_ASK
    return dict(own_item(lr), depth=_changed(text, DEPTH_ASK.splitlines()) + 1)

def question_run(ask, s:dict) -> str:
    from abhyasa.tutor import question_prompt
    c = AttrDict(name=s['name'], statement=s['statement'], subject='', floor=0, ceiling=6)
    r = ask_json(for_task(ask, 'question'), question_prompt(c, s['depth']), teach_sp('tutor'), need=('question',))
    return f"{r['question']}\n\nModel answer: {r.get('answer', '')}"

def own_sample(lr, text:str) -> dict: return own_item(lr)

def grade_run(ask, s:dict) -> str:
    from abhyasa.tutor import grade_prompt
    g = ask_json(for_task(ask, 'grade'), grade_prompt(_q(s), s['said']), prompt('grade'))
    return f"Grade {g.get('grade')} of 10 · core met: {g.get('core_met')}\n\n{g.get('feedback', '')}"

def lesson_run(ask, s:dict) -> str:
    from abhyasa.tutor import teach_prompt
    return for_task(ask, 'lesson')(teach_prompt(_q(s), s['first_error']), teach_sp('tutor')).strip()

RUNNERS = dict(hints=(hints_sample, hints_run), ways=(ways_sample, hints_run), depths=(question_sample, question_run), question=(question_sample, question_run),
               tutor=(own_sample, lesson_run), lesson=(own_sample, lesson_run), **{'teach.human': (own_sample, lesson_run)}, grade=(own_sample, grade_run))   # prompt name -> (the sample, from the learner's data and the draft; one call on it)

AGENT_OR_PAGE = frozenset(('guide.figure', 'guide.board', 'walk.notebook', 'demo.explainer', 'research.lead', 'build.agent'))   # they run an agent loop or need a whole page
LATER = frozenset(('profile.onboard', 'profile.observe', 'core', 'extract', 'concepts.sort', 'research.pick', 'research.more', 'walk.plan', 'walk.pick', 'walk.map', 'primer',
                   'walk.note', 'walk.note_topic', 'walk.code', 'walk.gloss', 'edit.rewrite', 'edit.improve', 'edit.fix', 'course.level', 'course.stages',
                   'demo.feedback', 'lesson.feedback', 'demo.order', 'demo.simpler', 'demo.images', 'demo.asked', 'demo.values', 'demo.gates', 'demo.gave',
                   'talk.choice', 'talk.slide', 'talk.poll'))   # single calls with no runner yet: each reader needs a walk, a talk or a saved concept that it would change
SCREENS = AGENT_OR_PAGE | LATER

_cache, _lock = {}, threading.Lock()

def _run(name:str, text:str, run, ask, s:dict) -> AttrDict:
    t = time.time()
    try:
        with use_prompts({name: text}): out = run(ask, s)
    except Exception as e: return AttrDict(err=f'{type(e).__name__}: {str(e)[:200]}')
    return AttrDict(text=out, secs=round(time.time() - t, 1))

def try_it(name:str, text:str, ask, lr) -> AttrDict:
    "Run prompt `name` on its sample with the draft `text` and with its default. The default result is kept by name, default text, sample and the other saved texts. Nothing is saved."
    sample, run = RUNNERS[name]
    s = sample(lr, text)
    others = {k: v for k, v in saved().items() if k != name}
    key = (name, hashlib.sha1(PROMPTS[name].dflt.encode()).hexdigest(), json.dumps(s, sort_keys=True), json.dumps(others, sort_keys=True))
    with _lock: hit = _cache.get(key)
    cached = hit is not None
    if not cached:
        hit = _run(name, '', run, ask, s)
        if 'err' not in hit:
            with _lock: _cache[key] = hit
    return AttrDict(draft=_run(name, text, run, ask, s), default=AttrDict(hit, cached=cached))