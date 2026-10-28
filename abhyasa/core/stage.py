"""The stage bundle: the presenter window and the audience window of a talk, in step over a checked `BroadcastChannel`.

`stage.js` does the work in the browser: `abhyasaStage.valid` checks each message, `channel` sends and takes them, `audience`
draws the laser, the lit id, the blank screen and the side pane, and `presenter` binds the talk keys and sends the laser.
`stage.css` is the audience frame. This file has the version, the message types, the test cases that node runs through
`valid`, the rows of the talk keys, and the assets. A host (abhyasa, later Leela) draws its own slides with `draw`."""
from pathlib import Path
from abhyasa.core.ui import asset_css, asset_js

__all__ = ['STAGE_V', 'STAGE_TYPES', 'STAGE_CASES', 'PLAN_KEYS', 'TALK_KEYS', 'ROOM_KEYS', 'VOTE_KEYS', 'STAGE_KEYS', 'stage_assets']

_here = Path(__file__).parent
STAGE_V = 1
#: the message types of version 1, as in the table `TYPES` of `stage.js`; a later task adds a type to both, under `v: 1`
STAGE_TYPES = ('go', 'point', 'demo', 'ask', 'result', 'pair', 'pane', 'blank', 'end', 'hello', 'here', 'join', 'room', 'question')

OK = [dict(v=1, t='go', slide='s4', beat=2), dict(v=1, t='point', x=.31, y=.62), dict(v=1, t='point', id='scale'), dict(v=1, t='point', off=True),
      dict(v=1, t='demo', slug='softmax-temperature', state=dict(t=2), gates=dict(hot='done')),
      dict(v=1, t='ask', slide='s3', ask=dict(kind='choice', q='T goes from 1 to 2. What happens to the share of Paris?', options=['It rises', 'It falls', 'It stays the same'])),
      dict(v=1, t='ask', slide='s3', ask=None),
      dict(v=1, t='result', slide='s3', kind='choice', rounds=[dict(counts=[11, 10, 4], n=25)], right=1, main=None),
      dict(v=1, t='pair', on=True, prompt='Talk to your neighbour about your answer.'), dict(v=1, t='pane', url='/w/g-1a2b/0'), dict(v=1, t='pane', url=None),
      dict(v=1, t='blank', on=True), dict(v=1, t='end'), dict(v=1, t='hello'), dict(v=1, t='here'),
      dict(v=1, t='join', url='http://192.168.1.23:5180/j/K7PQ2M', code='K7PQ2M'), dict(v=1, t='join', url=None, code=None),
      dict(v=1, t='room', joined=34, answered=27), dict(v=1, t='question', text='Is √dk the best number?')]
BAD = [dict(v=2, t='go', slide='s4', beat=2), dict(v=1, t='eval', code='alert(1)'), dict(v=1, t='go', slide='s4', beat=-1), dict(v=1, t='go', slide='../x', beat=1),
       dict(v=1, t='go', slide='s4', beat=2, extra=1), dict(v=1, t='point', x=1.5, y=.2), dict(v=1, t='point', id='<b>'),
       dict(v=1, t='pane', url='https://evil.example/'), dict(v=1, t='pane', url='//evil.example'), dict(v=1, t='pane', url='/\\evil.example'),
       dict(v=1, t='pane', url='javascript:alert(1)'),
       dict(v=1, t='ask', slide='s3', ask=dict(kind='choice', q='Q?', options=['a', 'b'], answer=1)),
       dict(v=1, t='ask', slide='s3', ask=dict(kind='choice', q='Q?', options=list('abcdefg'))),
       dict(v=1, t='question', text='x' * 281), dict(v=1, t='join', url='http://evil.example/j/K7PQ2M', code='K7PQ2M'),
       dict(v=1, t='join', url='http://192.168.1.23:5180/j/K7PQ2O', code='K7PQ2O'), dict(v=1, t='blank', on='yes'),
       dict(v=1, t='room', joined=-1, answered=0), dict(v=1, t='demo', slug='x', state=dict(a='x' * 70000), gates={}), [1, 2]]
#: each (message, valid); `tests/test_stage.py` runs them through `abhyasaStage.valid` in node
STAGE_CASES = [(m, True) for m in OK] + [(m, False) for m in BAD]

#: the rows of the talk keys, as (group, keys, action); the task that binds a list adds it to `KEYS` in `keys.py`
PLAN_KEYS = [('Talk plan', 'W', 'Move the focus to the slide above'), ('Talk plan', 'S', 'Move the focus to the slide below'),
             ('Talk plan', '⇧W ⇧S', 'Move the slide up or down'), ('Talk plan', 'E', 'Change the slide'), ('Talk plan', 'X', 'Take out the slide'),
             ('Talk plan', 'Q', 'Add a pause after the slide'), ('Talk plan', '⌥S', 'Present the talk')]
TALK_KEYS = [('Talk', 'D', 'Next beat, then the next slide'), ('Talk', 'space', 'Next beat, then the next slide'), ('Talk', 'A', 'Back one beat'),
             ('Talk', 'Q', 'Ask the room, or close the question'), ('Talk', 'R', 'Show the result and the right answer'),
             ('Talk', '⌥S', 'The main button: start the talk, ask the room, vote again, end the talk'),
             ('Talk', 'E', 'Go into the demo. Esc comes out'), ('Talk', 'X', 'Laser on or off'), ('Talk', 'B', 'Blank the room screen, and back'),
             ('Talk', 'G', 'Go to a slide: G, then its number'), ('Talk', '1–6', 'With no phones: the option that most hands chose'),
             ('Talk', 'F', 'In the audience window: fill the screen'), ('Talk', '⌥B', 'Learn beside: open a missing idea next to the slide'),
             ('Talk', '⌥Z', 'Back to the slide: close the side pane'),
             ('Talk', 'esc', 'Close the open question, the demo focus or the side pane. It never ends the talk')]
ROOM_KEYS = [('Talk', 'C', 'Show the join code on the room screen, and back'), ('Talk', '⇧C', 'Make a new join code'),
             ('Talk', 'T', 'Lock the room, so no new phones join')]
VOTE_KEYS = [('Talk', 'V', 'Vote again on the closed question'), ('Talk', 'W', 'Show the next question from the room')]
STAGE_KEYS = PLAN_KEYS + TALK_KEYS + ROOM_KEYS + VOTE_KEYS

def stage_assets() -> tuple:
    "The style and the script of the stage, for the head of a talk page."
    return asset_css(_here/'stage.css'), asset_js(_here/'stage.js')
