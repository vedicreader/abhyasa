"The talk on the page: the editor with one row for each slide, the form that changes a slide, and the parts on other pages."
import json, math
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from fasthtml.common import *
from rupaka.render import Demo, version
from abhyasa.core import Primary, Secondary, Quiet, Part, Md, meta, n_of, asset_css, asset_js, stage_assets
from abhyasa.talk import talk_minutes, public_ask, share_right
from abhyasa.settings import val
from .cfg import Routes

_P = Path(__file__).parent
KINDS = dict(choice='Choice', order='Order', words='Short answer', scale='Scale', none='No question')
SHOWS = dict(passage='passage', figure='figure', demo='live demo')
ENDS = dict(questions='the questions from the room, or your notes', recap='made at the end from what the room answered')

def assets(): return asset_css(_P/'talk.css'), asset_js(_P/'talk.js')

def rupaka_assets():
    "The rupaka runtime that the demo block serves, for the live demo of a slide."
    v = version()
    return Link(rel='stylesheet', href=f'/rupaka/rupaka.css?v={v}'), Script(src=f'/rupaka/rupaka.js?v={v}')

def at(r, tid): return Routes.of(r, tid=tid)

def short(s, n=140):
    s = ' '.join(str(s or '').split())
    return s if len(s) <= n else s[:n].rsplit(' ', 1)[0] + '…'

# --- on other pages --------------------------------------------------------------------------------------------------

def PresentWalk(jid):
    "Make a talk from walk `jid`: the button gives way to the pending card."
    return Form(Input(type='hidden', name='jid', value=jid), Secondary('Present this walk', data_wait='Making the talk…'),
                hx_post=Routes.new, hx_target='this', hx_swap='outerHTML', cls='talk-new')

def Pending(jid):
    "A talk that is still being made: the card asks the server again in 2 seconds."
    return Div(P('Making the talk…'), P('The tutor writes a question for the room from each check. This can take a minute.', cls='mute'),
               cls='talk-new pending', hx_get=f"{Routes.job}?{urlencode(dict(jid=jid))}", hx_trigger='load delay:2s', hx_swap='outerHTML')

def YourTalks(ts):
    "Each talk as a link to its editor, with its slide count and its slot."
    return Part('Your talks', Ul(*[Li(A(t.title, href=at(Routes.one, t.id)), Span('  ' + meta(n_of(len(t.slides), 'slide'), f"a {t.minutes} min slot"), cls='mute'))
                                   for t in ts], cls='plain'))

# --- the editor ------------------------------------------------------------------------------------------------------

def shows(s):
    "What slide `s` shows, as one short line."
    k, beats = s.get('kind'), s.get('beats') or []
    if k == 'pause': return meta(f"{s.get('secs', 120)} s", 'you added it')
    if k in ENDS: return ENDS[k]
    if k not in ('idea', 'primer'): return 'This slide kind shows in a later version.'
    parts = [SHOWS[b] for b in SHOWS if b in beats]
    lit = sum(str(b).startswith('lit:') for b in beats)
    return meta(*parts, n_of(lit, 'lit line') if lit else '', n_of(len(beats), 'beat') if len(beats) > 1 else '') or 'the title only'

def AskCell(s):
    "The question of slide `s` for the room, or the prompt of a pause."
    if s.get('kind') == 'pause': return Div(Span('Prompt', cls='lbl'), f"“{s.get('prompt') or ''}”", cls='ask')
    a = s.get('ask')
    if not a or a.get('kind') == 'none': return Div(Span('Ask the room', cls='lbl'), Span('none', cls='mute'), cls='ask')
    src = a.get('src') or {}
    how = meta(KINDS.get(a['kind'], a['kind']).lower(), n_of(len(a.get('options') or ()), 'option') if a.get('options') else '',
               'from the demo gate' if src.get('demo') else '')
    return Div(Span('Ask the room', cls='lbl'), Span(a.get('q') or ''), Small(how, cls='mute'), cls='ask')

def Mini(s):
    "A small picture of the slide: its section, its title and the start of its passage."
    sh = s.get('show') or {}
    return Div(Small(s.get('section') or ''), B(s.get('title') or ''), P(short(sh.get('passage') or s.get('prompt') or '', 120)),
               I(cls='fig') if sh.get('figure') else '', cls='mini', aria_hidden='true')

def Field(label, el, help=''):
    return Label(label, el, Small(help, cls='mute help') if help else '')

def Options(a, most=6):
    """One box for each option, with a radio button on the right one for a choice. An order shows its options in the right order;
    the talk mixes them for the room when you save."""
    opts, ans = list(a.get('options') or []), a.get('answer')
    if a.get('kind') == 'order' and isinstance(ans, list) and sorted(ans) == list(range(len(opts))): opts = [opts[i] for i in ans]
    opts += [''] * (most - len(opts))
    right = ans if a.get('kind') == 'choice' else None
    return Fieldset(Legend('Options'), *[Div(Input(type='radio', name='answer', value=str(k), checked=k == right, aria_label=f'Option {k + 1} is right'),
                                             Input(type='text', name='options', value=o, maxlength='200', aria_label=f'Option {k + 1}'), cls='opt-row')
                                         for k, o in enumerate(opts)],
                    Small('For a choice, pick the right option. For an order, write the options in the right order. The room sees them mixed.', cls='mute help'),
                    cls='opts')

def EditForm(tid, s):
    "The form that changes slide `s`: the note, what shows, the beats and the question. It sends only what it shows."
    sid, sh, a = s['id'], s.get('show') or {}, s.get('ask') or {}
    beats, kind = s.get('beats') or [], (s.get('ask') or {}).get('kind') or 'none'
    boxes = [Label(Input(type='checkbox', name=f'show_{p}', checked=p in beats), SHOWS[p], cls='box') for p in SHOWS if sh.get(p)]
    q = Div(Field('Ask the room', Select(*[Option(t, value=k, selected=k == kind) for k, t in KINDS.items()], name='kind')),
            Field('Question', Input(type='text', name='q', value=a.get('q') or '', maxlength='500')), Options(a), cls='ask-fields')
    return Form(Input(type='hidden', name='sid', value=sid), Input(type='hidden', name='act', value='edit'),
                Field('Speaker note', Textarea(s.get('notes') or '', name='notes', rows='3'), 'Only you see it.'),
                Div(Span('What shows', cls='lbl'), *boxes, cls='boxes') if boxes else '',
                Field('Beats', Textarea('\n'.join(beats), name='beats', rows='3'),
                      'Each press of D shows one more. Use passage, figure, demo or ask, or lit: and words from the passage to light them.'),
                q if s.get('kind') in ('idea', 'primer') else '',
                Div(Secondary('Save the slide'), cls='row'),
                hx_post=at(Routes.slide, tid), hx_target='#deck', hx_swap='outerHTML', cls='slide-edit')

def Acts(tid, sid):
    "The changes that need no form: move, add a pause, take out."
    post = lambda act, **kw: dict(hx_post=at(Routes.slide, tid), hx_vals=json.dumps(dict(sid=sid, act=act, **kw)), hx_target='#deck', hx_swap='outerHTML', type='button')
    return Div(Quiet('Move up', small=True, **post('up')), Quiet('Move down', small=True, **post('down')),
               Quiet('Add a pause after it', small=True, **post('pause')),
               Danger(Quiet('Take it out', small=True, hx_confirm='Take out this slide? The walk does not change.', **post('drop'))), cls='acts')

def Danger(b):
    "A quiet button that takes something out: the --no colour (talk.css)."
    b.attrs['class'] = f"{b.attrs.get('class', '')} danger".strip()
    return b

def Row(tid, n, s):
    "One slide: its number, a small picture, the title and what shows, the question, the minutes, and the closed form that changes it."
    added = s.get('kind') in ('pause', 'questions', 'recap', 'primer')
    title = 'Pause: ' + (s.get('prompt') or 'talk to your neighbour') if s.get('kind') == 'pause' else s.get('title') or ''
    return Li(Span(str(n), cls='no'), Mini(s), Div(B(title, cls='added' if added else None), Span(shows(s)), cls='ttl'), AskCell(s),
              Span(f"{s.get('mins') or 0} min", cls='min'),
              Details(Summary('Change', title='E'), Acts(tid, s['id']), EditForm(tid, s), cls='edit'),
              cls='slide', data_sid=s['id'], tabindex='0')

def Rows(t):
    "The slides in order, under the section of the walk that they come from. A slide with no section stays in the section before it."
    out, sec = [], None
    groups = []
    for n, s in enumerate(t['slides'], 1):
        if (x := s.get('section')) and x != sec: sec = x; groups.append((x, []))
        elif not groups: groups.append(('', []))
        groups[-1][1].append((n, s))
    for name, rows in groups:
        if name: out.append(Li(B(name), Small(' · ' + meta(n_of(sum(s.get('kind') == 'idea' for _, s in rows), 'idea'), f"{sum(s.get('mins') or 0 for _, s in rows)} min")), cls='sec'))
        out += [Row(t['id'], n, s) for n, s in rows]
    return out

def Deck(t):
    "The slides part: the total against the slot, then one row for each slide. Each change swaps it whole."
    total, slot = talk_minutes(t), t['minutes']
    return Div(P(f'About {total} min of a {slot} min slot', cls='total' + (' over' if total > slot else '')),
               Ol(*Rows(t), cls='deck') if t['slides'] else P('The talk has no slides.', cls='mute empty'), id='deck')

def Slot(t):
    "The slot and room phones: a change saves at once."
    post = dict(hx_post=at(Routes.slot, t['id']), hx_trigger='change', hx_target='#deck', hx_swap='outerHTML')
    return (Label('Slot', Input(type='number', name='minutes', value=str(t['minutes']), min='5', max='240', step='5', aria_label='The slot in minutes', **post),
                  Span('min', cls='mute'), cls='inline'),
            Label('Room phones', Select(Option('No phones', value='off', selected=not t.get('phones')),
                                        Option('Phones on this Wi-Fi', value='on', selected=bool(t.get('phones'))), name='phones', **post), cls='inline phones'))

def Editor(t, j):
    "The editor of talk `t` from walk `j`: what it is, Present, the slot, then the slides (as `shots/a1-deck.png`)."
    ideas = sum(s.get('kind') == 'idea' for s in t['slides'])
    secs = len({s.get('section') for s in t['slides'] if s.get('kind') == 'idea' and s.get('section')})
    made = A('Made from your walk', href=f'/w/{j.id}') if j else 'Made from a walk that is gone'
    return (H1(f"{t['title']}, as a talk"),
            P(made, ' · ' + meta(n_of(ideas, 'idea'), n_of(secs, 'section') if secs else ''), cls='mute'),
            P('Each idea of the walk is one slide. The passage and the figure show to the room. The tutor note is your speaker note. '
              'The check of the idea becomes a question for the room. A change here does not change the walk.', cls='lead'),
            Div(Form(Primary('Present', data_wait='Starting…'), action=at(Routes.start, t['id']), method='post', hx_boost='false'), *Slot(t), cls='row talk-top'),
            Part('The slides', Deck(t)),
            P('With the list in focus: ', Kbd('W'), ' ', Kbd('S'), ' move the focus · ', Kbd('⇧W'), ' ', Kbd('⇧S'), ' move the slide · ',
              Kbd('E'), ' change the slide · ', Kbd('X'), ' take it out · ', Kbd('Q'), ' add a pause · ', Kbd('⌥S'), ' present', cls='mute keys-line'))

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

def Slide(tid, s, ps, n, total, title, demo, at, presenter=False):
    """One slide as `section.stage`: the crumb, the title, then each part that a beat shows. `s` is the slide of the talk (for its
    beats), `ps` its public part (what the room sees), and `demo` the slug and the spec of its live demo, or None."""
    beats, kind, here = s.get('beats') or [], ps['kind'], ps['id'] == at['slide']
    hide = lambda k: here and k > at['beat']
    parts = []
    if kind in ('idea', 'primer'):
        if ps['passage'] and (k := part_at(beats, 'passage')): parts.append(Blockquote(ps['passage'], cls='passage', data_at=k, hidden=hide(k)))
        if ps['figure'] and (k := part_at(beats, 'figure')):
            parts.append(Figure(Img(src=at_img(tid, ps['figure']), alt=f"The figure of {ps['title']}"), cls='fig', data_at=k, hidden=hide(k)))
        if demo and (k := part_at(beats, 'demo')): parts.append(Div(Demo(demo[1], data_demo=demo[0]), cls='demo', data_at=k, hidden=hide(k)))
        crumb, head, say = ps['section'], ps['title'], ''
    elif kind == 'pause': crumb, head, say = f"Pause · {n_of(math.ceil((s.get('secs') or 120) / 60), 'min', 'min')}", s.get('prompt') or 'Talk to your neighbour.', ''
    elif kind in SAY: crumb, head, say = '', ps['title'], SAY[kind]
    else: crumb, head, say = '', ps['title'], 'This slide kind shows in a later version.'
    extra = dict(data_beats=json.dumps(beats), data_n=str(max(1, len(beats)))) if presenter else {}
    return Section(P(crumb, cls='crumb') if crumb else '', H1(head), P(say, cls='say') if say else '',
                   Div(*parts, cls='body' + (' two' if len(parts) > 1 else '')) if parts else '',
                   Div(Span(title), Span(f'{n} of {total}'), cls='foot'),
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
    if kind == 'order' and isinstance(ans, list): right = Ol(*[Li(opts[i]) for i in ans if 0 <= i < len(opts)], cls='right-order')
    else: right = ''
    rows = [Li(Span(LETTERS[k] if kind != 'scale' else str(k + 1), cls='L'), o, cls='right' if kind == 'choice' and k == ans else None) for k, o in enumerate(opts)]
    hands = [Button(LETTERS[k] if kind != 'scale' else str(k + 1), Kbd(str(k + 1)), type='button', data_hand=str(k)) for k in range(len(opts))]
    return Div(Span('Ask the room' + (' · from the demo gate' if src.get('demo') else ''), cls='lbl'), P(a['q'], cls='q'),
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
    return Div(Mini(s), Div(B(title), Span(n_of(s.get('mins') or 0, 'min', 'min'), cls='mute')), cls='next-row')

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
    return Div(Div(Span(t['title'], cls='t'), aud, Span(cls='gap'), Span(id='left'),
                   Span('0:00', id='clock', data_started=str(run['started']), data_slot=str(t['minutes'])), Small(f"of {t['minutes']} min"), end, cls='pv-top'),
               Div(Div(Span(id='now'), Span(id='beats', cls='beats'), cls='mini-lbl'),
                   Stage(t, deck, run, demos, presenter=True),
                   Div(*[I(data_sid=s['id'], data_mins=str(s.get('mins') or 0), title=s.get('title') or '', cls='shaky' if s['id'] in shaky else None) for s in ss],
                       id='rail', cls='rail'),
                   P(id='say', cls='say', role='status'), cls='pv-main'),
               Div(Div(Span('Your notes', cls='lbl'),
                       Div(*[Div(Md(s['notes']) if s.get('notes') else P('This slide has no note.', cls='mute'), data_sid=s['id'], hidden=s['id'] != a['slide']) for s in ss], id='notes', cls='notes')),
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
