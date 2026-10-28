"The levers beside the graph. `graph.js` reads and writes them by `name`; it does not make its own controls."
from fasthtml.common import *
from abhyasa.core import Empty
from abhyasa.model import DEPTHS

__all__ = ['Levers', 'Stage', 'Empty_']

MODES = (('force', 'Free', '1', 'The links pull and the nodes push apart'),
         ('path', 'Path', '2', 'Left to right: a concept comes after the concepts it needs'),
         ('rings', 'Rings', '3', 'One slice for each subject, one ring for each step of prereqs'),
         ('groups', 'Groups', '4', 'One group for each subject'))

def _sec(title, *c, keys=''): return Div(Span(title, Kbd(keys) if keys else '', cls='lbl'), *c, cls='sec')

def _pick(name, opts, val):
    return Select(*[Option(t, value=v, selected=v == val) for v, t in opts], name=name)

def _slide(name, title, lo=0, hi=100, val=50, step=1):
    return Label(Span(title), Input(type='range', name=name, min=lo, max=hi, value=val, step=step), cls='slide')

def _tick(name, title, on=False): return Label(Input(type='checkbox', name=name, checked=on), title, cls='tick')

def Levers(subjects):
    "The quiet panel. Find, the layout and the legend show; the other levers are under a closed `Adjust the view`."
    modes = Div(*[Label(Input(type='radio', name='mode', value=v, checked=v == 'force'), t, Kbd(k), title=why, cls='mode')
                  for v, t, k, why in MODES], cls='modes')
    floors = [(str(i), d) for i, d in enumerate(DEPTHS)]
    return Aside(
        _sec('Find', Input(type='search', name='q', placeholder='A concept', autocomplete='off'), keys='S'),
        _sec('Layout', modes, keys='1–4'),
        Div(Button('Freeze', Kbd('␣'), type='button', name='freeze'), Button('Fit', Kbd('F'), type='button', name='fit'),
            Button('Lay out again', Kbd('R'), type='button', name='reset'), cls='acts'),
        _sec('Colours', Div(cls='legend')),
        Details(Summary('Adjust the view'),
            _sec('Focus', P('Point at a concept and press E, or find a concept.', cls='hint', id='focus-name'),
                 _slide('steps', 'Steps out', 1, 4, 1), keys='E'),
            _sec('Space', _slide('spacing', 'Spacing'), _slide('link', 'Link length'), _slide('push', 'Push apart'),
                 _slide('size', 'Node size')),
            _sec('Look', Label(Span('Size by'), _pick('sizeBy', [('even', 'the same'), ('seen', 'times seen'), ('due', 'how due'), ('depth', 'prereq steps')], 'seen'), cls='pick'),
                 Label(Span('Colour by'), _pick('colorBy', [('floor', 'floor'), ('understanding', 'understanding'), ('subject', 'subject'), ('due', 'due')], 'floor'), cls='pick'),
                 Label(Span('Labels'), _pick('labels', [('all', 'all that fit'), ('learned', 'learned only'), ('hover', 'on hover')], 'all'), cls='pick'), keys='W'),
            _sec('Show', Div(*[_tick(f'sub:{s}', s, True) for s in subjects], cls='subs'),
                 Label(Span('Floor from'), _pick('floorLo', floors, '0'), cls='pick'),
                 Label(Span('Floor to'), _pick('floorHi', floors, '5'), cls='pick'),
                 _tick('dueOnly', 'Due only'), _tick('hideUnseen', 'Hide unseen'), _tick('related', 'Related links', True)),
            Div(Button('Reset all levers', type='button', name='levers'), cls='acts'),
            P('Click a concept to open it. Shift-click to pick it. Drag a concept to move it. It stays where you put it. '
              'D shows only what is due. ⎋ stops the find and the focus.', cls='hint'),
            cls='adjust'),
        id='levers')

def Empty_():
    "The graph with no concepts: one line in the middle, and a link to Add."
    return Empty('Each idea that you learn shows here. Start with a walk.', A('Add a source', href='/add'), cls='graph-empty')

def Stage(url, subjects, subject='', focus=''):
    "The canvas and its panel. The wrapper takes keyboard focus, so the keys work only here."
    return Div(Div(Canvas(), Div(cls='tip', hidden=True), P('Loading the graph…', cls='hint note'), cls='stage'), Levers(subjects),
               id='graph', tabindex='0', data_url=url, data_subject=subject, data_focus=focus)
