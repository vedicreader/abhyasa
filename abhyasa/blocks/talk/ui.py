"The talk on the page: the editor with one row for each slide, the form that changes a slide, and the parts on other pages."
import json
from pathlib import Path
from urllib.parse import urlencode
from fasthtml.common import *
from abhyasa.core import Primary, Secondary, Quiet, Part, meta, n_of, asset_css, asset_js
from abhyasa.talk import talk_minutes
from .cfg import Routes

_P = Path(__file__).parent
KINDS = dict(choice='Choice', order='Order', words='Short answer', scale='Scale', none='No question')
SHOWS = dict(passage='passage', figure='figure', demo='live demo')
ENDS = dict(questions='the questions from the room, or your notes', recap='made at the end from what the room answered')

def assets(): return asset_css(_P/'talk.css'), asset_js(_P/'talk.js')

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
            Div(Form(Primary('Present', data_wait='Starting…'), action=at(Routes.start, t['id']), method='post'), *Slot(t), cls='row talk-top'),
            Part('The slides', Deck(t)),
            P('With the list in focus: ', Kbd('W'), ' ', Kbd('S'), ' move the focus · ', Kbd('⇧W'), ' ', Kbd('⇧S'), ' move the slide · ',
              Kbd('E'), ' change the slide · ', Kbd('X'), ' take it out · ', Kbd('Q'), ' add a pause · ', Kbd('⌥S'), ' present', cls='mute keys-line'))
