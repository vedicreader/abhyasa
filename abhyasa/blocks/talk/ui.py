"The talk on the page: the editor with one row for each slide (an `EditList`: each field saves at once, with an Undo), and the parts on other pages."
import json, math, re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from fasthtml.common import *
from rupaka.render import Demo, version
from abhyasa.core import Primary, Secondary, Quiet, Part, Md, Inline, Cites, SourceLine, meta, n_of, asset_css, asset_js, stage_assets, edit_assets, EditList, Live, UndoBar, HistoryList
from fastcore.basics import AttrDict
from abhyasa.talk import talk_minutes, public_ask, share_right, needs_fill, slide_source, GONE, parked
from abhyasa.settings import val
from .cfg import Routes

_P = Path(__file__).parent
KINDS = dict(choice='Choice', order='Order', words='Short answer', scale='Scale', run='What does this print?', none='No question')
SHOWS = dict(passage='passage', body='points', figure='figure', demo='live demo')
ENDS = dict(questions='the questions from the room, or your notes', recap='made at the end from what the room answered')

def assets(): return asset_css(_P/'talk.css'), asset_js(_P/'talk.js')

def editor_assets(): return (*edit_assets(), *assets())

def rupaka_assets():
    "The rupaka runtime that the demo block serves, for the live demo of a slide."
    v = version()
    return Link(rel='stylesheet', href=f'/rupaka/rupaka.css?v={v}'), Script(src=f'/rupaka/rupaka.js?v={v}')

def at(r, tid): return Routes.of(r, tid=tid)

_PAIR = re.compile(r'\$\$.+?\$\$|(?<!\\)\$[^$]+?(?<!\\)\$')   # a `$…$` or `$$…$$` pair of maths

def short(s, n=140):
    "`s` cut to about `n` characters at a space, with `…`. A cut never splits a pair of maths: it goes before the pair, or after it at the start."
    s = ' '.join(str(s or '').split())
    if len(s) <= n: return s
    m = first(m for m in _PAIR.finditer(s) if m.start() < n < m.end())
    if m: return (s[:m.start()].rstrip() if m.start() else s[:m.end()]) + '…'
    return s[:n].rsplit(' ', 1)[0] + '…'

# --- on other pages --------------------------------------------------------------------------------------------------

def PresentWalk(jid, t=None, quiet=False):
    """Make a talk from walk `jid`: the button gives way to the pending card. When talk `t` was made from it before: open that talk, or make it again
    from the walk (`again`), with your edits. `quiet` is for a page that has its own main button (the step page, the last page)."""
    btn = (lambda *a, **kw: Quiet(*a, small=True, **kw)) if quiet else Secondary
    go = Form(Input(type='hidden', name='jid', value=jid), *again_input(t), btn('Make the talk again (keeps your edits)' if t else 'Present this walk', data_wait='Making the talk…'),
              hx_post=Routes.new, hx_target='this', hx_swap='outerHTML', cls='talk-new')
    if not t: return go
    second = Form(Input(type='hidden', name='jid', value=jid), Quiet('Make a second talk', small=True, data_wait='Making the talk…'),
                  hx_post=Routes.new, hx_target='this', hx_swap='outerHTML', cls='talk-new')   # the old way: a new talk, with no edits
    if quiet: return Div(btn('Open the talk', href=at(Routes.one, t.id)), Details(Summary('More'), go, second, cls='talk-more'), cls='row')   # a page with its own main button shows one way to the talk; the rest is under More
    return Div(btn('Open the talk', href=at(Routes.one, t.id)), go, Details(Summary('More'), second, cls='talk-more'), cls='row')

def again_input(t): return (Input(type='hidden', name='again', value='1'), Input(type='hidden', name='tid', value=t['id'])) if t else ()

def AgainLine(t, jid, ch):
    "The walk `jid` changed after talk `t` was made (`ch`, from `walk_changes`): what changed, and Make it again for this talk. Nothing when nothing changed."
    parts = [f"{n_of(ch[k], 'idea')} {k}" for k in ('added', 'removed', 'moved') if ch and ch.get(k)]
    n = (ch or {}).get('changed') or 0
    if not parts and not n: return ''
    said = ' '.join(x for x in (f"The walk changed after this talk was made: {', '.join(parts)}." if parts else '',
                                f"{n_of(n, 'idea')} changed in the walk. Make it again to take the changes." if n else '') if x)
    return Div(P(said, cls='mute'),
               Form(Input(type='hidden', name='jid', value=jid), *again_input(t), Secondary('Make it again', data_wait='Making the talk again…'),
                    Small(' Your edits to slides stay in the new talk where the idea is the same.', cls='mute'),
                    hx_post=Routes.new, hx_target='this', hx_swap='outerHTML', cls='talk-new'), cls='talk-again')

def RowPresent(jid, t=None, path=False):
    """The one quiet control on the row of walk `jid` in a list: "Open the talk" when talk `t` was made from it, else "Present", which makes the talk.
    `path` makes the talk from a path (a walk with no source)."""
    if t: return A('Open the talk', href=at(Routes.one, t.id), cls='quiet')
    return Form(Input(type='hidden', name='jid', value=jid), Quiet('Present', small=True, data_wait='Making the talk…', title='Make a talk from this walk'),
                hx_post=Routes.journey if path else Routes.new, hx_target='this', hx_swap='outerHTML', cls='talk-new')

def PresentJourney(jid, t=None):
    "Make a talk from path `jid` (a walk with no source). When talk `t` was made from it before: open that talk, or make it again."
    def go(label, *again): return Form(Input(type='hidden', name='jid', value=jid), *again, Secondary(label, data_wait='Making the talk…'),
                                      hx_post=Routes.journey, hx_target='this', hx_swap='outerHTML', cls='talk-new')
    if not t: return go('Present this walk')
    return Div(Secondary('Open the talk', href=at(Routes.one, t.id)), go('Make it again', Input(type='hidden', name='again', value='1')), cls='row')

def Pending(jid, fill=False, again=False):
    "A talk that is still being made, filled (`fill`) or made again (`again`): the card asks the server again in 2 seconds."
    said = (('Filling the slides…', 'The tutor writes the points and the speaker notes of each slide that has none. This can take a minute.') if fill else
            ('Making the talk again…', 'The tutor writes a slide for each new idea. Your edits to slides stay where the idea is the same.') if again else
            ('Making the talk…', 'The tutor writes the points and the speaker notes of each slide, and a question for the room from each check. This can take a minute.'))
    return Div(P(said[0]), P(said[1], cls='mute'),
               cls='talk-new pending', hx_get=f"{Routes.job}?{urlencode(dict(jid=jid))}", hx_trigger='load delay:2s', hx_swap='outerHTML')

def TalkRow(t):
    "One talk in Learn: its title, its slide count and its slot, then Edit and a quiet Present that starts a run."
    return Li(Div(A(t.title, href=at(Routes.one, t.id), cls='jt'), Span(meta(n_of(sum(not parked(s) for s in t.slides), 'slide'), f"a {t.minutes} min slot"), cls='mute'), cls='lrow-head'),
              Div(A('Edit', href=at(Routes.one, t.id), cls='btn small'),
                  Form(Quiet('Present', small=True, data_wait='Starting…'), action=at(Routes.start, t.id), method='post', hx_boost='false'), cls='lrow-acts'),
              cls='lrow')

def YourTalks(ts):
    "Your talks, in Learn: one row for each."
    return Part('Your talks', Ul(*[TalkRow(t) for t in ts], cls='plain talks'))

# --- the editor ------------------------------------------------------------------------------------------------------

FIELDS = dict(title='title', body='points', notes='speaker note', prompt='prompt', beats='beats', show='parts that show',
              ask='question', passage='passage', figure='figure')   # the names of the fields of a slide, for the Undo bar
CHIPS = ('Simpler', 'Add an example', 'Shorter')
REWRITE_HELP = 'The tutor rewrites the points and the note. It never changes the passage.'

def shows(s):
    "What slide `s` shows, as one short line."
    k, beats = s.get('kind'), s.get('beats') or []
    if k == 'pause': return meta(f"{s.get('secs', 120)} s", 'you added it')
    if k in ENDS: return ENDS[k]
    if k not in ('idea', 'primer'): return 'This slide kind shows in a later version.'
    parts = [SHOWS[b] for b in SHOWS if b in beats]
    lit = sum(str(b).startswith('lit:') for b in beats)
    return meta(*parts, n_of(lit, 'lit line') if lit else '', n_of(len(beats), 'beat') if len(beats) > 1 else '') or 'the title only'

def Mini(s):
    "A small picture of the slide: its section, its title and the start of its passage."
    sh = s.get('show') or {}
    return Div(Small(Inline(s.get('section') or '')), B(Inline(s.get('title') or '')), P(Inline(short(sh.get('passage') or ' '.join(sh.get('body') or []) or s.get('prompt') or '', 120))),
               I(cls='fig') if sh.get('figure') else '', cls='mini', aria_hidden='true')

def Field(label, el, help=''):
    return Label(label, el, Small(help, cls='mute help') if help else '')

def Right(sid, a, oob=False):
    "The line under the options that says which option is right. Only you see it."
    n = (a or {}).get('answer')
    said = f'Option {n + 1} is the right answer. The room does not see this.' if (a or {}).get('kind') == 'choice' and isinstance(n, int) else ''
    return P(said, cls='mute right-line', id=f'right-{sid}', **({'hx_swap_oob': 'true'} if oob else {}))

def Options(a, most=6):
    """One box for each option, with a radio button on the right one for a choice. An order shows its options in the right order;
    the talk mixes them for the room when it saves."""
    opts, ans = list(a.get('options') or []), a.get('answer')
    if a.get('kind') == 'order' and isinstance(ans, list) and sorted(ans) == list(range(len(opts))): opts = [opts[i] for i in ans]
    opts += [''] * (most - len(opts))
    right = ans if a.get('kind') == 'choice' else None
    return Fieldset(Legend('Options'), *[Div(Input(type='radio', name='answer', value=str(k), checked=k == right, aria_label=f'Option {k + 1} is right'),
                                             Input(type='text', name='options', value=o, maxlength='200', aria_label=f'Option {k + 1}'), cls='opt-row')
                                         for k, o in enumerate(opts)],
                    Small('For a choice, pick the right option. For an order, write the options in the right order. The room sees them mixed.', cls='mute help'),
                    cls='opts')

def act(post, name, **kw):
    "The htmx attributes of a button that makes the change `name` to its slide, and swaps the list."
    return dict(hx_post=post, hx_vals=json.dumps(dict(act=name, **kw)), hx_target='#deck', hx_swap='outerHTML', type='button')

def Ask(s, post):
    "The question for the room: its kind, the question, the options and the right one. The group saves as one, when one of its fields changes."
    sid, a = s['id'], s.get('ask') or {}
    kind = a.get('kind') or 'none'
    return Form(Span('Question for the room', cls='lbl'),
                Field('Kind', Select(*[Option(t, value=k, selected=k == kind) for k, t in KINDS.items()], name='kind')),
                Field('Question', Input(type='text', name='q', value=a.get('q') or '', maxlength='500')), Options(a), Right(sid, a),
                hx_post=post, hx_trigger='change, input delay:700ms', hx_swap='none', hx_vals=json.dumps(dict(act='edit')), cls='ask-fields')

def Passage(s, post, ps):
    "The passage of the slide with its source line, and the passages of its idea that can take its place, word for word."
    sh, k = s.get('show') or {}, -1
    have = (sh.get('passage') or '').strip()
    for n, p in enumerate(ps or ()):
        if p['text'].strip() == have: k = n
    pick = Field('Pick another passage', Select(Option('Pick a passage', value='', disabled=True, selected=k < 0),
                                                *[Option(short(p['text'], 90), value=str(n), selected=n == k) for n, p in enumerate(ps)],
                                                name='k', hx_post=post, hx_trigger='change', hx_vals=json.dumps(dict(act='passage')), hx_target='#deck', hx_swap='outerHTML')) if ps and (len(ps) > 1 or k < 0) else ''
    return Div(Span('Passage', cls='lbl'),
               *((Blockquote(Inline(have), cls='passage', data_pick='1'), SourceLine(slide_source(s))) if have else (P('This slide shows no passage.', cls='mute'),)),
               Div(pick, Quiet('Remove the passage', small=True, **act(post, 'passage', k='')) if have else '', cls='pick-row'), cls='passage-part')

def fig_url(tid, f): return f"{at(Routes.fig, tid)}?{urlencode(dict(f=f))}"

def Figure_(s, post, fs, tid):
    """The figure of the slide as a small picture with its caption, Remove the figure, and Pick another figure: the figures of the
    source of the slide, each as a small picture. `fs` is a list of dicts with `id` (an image id) and `caption`."""
    f, fs = (s.get('show') or {}).get('figure'), list(fs or ())
    if not f and not fs: return ''
    cap = next((x.get('caption') for x in fs if x['id'] == f), '') if f else ''
    others = [x for x in fs if x['id'] != f]
    pick = Details(Summary('Pick another figure', cls='quiet small'),
                   Div(*[Button(Img(src=fig_url(tid, x['id']), alt='', loading='lazy'), Span(x.get('caption') or f'Figure {n}', cls='cap'),
                                cls='fig-choice', **act(post, 'figure', asset=x['id'])) for n, x in enumerate(others, 1)], cls='fig-pick'),
                   cls='fig-more') if others else ''
    shown = (Figure(Img(src=fig_url(tid, f), alt=cap or 'The figure of the slide', loading='lazy'), Figcaption(cap) if cap else '', cls='thumb')
             if f else P('This slide shows no figure.', cls='mute'))
    return Div(Span('Figure', cls='lbl'), shown, Div(Quiet('Remove the figure', small=True, **act(post, 'figure', asset='')) if f else '', pick, cls='pick-row'),
               cls='figure-part')

BEAT_NAMES = dict(passage='Passage', body='Points', figure='Figure', demo='Demo', ask='Question')
BEAT_OF = dict(passage='passage', body='body', figure='figure', demo='demo')   # the part of `show` that each beat needs; `ask` needs a question

def beat_name(b):
    "A beat in plain words: Passage, Points, Figure, Demo, Question, or Light: and the words."
    if str(b).startswith('lit:'): return f"Light: part {b[5:]}" if b.startswith('lit:#') else f'Light: {b[4:]}'
    return BEAT_NAMES.get(b, b)

def beat_ids(s):
    "One id for each beat of slide `s`, from its words, so the focus follows a beat that moves."
    seen, out = {}, []
    for b in s.get('beats') or []:
        n = seen[b] = seen.get(b, 0) + 1
        out.append(f"{s['id']}:{b}" + (f':{n}' if n > 1 else ''))
    return out

def Beats(tid, s):
    """The beats of slide `s` as a list of small chips, in the order of the talk: each press of D in the talk shows the next one. A chip
    moves by the grip, by ⇧W ⇧S or by its arrows, and goes with ×  or X. The list is an editor list too (`edit.js`)."""
    sid, bs = s['id'], s.get('beats') or []
    post = lambda k: f"{at(Routes.beat, tid)}?{urlencode(dict(sid=sid, at=k))}"
    swap = dict(hx_target=f'#beats-{sid}', hx_swap='outerHTML', type='button')
    chips = [Li(Span(cls='grip', title='Drag to move', aria_hidden='true'), Span(beat_name(b), cls='chip-name'),
                Button('↑', data_move=str(k - 1), disabled=k == 0, aria_label='Move the beat up', type='button', cls='chip-btn'),
                Button('↓', data_move=str(k + 1), disabled=k == len(bs) - 1, aria_label='Move the beat down', type='button', cls='chip-btn'),
                Button('×', data_key='X', aria_label=f'Remove the beat {beat_name(b)}', hx_post=post(k), hx_vals=json.dumps(dict(act='drop')), cls='chip-btn', **swap),
                tabindex='0', data_id=i, data_post=post(k), cls='edit-row beat')
             for k, (b, i) in enumerate(zip(bs, beat_ids(s)))]
    return Ol(*chips, id=f'beats-{sid}', cls='beats', data_edit='1', aria_label='The beats, in order') if chips else Ol(
        Li('No beats: the slide shows its title only.', cls='mute none'), id=f'beats-{sid}', cls='beats', data_edit='1')

def AddBeat(tid, s, oob=False, open=False):
    "Add a beat: the parts that the slide has and does not show yet, and Light, which lights words of the passage that you select (or write)."
    sid, sh, bs = s['id'], s.get('show') or {}, s.get('beats') or []
    url = f"{at(Routes.beat, tid)}?{urlencode(dict(sid=sid))}"
    swap = dict(hx_post=url, hx_target=f'#beats-{sid}', hx_swap='outerHTML')
    can = [b for b in BEAT_NAMES if b not in bs and (s.get('ask') if b == 'ask' else sh.get(BEAT_OF[b]))]
    light = Form(Input(type='text', name='words', maxlength='200', placeholder='Select words in the passage, or write them', aria_label='Words to light', data_light='1'),
                 Quiet('Light these words', small=True), Input(type='hidden', name='act', value='add'), cls='light', **swap) if (sh.get('passage') or '').strip() else ''
    return Details(Summary('Add a beat', cls='quiet small'),
                   Div(*[Quiet(BEAT_NAMES[b], small=True, hx_vals=json.dumps(dict(act='add', kind=b)), type='button', **swap) for b in can], cls='beat-menu') if can else '',
                   light, id=f'addbeat-{sid}', cls='add-beat', open=open, **({'hx_swap_oob': 'true'} if oob else {}))

def BeatsPart(tid, s):
    return Div(Span('Beats', cls='lbl'), Beats(tid, s), AddBeat(tid, s),
               Small('In the talk, each press of D shows the next beat. With a beat in focus: W and S move the focus, ⇧W and ⇧S move the beat, X removes it.', cls='mute help'),
               cls='beats-part')

def Rewrite(post):
    "Rewrite this slide: a short instruction, or one of three chips. The tutor changes the points and the note, never the passage."
    go = dict(hx_post=post, hx_vals=json.dumps(dict(act='rewrite')), hx_target='#deck', hx_swap='outerHTML')
    return Form(Field('Rewrite this slide', Input(type='text', name='text', maxlength='300', placeholder='Tell the tutor what to change', aria_label='What to change'), REWRITE_HELP),
                Div(*[Quiet(c, small=True, type='submit', name='chip', value=c, data_wait='Rewriting…') for c in CHIPS],
                    Quiet('Rewrite', small=True, type='submit', data_wait='Rewriting…'), cls='chips'), cls='rewrite', **go)

def Body(tid, s, post, ch):
    "The fields of an open row: they save when you stop typing. Each change has an Undo."
    sh, k = s.get('show') or {}, s.get('kind')
    ideas = k in ('idea', 'primer')
    return [Field('Title', Live('title', Input(type='text', value=s.get('title') or '', maxlength='200'))),
            Field('Prompt', Live('prompt', Input(type='text', value=s.get('prompt') or '', maxlength='200'))) if k == 'pause' else '',
            Field('Points the room sees', Live('body', Textarea('\n'.join(sh.get('body') or []), rows='4')), 'One point on each line, at most 6.') if ideas else '',
            Field('Speaker note · only you see it', Live('notes', Textarea(s.get('notes') or '', rows='3'))),
            Passage(s, post, ch.get('passages')) if ideas else '',
            Figure_(s, post, ch.get('figures'), tid) if ideas else '',
            BeatsPart(tid, s) if ideas else '',
            Ask(s, post) if ideas else '',
            Rewrite(post) if ideas else '']

def row_line(s):
    "The short line of a slide row: what it shows, its minutes and its question."
    a = s.get('ask') or {}
    q = short(a.get('q'), 90) if a and a.get('kind') != 'none' else ''
    return (meta(shows(s), f"{s.get('mins') or 0} min"), *((' · asks: ', Inline(q)) if q else ()))

def Line(s, oob=False):
    "The short line of a slide row, out of band after a change in its open row (such as a beat)."
    return Span(*row_line(s), cls='line', **({'hx_swap_oob': f"outerHTML:#deck > li[data-id={s['id']}] > .head > .line"} if oob else {}))

def Row(t, i, s, ch, opened='', fresh=''):
    "Slide `s` as row `i` of the editor list: the small picture, the title, what shows and its minutes, then the fields of the open row."
    sid = s['id']; post = f"{at(Routes.slide, t['id'])}?{urlencode(dict(sid=sid))}"
    title = 'Pause: ' + (s.get('prompt') or 'talk to your neighbour') if s.get('kind') == 'pause' else s.get('title') or ''
    line = row_line(s)
    ideas = s.get('kind') in ('idea', 'primer')
    if parked(s):   # its idea left the walk: put it back, or remove it
        acts = [Quiet('Put back in the talk', small=True, **act(post, 'back')), Quiet('Remove', ' ', Kbd('X'), small=True, data_key='X', **act(post, 'drop'))]
        see = Span(Quiet('Put back in the talk', small=True, **act(post, 'back')), Quiet('Remove', small=True, **act(post, 'drop')), cls='parked-acts')   # on the row, not only in the open row
        return dict(id=sid, title=Inline(title), line=(*line, ' · not in the talk ', see), post=post, body=Body(t['id'], s, post, ch.get(sid) or {}), acts=acts,
                    open=sid == opened, fresh=sid == fresh, cls=f"{s.get('kind') or ''} parked", mini=Mini(s))
    acts = [Quiet('Duplicate', ' ', Kbd('D'), small=True, data_key='D', **act(post, 'dup')),
            Quiet('Remove', ' ', Kbd('X'), small=True, data_key='X', **act(post, 'drop')),
            Quiet('Rewrite', ' ', Kbd('R'), small=True, type='button', data_key='R', data_rewrite='1') if ideas else '']
    return dict(id=sid, title=Inline(title), line=line, post=post, body=Body(t['id'], s, post, ch.get(sid) or {}), acts=[x for x in acts if x],
                open=sid == opened, fresh=sid == fresh, cls=s.get('kind') or '', mini=Mini(s))

def Total(t, oob=False):
    "The minutes of the slides against the slot."
    total, slot = talk_minutes(t), t['minutes']
    return P(f'About {total} min of a {slot} min slot', id='total', cls='total' + (' over' if total > slot else ''), **({'hx_swap_oob': 'true'} if oob else {}))

def Deck(t, ch=None, opened='', fresh=''):
    "The slides as an editor list (`EditList`), with Add a slide and Add a pause under it. Each change swaps it whole."
    ch, ss = ch or {}, t['slides']
    rows = [Row(t, i, s, ch, opened, fresh) for i, s in enumerate(ss)]
    add = [Quiet('Add a slide', ' ', Kbd('A'), data_key='A', data_after='1', **act(at(Routes.slide, t['id']), 'add')),
           Quiet('Add a pause', ' ', Kbd('Q'), data_key='Q', data_after='1', **act(at(Routes.slide, t['id']), 'pause', prompt=PAUSE_SAY, secs=120))]
    out = EditList(rows, 'deck', add=add, id='deck', aria_label='The slides')
    kids, sec = [], None
    for li, r, s in zip(out.children, rows, ss):
        head = li.children[2]; head.children = (r['mini'], *head.children)   # the small picture goes before the title of each row
        if (x := s.get('section')) and x != sec:   # a quiet label where a section of the walk starts; it is not a row
            sec = x; kids.append(Li(Inline(x), cls='sec', role='presentation'))
        kids.append(li)
    out.children = (*kids, *out.children[len(rows):])
    return out

PAUSE_SAY = 'Talk to your neighbour.'

def Slot(t):
    "The slot and room phones: a change saves at once."
    post = dict(hx_post=at(Routes.slot, t['id']), hx_trigger='change', hx_target='#deck', hx_swap='outerHTML')
    return (Label('Slot', Input(type='number', name='minutes', value=str(t['minutes']), min='5', max='240', step='5', aria_label='The slot in minutes', **post),
                  Span('min', cls='mute'), cls='inline'),
            Label('Room phones', Select(Option('No phones', value='off', selected=not t.get('phones')),
                                        Option('Phones on this Wi-Fi', value='on', selected=bool(t.get('phones'))), name='phones', **post), cls='inline phones'))

def Fill(t):
    "Fill the slides: a quiet button for a talk made before the tutor wrote slide content. It shows only when a slide has no points or no speaker note."
    if not (n := sum(map(needs_fill, t['slides']))): return ''
    have = 'slide has' if n == 1 else 'slides have'
    return Form(Quiet('Fill the slides', small=True, data_wait='Filling the slides…'), Small(f' {n} {have} no points or no speaker note.', cls='mute'),
                hx_post=at(Routes.fill, t['id']), hx_target='this', hx_swap='outerHTML', cls='talk-new talk-fill')

def Editor(t, j, pj=None, changed=False, ch=None, bar=None, again=None):
    """The editor of talk `t` from walk `j` (made from path `pj`, if given, which `changed` after): what it is, Present, the slot, then the slides.
    `ch` has the passages and the figures that each slide can pick. A change saves at once, and the Undo bar at the foot can take it back.
    `bar` is the Undo bar to show when the page opens (after Fill the slides or Make it again), else the empty bar.
    `again` has what changed in walk `j` after the talk was made (`walk_changes`): the page then offers Make it again."""
    ins = [s for s in t['slides'] if s.get('kind') == 'idea' and s.get('section') != GONE]   # a slide whose idea left the walk is not counted
    ideas, secs = len(ins), len({s.get('section') for s in ins if s.get('section')})
    made = A('Made from your walk', href=f'/path/{pj.id}') if pj else A('Made from your walk', href=f'/w/{j.id}') if j else 'Made from a walk that is gone'
    cut = P('This talk has the first steps of the walk, up to the Ideas in a walk setting (12 by default). Skipped steps are left out.', cls='mute') if pj and (j.get('more') or any(s.get('status') == 'skip' for s in pj.steps)) else ''
    old = P('The walk changed after this talk was made. Make it again to update it.', cls='mute') if changed else ''
    return (H1(f"{t['title']}, as a talk"),
            P(made, ' · ' + meta(n_of(ideas, 'idea'), n_of(secs, 'section') if secs else ''), ' · ', A('Earlier versions', href=at(Routes.history, t['id'])), cls='mute'), cut, old, AgainLine(t, j.id, again) if j and again else '',
            P('Each idea of the walk is one slide. The passage or the points, and the figure, show to the room. The speaker note is for you only. '
              'A change saves at once, and Undo takes it back. A change here does not change the walk.', cls='lead'),
            Div(Form(Primary('Present', data_wait='Starting…'), action=at(Routes.start, t['id']), method='post', hx_boost='false'), *Slot(t), cls='row talk-top'),
            Part('The slides', Fill(t), Total(t), Deck(t, ch)),
            P('With the list in focus: ', Kbd('W'), ' ', Kbd('S'), ' move the focus · ', Kbd('⇧W'), ' ', Kbd('⇧S'), ' move the slide · ',
              Kbd('E'), ' edit · ', Kbd('A'), ' add a slide · ', Kbd('D'), ' duplicate · ', Kbd('X'), ' remove · ', Kbd('Q'), ' add a pause · ',
              Kbd('R'), ' rewrite · ', Kbd('⌘Z'), ' undo · ', Kbd('⌥S'), ' present', cls='mute keys-line'),
            bar or UndoBar(oob=False))

def History(t, rows):
    "The earlier versions of talk `t`: each change, newest first, with Restore this version."
    return (H1(f"Earlier versions of {t['title']}"),
            P('Each line is one change. Restore this version gives back the talk as it was before that change. You can undo a restore too.', cls='lead'),
            HistoryList(rows, at(Routes.restore, t['id'])),
            P(A('Back to the talk', href=at(Routes.one, t['id'])), cls='mute'))

# --- the stage: the slides of a run, in the presenter window and the audience window -----------------------------------

LETTERS = 'ABCDEF'
SAY = dict(questions='Ask your questions now.', recap='What the room answered.')

def part_at(beats, p):
    "The beat (from 1) that shows part `p`: 1 when the slide has no beats, None when no beat shows it."
    if not beats: return 1
    return beats.index(p) + 1 if p in beats else None

def lits(beats, passage):
    "Each `lit:` beat as [beat, text]: words of the passage, or `#id` for a part of the figure or the demo."
    return [[k + 1, b[4:]] for k, b in enumerate(beats) if b.startswith('lit:') and (b[4:].startswith('#') or b[4:] in passage)]

def Said(passage):
    "The paragraphs of a passage, each with its maths drawn, with the blank lines between them kept (the passage keeps its line breaks)."
    return [x for k, p in enumerate(re.split(r'\n\s*\n', passage.strip())) for x in (['\n\n'] if k else []) + [Inline(p)]]

def Slide(tid, s, ps, n, total, title, demo, at, presenter=False):
    """One slide as `section.stage`: the crumb, the title, then each part that a beat shows. `s` is the slide of the talk (for its
    beats), `ps` its public part (what the room sees), and `demo` the slug and the spec of its live demo, or None."""
    beats, kind, here = s.get('beats') or [], ps['kind'], ps['id'] == at['slide']
    hide = lambda k: here and k > at['beat']
    parts = []
    if kind in ('idea', 'primer'):
        if ps['passage'] and (k := part_at(beats, 'passage')): parts.append(Blockquote(*Said(ps['passage']), cls='passage', data_at=k, hidden=hide(k)))
        if ps['body'] and (k := part_at(beats, 'body')): parts.append(Ul(*[Li(Inline(b)) for b in ps['body']], cls='points', data_at=k, hidden=hide(k)))
        if ps['figure'] and (k := part_at(beats, 'figure')):
            parts.append(Figure(Img(src=at_img(tid, ps['figure']), alt=f"The figure of {ps['title']}"), cls='fig', data_at=k, hidden=hide(k)))
        if demo and (k := part_at(beats, 'demo')): parts.append(Div(Demo(demo[1], data_demo=demo[0]), cls='demo', data_at=k, hidden=hide(k)))
        crumb, head, say = ps['section'], ps['title'], ''
    elif kind == 'pause': crumb, head, say = f"Pause · {n_of(math.ceil((s.get('secs') or 120) / 60), 'min', 'min')}", s.get('prompt') or 'Talk to your neighbour.', ''
    elif kind in SAY: crumb, head, say = '', ps['title'], SAY[kind]
    else: crumb, head, say = '', ps['title'], 'This slide kind shows in a later version.'
    extra = dict(data_beats=json.dumps(beats), data_n=str(max(1, len(beats)))) if presenter else {}
    return Section(P(Inline(crumb), cls='crumb') if crumb else '', H1(Inline(head)), P(say, cls='say') if say else '',
                   Div(*parts, cls='body' + (' two' if len(parts) > 1 else '')) if parts else '',
                   Div(SourceLine(AttrDict(ps['src']), room=True) if ps.get('src') else '', Inline(title), Span(f'{n} of {total}'), cls='foot'),
                   cls='stage', data_sid=ps['id'], data_lits=json.dumps(lits(beats, ps['passage'])), hidden=not here, **extra)

def at_img(tid, h): return Routes.of(Routes.img, tid=tid, h=h)

def Stage(t, deck, run, demos, presenter=False, **kw):
    "Every slide of the public deck, with only the slide of the place shown; the blank screen and the room parts are drawn by talk.js."
    a, ss, n = run['at'], {s['id']: s for s in t['slides']}, len(deck.slides)
    return Div(Div(deck.title, cls='stage-blank'),
               *[Slide(t['id'], ss[ps['id']], ps, i, n, deck.title, demos.get(ps['id']), a, presenter) for i, ps in enumerate(deck.slides, 1)],
               Div(cls='stage-ask', hidden=True), Div(cls='stage-pair', hidden=True),
               id='stage', cls='stage' + (' blank' if a['blank'] else ''), data_slide=a['slide'], data_beat=str(a['beat']), data_title=deck.title, **kw)

def Audience(t, deck, run, demos, fade=1500):
    "The audience window: the slide only, full screen, with no top bar. F fills the screen."
    return (Stage(t, deck, run, demos, data_channel=f"{t['id']}:{run['key']}", data_fade=str(fade)),
            P('Keys work in the presenter window.', id='keys-note', role='status', hidden=True))

def AskBlock(s, n):
    "The question of slide `s` for the presenter: the question, each option with the right one marked, and the hands buttons."
    a, src = s['ask'], s['ask'].get('src') or {}
    opts, ans, kind = a.get('options') or [], a.get('answer'), a['kind']
    if kind == 'order' and isinstance(ans, list): right = Ol(*[Li(Inline(opts[i])) for i in ans if 0 <= i < len(opts)], cls='right-order')
    else: right = ''
    rows = [Li(Span(LETTERS[k] if kind != 'scale' else str(k + 1), cls='L'), Inline(o), cls='right' if kind == 'choice' and k == ans else None) for k, o in enumerate(opts)]
    hands = [Button(LETTERS[k] if kind != 'scale' else str(k + 1), Kbd(str(k + 1)), type='button', data_hand=str(k)) for k in range(len(opts))]
    return Div(Span('Ask the room' + (' · from the demo gate' if src.get('demo') else ''), cls='lbl'), P(Inline(a['q']), cls='q'),
               Ol(*rows, cls='opts') if rows else '',
               Div(Span('Right order', cls='lbl'), right, cls='right-box') if right else '',
               Div(*hands, cls='hands row') if hands else '',
               P(f"No phones in this room: the room puts hands up. Press 1 to {len(opts)} for the answer that most hands chose, so the recap has it."
                 if opts else 'No phones in this room: ask some people to say their answer.', cls='meta'),
               cls='ask-q', data_sid=s['id'], data_n=str(len(opts)), data_kind=kind, data_ask=json.dumps(dict(slide=s['id'], ask=public_ask(a))),
               hidden=True)

def AskCard(t, run):
    "The one raised card: the question of the slide now, and the main button that asks the room, shows the answer, then closes it."
    qs = [AskBlock(s, i) for i, s in enumerate(t['slides'], 1) if s.get('ask') and s['ask'].get('kind') != 'none']
    return Section(*qs, P('This slide has no question for the room.', cls='mute none'),
                   Div(Primary(Span('Ask the room', cls='act'), key='Q', type='button', id='ask-go'),
                       Quiet('Talk to your neighbour', type='button', id='pair-go', hidden=True), cls='row acts'),
                   id='ask-card', cls='check askcard')

def NextRow(s):
    "The next slide, small: its title and its minutes."
    title = 'Pause: ' + (s.get('prompt') or 'talk to your neighbour') if s.get('kind') == 'pause' else s.get('title') or ''
    return Div(Mini(s), Div(B(Inline(title)), Span(n_of(s.get('mins') or 0, 'min', 'min'), cls='mute')), cls='next-row')

def shaky_slides(t, run):
    "The slides whose answer was shown and where most hands chose a wrong option (the rail marks them)."
    shown = (run.get('stage') or {}).get('revealed') or []
    out = set()
    for s in t['slides']:
        a, m = s.get('ask') or {}, ((run.get('asks') or {}).get(s['id']) or {}).get('main')
        if s['id'] in shown and a.get('kind') == 'choice' and isinstance(m, int) and not isinstance(m, bool) and m != a.get('answer'): out.add(s['id'])
    return out

def Presenter(t, deck, run, demos):
    """The presenter window (shots/a2-presenter.png): the slide now with its beat, the rail, the notes, the next slide, the question
    card and the clock, with the keys at the foot. The audience window opens on the first key press or click."""
    tid, a, ss, log = t['id'], run['at'], t['slides'], run.get('stage') or {}
    shaky = shaky_slides(t, run)
    url = f"{Routes.of(Routes.audience, tid=tid)}?{urlencode(dict(k=run['key']))}"
    win = f'abhyasa-audience-{tid}'
    aud = Span(A('Open the audience window', href=url, target=win, id='aud-open', hx_boost='false'),
               Span(I(), 'Audience window open', cls='live', id='aud-live', hidden=True),
               Span('The audience window is closed. ', A('Open it again.', href=url, target=win, hx_boost='false'), cls='no', id='aud-gone', hidden=True),
               Span('Present in your browser: open ', Code('', id='app-url'), ' ', Quiet('Copy', small=True, type='button', id='app-copy'),
                    id='aud-app', hidden=True), cls='aud')
    keys = [('D', 'or space: next'), ('A', 'back'), ('Q', 'ask the room'), ('R', 'show the answer'), ('E', 'into the demo'), ('X', 'laser'),
            ('B', 'blank the room screen'), ('G', 'go to a slide'), ('⌥B', 'learn beside'), ('⌥Z', 'back to the slide'), ('esc', 'close')]
    end = Form(Quiet('End the talk', small=True, type='submit'), action=at(Routes.end, tid), method='post', hx_boost='false', id='end-form')
    return Div(Div(Inline(t['title'], cls='t'), aud, Span(cls='gap'), Span(id='left'),
                   Span('0:00', id='clock', data_started=str(run['started']), data_slot=str(t['minutes'])), Small(f"of {t['minutes']} min"), end, cls='pv-top'),
               Div(Div(Span(id='now'), Span(id='beats', cls='beats'), cls='mini-lbl'),
                   Stage(t, deck, run, demos, presenter=True),
                   Div(*[I(data_sid=s['id'], data_mins=str(s.get('mins') or 0), title=s.get('title') or '', cls='shaky' if s['id'] in shaky else None) for s in ss],
                       id='rail', cls='rail'),
                   P(id='say', cls='say', role='status'), cls='pv-main'),
               Div(Div(Span('Your note', cls='lbl'),
                       Div(*[Div(Md(s['notes']) if s.get('notes') else P('This slide has no note.', cls='mute'), Cites(s.get('cites')), data_sid=s['id'], hidden=s['id'] != a['slide'])
                             for s in ss], id='notes', cls='notes')),
                   Div(Span('Next', cls='lbl'),
                       Div(*[Div(NextRow(ss[i + 1]) if i + 1 < len(ss) else P('This is the last slide.', cls='mute'), data_sid=s['id'], hidden=s['id'] != a['slide'])
                             for i, s in enumerate(ss)], id='next')),
                   Div(id='beside-offer', aria_live='polite'), AskCard(t, run), cls='pv-side'),
               Div(*[Span(Kbd(k), w) for k, w in keys], cls='pv-foot'),
               id='talk', cls='pv', data_tid=tid, data_channel=f"{tid}:{run['key']}", data_audience=url, data_window=win,
               data_at=json.dumps(a), data_result=json.dumps(log.get('result')), data_pair=json.dumps(log.get('pair')), data_side=json.dumps(run.get('side')),
               data_revealed=json.dumps(log.get('revealed') or []))

# --- the side pane in a talk (spec 12): the offer in the presenter window --------------------------------------------------

WAYS = dict(primer=('A quick primer', 'The idea in short, beside the slide. About 2 minutes.'),
            walk=('A short side walk', 'The idea and the ideas under it, beside the slide, one at a time.'))

def BesideNone(c):
    "The offer when the idea of the slide needs no other idea on your shelf."
    said = f'{c.name} needs no other idea on your shelf.' if c else 'This slide has no idea that needs another idea.'
    return Div(Span('Learn beside', cls='lbl'), P(said), P('Press Esc to close this.', cls='meta'), cls='bs-offer none')

def BesideOffer(s, c, ns, n, pick):
    """The offer for the presenter only: the ideas that the idea of slide `s` needs, and two ways to open idea `n` beside the slide.
    1 is the primer and 2 the side walk; the tutor's pick (`pick_way_down`) is marked. Its own session never opens in a talk."""
    rows = [Li(B(x.name) if x.slug == n.slug else Button(x.name, type='button', cls='quiet small bs-need', data_need=x.slug),
               Span(' · learned' if x.ok else ' · not learned yet', cls='mute')) for x in ns]
    ways = [Button(Span(B(title), ' ', Kbd(str(k))), Span(body, cls='body'),
                   Span(f"The tutor's pick: {pick.why}.", cls='why') if pick.how == how else '',
                   type='button', cls='bs-way' + (' pick' if pick.how == how else ''), data_how=how, data_slug=n.slug)
            for k, (how, (title, body)) in enumerate(WAYS.items(), 1)]
    far = P(f"The tutor would open {n.name} as its own session: {pick.why}. In a talk, use the primer.", cls='meta') if pick.how == 'session' else ''
    return Div(Span(f"Learn beside · {s.get('title') or ''}", cls='lbl'), P(f'{c.name} needs:', cls='lead-in'), Ul(*rows, cls='plain bs-needs'),
               P(f'Open {n.name} beside the slide:', cls='lead-in'), Div(*ways, cls='bs-ways'), far,
               P('Press 1 or 2 to choose. Esc closes this. Only you see it.', cls='meta'), cls='bs-offer', data_slide=s['id'])

# --- after the talk (spec 13, shots/b5-recap.png) ---------------------------------------------------------------------------

def pct(x): return f'{round(100 * x)}%'

def mins(secs): return f'{max(1, round((secs or 0) / 60))} min'

def letter(a, i): return str(i + 1) if a.get('kind') == 'scale' else LETTERS[i] if isinstance(i, int) and 0 <= i < len(LETTERS) else '?'

def shares(a, log):
    "The share right of each round of question `a`."
    return [x for x in (share_right(a, rd) for rd in (log or {}).get('rounds') or []) if x is not None]

def Item(head, tail, *lines, act=''):
    "One row of a list on the page after the talk: a bold head, a short line at the right, the lines under it, and its button."
    return Li(Div(B(head), Span(tail, cls='share'), cls='h'), *[P(x) for x in lines if x], act, cls='after-item')

def asked(t, run, cnames):
    "Each question that the room answered, in slide order, as (key, title, question, answers): a slide's own, then each primer beside it."
    out = []
    for k, s in enumerate(t['slides'], 1):
        a, log = s.get('ask') or {}, (run.get('asks') or {}).get(s['id']) or {}
        if a and a.get('kind') != 'none' and (log.get('rounds') or log.get('main') is not None): out.append(((s['id'], None), s.get('title') or '', a, log))
        for b in run.get('beside') or []:
            if b.get('slide') == s['id'] and b.get('ask') and (b.get('rounds') or b.get('main') is not None):
                out.append(((s['id'], b['slug']), f"{cnames.get(b['slug'], b['slug'])} (beside idea {k})", b['ask'], b))
    return out

def Unsure(t, run, unsure, cnames):
    """Where the room was unsure: each question that the room answered, in slide order, with the questions on a primer beside a slide.
    A weak one has the share right in each round (or the hands line), the wrong answer that most people chose, and one plain line.
    The other ones say that the room was sure."""
    weak, out = {(w['slide'], w.get('beside')): w for w in unsure}, []
    for key, title, a, log in asked(t, run, cnames):
        sh, w = shares(a, log), weak.get(key)
        tail = ' → '.join(map(pct, sh)) + ' right' if sh else ''
        if w and w['share'] is None:
            out.append(Item(title, f"Most hands: {letter(a, w['main'])} (right: {letter(a, a.get('answer'))})",
                            f"Most hands chose “{w['top_wrong']}”. Go over this idea again." if w.get('top_wrong') else 'Most hands chose a wrong answer. Go over this idea again.'))
        elif w:
            moved = len(sh) > 1 and sh[-1] > sh[0]
            plain = ('After the talk with a neighbour, more people were right, but the idea is not solid yet.' if moved
                     else 'A second vote did not help. Go over this idea again.' if len(sh) > 1 else f"Fewer than {pct(val('talks.weak'))} of the room chose the right answer.")
            out.append(Item(title, tail, f"The wrong answer that most people chose: “{w['top_wrong']}”." if w.get('top_wrong') else '', plain))
        else: out.append(Item(title, tail or 'Most hands were right', 'Solid. No follow-up is needed.'))
    return Part('Where the room was unsure', Ul(*out, cls='plain after-list') if out else P('The room answered no question in this talk.', cls='mute'))

def RoomQuestions(qs):
    "The questions from the room, each with your note."
    if not qs: return ''
    return Part('Questions from the room', Ul(*[Item(q.get('text') or '', 'shown' if q.get('shown') else 'not shown',
                                                     f"Your note: “{q['note']}”" if q.get('note') else 'This question has no note.') for q in qs], cls='plain after-list'))

def ForRoom(tid, rid):
    "The recap file for the room: a download, and a look at it first."
    f = f"{Routes.of(Routes.recap, tid=tid)}?{urlencode(dict(run=rid))}"
    return Part('For the room', P("One file with the slides, the passages, each question with its right answer and the room's result, and the "
                                  'questions that you kept, with your notes. It has no speaker notes of yours and no names. Send it by mail or chat.', cls='lead'),
                Div(Primary('Save the recap as one file', href=f, download='', hx_boost='false'),
                    Quiet('Look at it first', href=f + '&look=1', target='_blank', hx_boost='false'), cls='row'))

def ForYou(t, run, follow, cnames):
    """A follow-up walk on the weak ideas, and "Next time: put the <name> primer before idea <n>" for each primer that was open
    beside a slide, with "Add it to the talk"."""
    tid, ss, out = t['id'], t['slides'], []
    if follow:
        out.append(Item(f"A follow-up walk on {', '.join(follow)}", n_of(len(follow), 'idea'),
                        'For the ideas where the room was unsure. Make it now. Present it next time, or send it with the recap.',
                        act=Form(Input(type='hidden', name='run', value=run['id']), Secondary('Make the walk', data_wait='Making the walk…'),
                                 action=at(Routes.follow, tid), method='post', hx_boost='false', cls='row')))
    seen = set()
    for b in run.get('beside') or []:
        k = next((i for i, s in enumerate(ss) if s['id'] == b.get('slide')), None)
        if k is None or (b.get('slug'), b.get('slide')) in seen: continue
        seen.add((b.get('slug'), b.get('slide')))
        name, minute = cnames.get(b.get('slug'), b.get('slug')), max(0, round(((b.get('at') or 0) - (run.get('started') or 0)) / 60))
        there = k > 0 and ss[k - 1].get('kind') == 'primer' and ss[k - 1].get('concept') == b.get('slug')
        add = (P('It is in the talk now.', cls='mute') if there else
               Form(Secondary('Add it to the talk'), hx_post=at(Routes.slide, tid), hx_vals=json.dumps(dict(sid=b['slide'], act='primer', slug=b['slug'], **{'from': 'after'})),
                    hx_target='this', hx_swap='outerHTML', cls='row'))
        out.append(Item(f"Next time: put the {name} primer before idea {k + 1}", '1 slide',
                        f"You opened it beside the slide in minute {minute}, for {mins(b.get('secs'))}. Keep it in the talk as its own slide.", act=add))
    return Part('For you', Ul(*out, cls='plain after-list') if out else P('Nothing to do now. The room was sure on each idea.', cls='mute'))

def Added(tid, title):
    "The line in place of Add it to the talk."
    return P(f'Added. The {title} primer is in the talk now. ', A('See the slides', href=at(Routes.one, tid)), cls='mute')

def SlideBySlide(t, run, rc, cnames):
    "The talk, slide by slide: each shown slide with its time and its shares, and each primer under the slide that it was open beside."
    pos, by = {s['id']: k for k, s in enumerate(t['slides'], 1)}, {s['id']: s for s in t['slides']}
    out = []
    for x in rc.slides:
        s = by[x['slide']]
        title = 'Pause: ' + (s.get('prompt') or 'talk to your neighbour') if s.get('kind') == 'pause' else x['title']
        sh = shares(s.get('ask') or {}, (run.get('asks') or {}).get(x['slide']))
        out.append(Li(f"{pos[x['slide']]} · {title}", Span(' · ' + meta(mins(x['secs']), ' → '.join(map(pct, sh))), cls='mute')))
        out += [Li(I(f"Beside: {cnames.get(b['slug'], b['slug'])}"), Span(f" · {mins(b.get('secs'))}", cls='mute'), cls='beside')
                for b in rc.beside if b.get('slide') == x['slide']]
    return Aside(Span('The talk, slide by slide', cls='lbl'), Ul(*out, cls='plain'),
                 P('The answers of the room do not change your own learning.', cls='mute small'),
                 P("The room's answers are counts only. They are not your attempts.", cls='mute small'), cls='sunken after-side')

def After(t, run, rc, names, cnames):
    "The page after the talk (spec 13): what the room was unsure about, the questions, the recap file, and what to do next."
    d = datetime.fromtimestamp(run.get('started') or 0)
    n = len(asked(t, run, cnames))
    line = meta(f"{d:%A} {d.day} {d:%b} at {d:%H:%M}", mins((run.get('ended') or run.get('started') or 0) - (run.get('started') or 0)),
                n_of(run['people'], 'person', 'people') if run.get('people') else '', f"{n_of(n, 'question')} to the room" if n else '',
                f"{n_of(len(rc.beside), 'primer')} beside the slides" if rc.beside else '')
    follow = list(dict.fromkeys(cnames.get(w['beside'], w['beside']) if w.get('beside') else names[w['slide']] for w in rc.unsure if w['slide'] in names))
    return (H1('After the talk'), P(line, cls='mute'),
            Div(Div(Unsure(t, run, rc.unsure, cnames), RoomQuestions(rc.questions), ForRoom(t['id'], run['id']), ForYou(t, run, follow, cnames)),
                SlideBySlide(t, run, rc, cnames), cls='after-cols'))
