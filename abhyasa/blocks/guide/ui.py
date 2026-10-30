"The parts of the guide on each page: the Explain button, the one-line box, and the strip under the board."
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import asset_js, asset_css
from .cfg import Routes

_P = Path(__file__).parent
KEY = '⌃⌥⇧⌘E'
ASK = 'What do you not understand?'

def Go():
    "The Explain button, for a learner with no Hyper key. Hyper+E does the same."
    return Button('Explain', type='button', id='guide-go', cls='guide-go', aria_keyshortcuts='Control+Alt+Shift+Meta+E',
                  title=f'Ask the tutor to explain a part of this page. {KEY} (Caps+E): hold to talk, tap to type.')

def Box():
    "The one-line box. A tap of Hyper+E opens it; held, the key fills it with what you say."
    return Form(Input(type='text', name='said', id='guide-box', aria_label=ASK, placeholder="I don't get …", autocomplete='off', maxlength='300'),
                Button('Explain', type='submit', cls='small'), Span(cls='guide-heard mute', aria_live='polite'),
                id='guide-form', cls='guide-form', hidden=True, hx_boost='false')

def Strip():
    "The strip under the board: the tier, the step and its line, the sources, and the keys. board.js fills it, with text only."
    return Div(id='guide-strip', cls='guide-strip', hidden=True, aria_live='polite', role='status')

def Parts():
    return (Box(), Strip(), asset_css(_P/'guide.css'),
            asset_js(_P/'guide.js', data_ask=Routes.ask, data_figure=Routes.figure))

# --- the explainer video of a concept --------------------------------------------------------------------------------
EMBED = 'https://www.youtube-nocookie.com/embed/{}?enablejsapi=1&rel=0'

def mmss(t) -> str: return f'{int(t) // 60}:{int(t) % 60:02d}'

def Transcript(v):
    "The transcript, closed until you open it. Each time seeks the video (guide.js); with no script it opens YouTube at that time."
    if not v.get('cues'): return ''
    return Details(Summary('Transcript', cls='mute'),
                   Div(*[P(A(mmss(t), href=f"{v['url']}&t={int(t)}s", data_t=str(t), target='_blank', rel='noopener noreferrer', cls='mute'), ' ', x)
                         for t, x in v['cues']], cls='guide-transcript'), cls='guide-quiet')

def Video(v, slug:str='', tools=False):
    "The explainer video: a youtube-nocookie embed with no autoplay, its source line, and its transcript. `#guide-video` is what the guide reads and seeks."
    name = ' · '.join(x for x in (v.get('channel'), v.get('title')) if x) or 'The explainer video'
    return Section(Iframe(src=EMBED.format(v['id']), title=f"Video: {v.get('title') or 'the explainer'}", loading='lazy', allowfullscreen=True,
                          allow='encrypted-media; picture-in-picture; fullscreen', referrerpolicy='strict-origin-when-cross-origin', cls='guide-embed'),
                   P(Span('video', cls='pill'), ' ', A(name, href=v['url'], target='_blank', rel='noopener noreferrer', cls='src'), cls='src-line mute'),
                   Transcript(v), VideoTools(slug, True) if tools else '',
                   id='guide-video', cls='guide-video', data_vid=v['id'], data_title=v.get('title') or '', data_concept=slug or None)

def VideoTools(slug:str, has=False, msg:str=''):
    "Find a video for the concept, paste a link, or take the video away."
    from .cfg import Routes
    u = Routes.of(Routes.video, slug=slug)
    tgt = dict(hx_target='#guide-video-slot', hx_swap='outerHTML')
    return Div(P(msg, cls='mute', role='status') if msg else '',
               Form(Input(type='url', name='url', placeholder='Paste a YouTube link', aria_label='A YouTube link for this idea', required=True, maxlength='300'),
                    Button('Use this video', type='submit', cls='small quiet'), hx_post=u, **tgt, cls='row guide-paste'),
               Div(Button('Find a video', type='button', cls='small quiet', hx_post=Routes.of(Routes.find, slug=slug), **tgt, hx_disabled_elt='this'),
                   Button('Remove the video', type='button', cls='small quiet', hx_post=Routes.of(Routes.drop, slug=slug), **tgt) if has else '',
                   Span('The tutor looks on YouTube …', cls='htmx-indicator mute'), cls='row'),
               cls='guide-video-tools')

def VideoSlot(v, slug:str, msg:str=''):
    "The concept page part: the video with its tools, or only the tools."
    return Div(H2('Explainer video'), Video(v, slug, tools=True) if v else VideoTools(slug, msg=msg),
               P(msg, cls='mute', role='status') if v and msg else '', id='guide-video-slot')
