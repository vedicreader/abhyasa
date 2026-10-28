"The session page as a conversation: each question is a short thread in one scroll, and the composer stays at the bottom."
from pathlib import Path
from fasthtml.common import *
from fastcore.utils import AttrDict
from abhyasa.core import n_of, moved_words, Cites, Md, DepthBar, when, run, asset_css, asset_js, Check, Msg, Tag, FirstError, OUTCOMES, Confidence as Sure, Primary
from abhyasa.model import DEPTHS
from abhyasa.settings import val
from abhyasa.method import LABELS as WAYS
from .cfg import Routes

_P = Path(__file__).parent
OUTCOME = {k: OUTCOMES[k][0] for k in ('solid', 'fragile', 'misconception', 'gap')}
WORDS = {1: 'One more try', 2: 'Two more tries'}
GRADING, HINTING, TEACHING, NEXT = 'Grading…', 'Writing a hint…', 'Writing a lesson…', 'Thinking of the next question…'
OPT_KEYS = '1234'   # no ⌥: the cursor is on an option, not in a box (session.js)

def assets(): return asset_css(_P/'session.css'), asset_js(_P/'session.js')

def tl_id(q): return f'tl-{q.id}'

# --- the chat: one section for each question ---------------------------------------------------------------------

def Head(q):
    "The concept and depth as a small label, then why the tutor chose it: the quiet rule between questions."
    way = Span(f" · {WAYS[q.method].lower()}", cls='way', title='the way the tutor teaches this question') if q.get('method') in WAYS else ''
    return Div(Span(f"{q.name} · {DEPTHS[q.depth]}", way, DepthBar(q.get('floor', 0), asked=q.depth), cls='lbl'), P(q.why, cls='why'), cls='head')

def Options(sid, q, chosen=(), done=False, oob=False, right=None):
    "The options of a choice question, inline in the question. A wrong pick is struck, a right pick marked; all go off when the question closes."
    def opt(i, o):
        k = OPT_KEYS[i] if i < len(OPT_KEYS) else ''
        return Button(Md(o), Kbd(k) if k and not done else '', name='answer', value=str(i), id=f'o{i}' if not done else None,
                      cls='opt' + (' right' if o == right else ' tried' if o in chosen else ''), disabled=done or o in chosen,
                      hx_post=Routes.at(Routes.answer, sid), hx_include='#composer', hx_target=f'#{tl_id(q)}', hx_swap='beforeend',
                      data_wait=GRADING, data_skel=f'#{tl_id(q)}')
    return Div(*[opt(i, o) for i, o in enumerate(q.options)], cls='opts', id=f'opts-{q.id}', hx_swap_oob='true' if oob else None)

def Asked(sid, q):
    "The question, with its options for a choice question."
    return Div(Md(q.question, cls='q'), Options(sid, q) if q.get('options') else '', cls='ask')

def Section_(sid, q, entries=()):
    "One question and its thread so far, in the same check card as the walk. The composer stays at the foot of the window."
    return Check(Head(q), Asked(sid, q), *entries, thread_id=tl_id(q), cls='qa', id=f'q-{q.id}')

def Chat(sid, cur=None, waiting=False, viewing=None):
    "One question at a time: the open one, or a past one that you opened from the list (read only)."
    if viewing: return Div(P(A('← Back to the current question', href=Routes.at(Routes.page, sid)), cls='mute back'), Section_(sid, *viewing),
                           id='chat', data_sid=sid, cls='viewing')
    return Div(Section_(sid, *cur) if cur else '', Waiting(sid) if waiting else '', id='chat', data_sid=sid)

def Rail(sid, past=(), outcomes=None, current=None, viewing=None, oob=False):
    "The earlier questions of this sitting, one quiet line each; a click opens one. ⌥↑ and ⌥↓ step through them."
    outcomes = outcomes or {}
    def row(q):
        oc = OUTCOME.get(outcomes.get(q.id, ''), '')
        return Li(A(Span(q.name, cls='n'), Span(' · '.join(x for x in (DEPTHS[q.depth], oc) if x), cls='mute'),
                    href=f"{Routes.at(Routes.page, sid)}?q={q.id}"), cls='on' if viewing == q.id else None, data_q=q.id)
    cur = Li(A(Span(current.name, cls='n'), Span('now', cls='mute'), href=Routes.at(Routes.page, sid)), cls='now' + (' on' if not viewing else '')) if current else ''
    return Details(Summary(f'Earlier questions ({len(past)})'), Ol(*map(row, past), cur, cls='rail-list'),
                   open=True, id='rail', cls='rail', hx_swap_oob='true' if oob else None)

def You(text, thinking='', confidence=None):
    "One message of yours: what you said this time, at the left in a quieter ink, as in the walk."
    return Msg('You' + (f' · {confidence}% sure' if confidence is not None else ''),
               Md(text, cls='said') if text else P('No answer.', cls='said none'),
               Div(Span('Thinking: ', cls='k'), Md(thinking), cls='thought') if thinking else '', cls='you')

def Nudge(r):
    "The tutor's reply to a wrong try: what to look at next, and the first error."
    return Msg(Tag('nudge'), Md(r.feedback) if r.feedback else '', FirstError(r.first_error), cls='tutor fb no')

def Hint(n, text):
    "A hint, at the time you asked for it."
    return Msg(f'Hint {n}', Md(text), cls='tutor hint')

def Lesson(text, way=''):
    "A lesson under the outcome; `way` names the method of a lesson that you asked for in another way."
    return Div(Span('Lesson' + (f' · {WAYS[way].lower()}' if way in WAYS else ''), cls='lbl'), Md(text), cls='lesson')

def Now(r):
    "Your level on the concept now, and the next review, in plain words."
    return P(f"{f'Your level: {DEPTHS[r.floor]}.' if r.floor else 'Not at a level yet.'} Next review {when(r.due)}.", cls='mute now')

def TeachMe(sid, qid):
    "After a shaky pass: a lesson only when you ask for it. ⌥X asks."
    return Button('Teach me this ', Kbd('⌥X'), id='teach', type='button', hx_post=Routes.at(Routes.teach, sid), hx_vals={'qid': qid},
                  hx_target='this', hx_swap='outerHTML', data_wait=TEACHING)

def AnotherWay(sid, qid):
    "Under a lesson: the same idea in a different way. ⌥A asks."
    return Button('Another way ', Kbd('⌥A'), id='another', type='button', hx_post=Routes.at(Routes.teach, sid), hx_vals={'qid': qid, 'another': 1},
                  hx_target='this', hx_swap='outerHTML', data_wait=TEACHING)

def Close(r, said='', sid=None, qid=None):
    "The last message on a question: the outcome, the lesson and the next review. A shaky pass can ask for a lesson."
    fb = r.feedback if r.correct or not r.lesson else ''   # after a miss the lesson speaks; the last nudge would ask a question nobody answers
    return Msg(Tag(r.outcome, said), Md(fb) if fb else '',
              Lesson(r.lesson) if r.lesson else '',
              AnotherWay(sid, qid) if sid and r.lesson else '',
              TeachMe(sid, qid) if sid and r.outcome == 'fragile' and not r.lesson else '',
               Cites(r.get('grounds')), Now(r),
               cls=f"tutor fb close {'ok' if r.correct else 'no'}")

def Turns(turns):
    "The messages of a question drawn again from its thread: after a restart, or for a question of an earlier run."
    out, n = [], 0
    for t in turns:
        if t['who'] == 'you': out.append(You(t.get('text', ''), t.get('thinking', ''), t.get('confidence')))
        elif t.get('kind') == 'nudge': out.append(Nudge(AttrDict(feedback=t.get('text', ''), first_error=t.get('first_error', ''))))
        elif t.get('kind') == 'hint': n += 1; out.append(Hint(n, t.get('text', '')))
        elif t.get('kind') == 'lesson': out.append(Msg(Lesson(t.get('text', '')), cls='tutor fb close ok'))
        elif t.get('kind') == 'close':
            ok = t.get('outcome') in ('solid', 'fragile')
            out.append(Msg(Tag(t.get('outcome')), Md(t['text']) if t.get('text') and (ok or not t.get('lesson')) else '',
                           Lesson(t['lesson']) if t.get('lesson') else '', cls=f"tutor fb close {'ok' if ok else 'no'}"))
    return out

def Extras(r):
    "What other blocks add after the close, such as a demo under the lesson: each one is a tutor message in the thread."
    return [Msg('', x, cls='tutor extra') for x in run('lesson_extra', r)]

def Skeleton(label):
    "A placeholder question while the model writes it."
    return Div(Div(Span(label, cls='lbl'), cls='head'), Div(I(), I(), I(cls='short'), cls='skel q'), cls='skeleton')

def Waiting(sid):
    "A section that loads the question that is fetched ahead."
    return Section(Skeleton(NEXT), cls='qa waiting', data_wait=NEXT, hx_get=Routes.at(Routes.card, sid), hx_trigger='load', hx_swap='outerHTML')

# --- the composer: fixed at the bottom; its state follows the question -----------------------------------------------

def Confidence():
    "Five steps for how sure you are; ⌥1 to ⌥5 pick one."
    return Sure(keys=True)

def Left(n=None, **kw):
    "The tries that are left; empty before the first try."
    return Span(f'{WORDS.get(n, f"{n} more tries")}.' if n else '', id='left', cls='left mute', **kw)

def Composer(sid, q=None, ready=None, oob=False):
    "The bottom bar: your message, your thinking, how sure you are, and the actions. After the close it holds Next."
    at = lambda r: Routes.at(r, sid)
    kw = dict(id='composer', cls='composer', hx_swap_oob='true' if oob else None)
    if q is None:   # closed, or the first question is not written yet
        nxt = Primary('Next', id='send', hx_post=at(Routes.next), hx_target='#chat', hx_swap='innerHTML',
                      data_wait=NEXT, data_skel='#chat', focus=True) if ready is not None else ''
        return Div(Div(Ready(sid, ready) if ready is not None else Span('Writing the first question', cls='ready mute wait'),
                       A('End session', href=at(Routes.end), cls='btn quiet'), nxt, cls='row bar'), **kw)
    tl = dict(hx_target=f'#{tl_id(q)}', hx_swap='beforeend', data_skel=f'#{tl_id(q)}')
    tried, out = bool(q.get('tries')), Out(sid, q)
    choice = bool(q.get('options'))
    boxes = ([] if choice else [Textarea(name='answer', id='ans', rows=2, autofocus=True, aria_label='Your answer',
                                         placeholder='Your answer, or a follow-up. ⌘↵ sends.')]) + [
             Textarea(name='thinking', id='think', rows=1, aria_label='Think aloud',
                      placeholder='Think aloud: how did you get there? What are you not sure of?')]
    acts = ([out] if choice else [out, Button('Hint ', Kbd('⌥W'), type='button', id='hint', cls='quiet', hx_post=at(Routes.hint), data_wait=HINTING, **tl),
                                   Primary('Send', id='send', data_wait=GRADING)])
    return Form(*boxes, Div(*run('answer_tools', q, 'think' if choice else 'ans'), Confidence(), Left(val('checks.tries') - len(q.tries) if tried else None),
                            Span(cls='grow'), *acts, cls='row bar'),
                hx_post=at(Routes.answer), **tl, **kw)

def Out(sid, q, oob=False):
    "The way out: I don't know before the first try, Teach me after it. ⌥X presses it."
    t = f'#{tl_id(q)}'
    return Button('Teach me ' if q.get('tries') else "I don't know ", Kbd('⌥X'), type='button', id='idk', cls='quiet',
                  hx_post=Routes.at(Routes.giveup, sid), hx_vals='{"dont_know": 1}', hx_include='#conf', hx_target=t, hx_swap='beforeend',
                  data_wait=TEACHING, data_skel=t, hx_swap_oob='true' if oob else None)

def Ready(sid, ready):
    "Whether the next question is written yet; it asks again each second, out of the progress bar."
    if ready: return Span('The next question is ready.', cls='ready mute', id='ready')
    return Span('Writing the next question', cls='ready mute wait', id='ready', data_quiet='1',
                hx_get=Routes.at(Routes.ready, sid), hx_trigger='load delay:1s', hx_swap='outerHTML')

def Done():
    "A session that is not here any more: the ways out."
    return (Section(H1('This session is over'), P(A('Your learning', href='/learning'), ' · ', A('Today', href='/')), cls='qa done'),
            Div(id='composer', hx_swap_oob='true'))

def Moved(m):
    "One concept of the session: from what depth to what depth, and how many passed."
    up, down = m['after'] > m['before'], m['after'] < m['before']
    said, count = moved_words(m)
    return Li(A(m['name'], href=f"/c/{m['concept']}"), DepthBar(m['after']), ' ',
              Span(said, cls='moved up' if up else 'moved down' if down else 'moved'),
              Span(f"  · {count}", cls='mute') if count else '',
              *([P('Misconception: ', ', '.join(m['misconceptions']), cls='mute mis')] if m['misconceptions'] else []))

def EndPage(s, ms, j=None, pg=None, rel=()):
    "The end of a session: what moved, in plain words; then what comes next, one key away."
    n, ok = len(s.log), sum(r['correct'] for r in s.log)
    up = [m for m in ms if m['after'] > m['before']]
    mis = sum(len(m['misconceptions']) for m in ms)
    mins = max(1, round(((s.ended or s.start) - s.start) / 60))
    lead = ' '.join(x for x in (
        f"{n_of(len(up), 'concept')} moved up." if up else 'Nothing moved up this time. The misses show what to work on next.' if n else 'No questions this time.',
        f"You found {n_of(mis, 'misconception')}." if mis else '') if x)
    nxt = []
    if j and pg:
        nxt = [H2('Your journey'), P(A(j.title, href=f'/j/{j.id}'), Span(f"  {pg.done} of {n_of(pg.total, 'step')}", cls='mute')),
               Span(I(style=f"width:{100 * pg.done // max(pg.total, 1)}%"), cls='prog'),
               P(f"Next step: {pg.current.name}." if pg.current else 'You finished this journey.', cls='next-step'),
               Div(Primary('Continue the journey', href=f'/start?journey={j.id}') if pg.current else
                   Primary('See what comes after', href=f'/j/{j.id}'), cls='row')]
    elif rel:
        nxt = [H2('Related topics'), Ul(*[Li(A(c.name, href=f'/c/{c.slug}'), DepthBar(c.floor), ' ',
                                             A('Learn', href=f'/start?focus={c.slug}', cls='btn small quiet')) for c in rel], cls='plain related')]
    return (H1('Done for now' if n else 'Session'), P(f"{ok} of {n} passed · about {mins} min. ", lead, cls='lead-sum'),
            *([H2('What moved'), Ul(*map(Moved, ms), cls='plain moved-list')] if ms else []),
            *nxt,
            Div(A('Your learning', href='/learning', cls='btn quiet'), A('Today ', Kbd('⌥T'), href='/', cls='btn quiet'), cls='row'))
