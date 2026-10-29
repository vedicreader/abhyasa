"""The quiet feedback row under a demo or a lesson: "Too simple · Just right · Not clear". "Not clear" opens a short box that you
can speak into (a box with `data-mic` gets the mic of the voice block). One piece for every block, and one route that the app adds."""
import json, uuid
from fasthtml.common import *
from abhyasa.settings import val
from .ui import Quiet

__all__ = ['FEEDBACK_URL', 'PICKS', 'Feedback', 'FeedbackSaid', 'serve_feedback']

FEEDBACK_URL = '/feedback'
PICKS = dict(simple='Too simple', right='Just right', unclear='Not clear')   # the verdict -> its words on the row
THANKS = dict(simple='Thank you. The next one goes further.', right='Thank you.', unclear='Thank you. The tutor uses your note next time.')
NOTE_MAX = 500   # the same as `abhyasa.demo.NOTE_MAX`; this module does not load the demo engine to draw a page

def Feedback(kind, slug='', aid='', way='', simpler=None):
    """The row under a demo (`slug`) or a lesson (its attempt `aid`, taught in the way `way`). `simpler` holds the htmx attributes of a quiet
    "Show a simpler demo" that shows after "Not clear". Nothing when the setting `checks.feedback_row` is off."""
    if not val('checks.feedback_row') or not (slug or aid): return ''
    base = dict(on=kind, **{k: v for k, v in dict(slug=slug, aid=aid, way=way).items() if v})
    post = dict(hx_post=FEEDBACK_URL, hx_target='next .fb-said', hx_swap='innerHTML')
    pick = lambda v: Button(PICKS[v], type='button', cls='quiet small', data_verdict=v, hx_vals=json.dumps({**base, 'verdict': v}), **post)
    tid = f'fb-{uuid.uuid4().hex[:8]}'
    show = "const r = this.closest('.fb-row'), f = r.querySelector('.fb-note'); f.hidden = false; f.querySelector('textarea').focus();"
    note = Form(Label('What was unclear?', fr=tid),
                Textarea(name='note', id=tid, rows=2, maxlength=NOTE_MAX, data_mic='1', placeholder='Write or speak a few words.'),
                Div(Quiet('Send', small=True, type='submit'), cls='row'),
                cls='fb-note', hidden=True, data_verdict='unclear', hx_vals=json.dumps({**base, 'verdict': 'unclear'}), **post)
    return Div(Span(pick('simple'), Span(' · ', cls='sep'), pick('right'), Span(' · ', cls='sep'),
                    Button(PICKS['unclear'], type='button', cls='quiet small', onclick=show), cls='fb-picks'),
               note, Span(cls='fb-said', aria_live='polite'),
               Button('Show a simpler demo', type='button', cls='quiet small fb-more', **simpler) if simpler else '',
               cls='fb-row', data_kind=kind)

def FeedbackSaid(verdict): return THANKS[verdict]

def serve_feedback(app, learning):
    "Add the one route of the row: a POST (the app takes it only from itself, `LocalOnly`) with a known verdict and a short note."
    from abhyasa.demo import VERDICTS, FEEDBACK_ON, NOTE_MAX as most
    from abhyasa.method import METHODS
    def post(on:str='', verdict:str='', note:str='', slug:str='', aid:str='', way:str=''):
        if on not in FEEDBACK_ON or verdict not in VERDICTS or (way and way not in METHODS):
            return Response('Choose Too simple, Just right or Not clear.', status_code=400)
        if len(note) > most: return Response(f'Write at most {most} characters.', status_code=413)
        try: learning.give_feedback(on, verdict, note, slug=slug, aid=aid, way=way)
        except KeyError: return Response('This demo or lesson is not on the shelf.', status_code=404)
        except ValueError: return Response('Choose Too simple, Just right or Not clear.', status_code=400)
        return FeedbackSaid(verdict)
    app.post(FEEDBACK_URL)(post)
