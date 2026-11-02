"""The side pane: a page of this app beside the page, after vedicreader's `vr/core/pane.py`.

The pane shows a local page in an `iframe`, at its URL with `pane=1`. Its place is in the URL of the page (`?rh=<local path>`),
so a reload keeps it and browser Back closes it. `pane.js` does the opening, the grip, the keys and the messages.

The contract for a host (abhyasa here, Leela too):

- `open(url, title)` shows the local page `url`, with `pane=1`, beside the page. `close()` closes it. The state is one local URL
  in the query of the page: `rh`.
- The host takes a message only when its origin is the host's own origin and its source is the pane's own frame. It ignores
  all other messages. A URL in a message must pass `is_local`.
- `rh:at {url, title, trail}`: the pane is now at `url`. The host updates `rh` with `replaceState`. `trail` is a list of
  `[title, url]` from the main page to the parent of `url`.
- In a talk, the pane URL also has `talk=1` (`pane_url(url, talk=True)`): the page draws in the talk type, in big text and with no check.
- `rh:open {url}`: open `url` in the same pane (a nested side page).
- `rh:close`: close the pane. `rh:close {level: 1}` goes back one level only: to the last part of the trail, or, when there is
  no part in the pane, the pane closes (⌥Z).
- `rh:done {slug, outcome}`: the side walk ended. The host sends it again as the DOM event `abhyasa:rh-done` on `document`, with
  `detail = {slug, outcome}`. The detail comes from the page in the pane: the host must treat it as input that it cannot trust.
- `rh:link {url}`: open `url` outside the pane, in a new tab with `noopener` (Leela sends it). The URL must pass `is_web`: http
  or https only. The host refuses all other schemes, such as `javascript:`, `data:` and `file:`.

An outside link on a learning page goes through `side_link`. A YouTube video or playlist opens embedded in the pane, on the local
page `/watch?u=<link>` (`yt_embed`); on a narrow screen it opens in a new tab. Any other web link opens in a new tab, with `noopener`."""
import re
from urllib.parse import urlsplit, urlunsplit, parse_qs, quote
from fasthtml.common import A, Aside, B, Button, Div, Header, Iframe, Span
from abhyasa.stagekit import is_local, _BAD

__all__ = ['is_local', 'is_web', 'pane_url', 'pane_link', 'side_link', 'PaneHost', 'yt_embed', 'watch_url', 'YT_EMBED', 'WATCH']

_WEB = re.compile(r'https?://[^\s/?#\\]+[^\s\\]*\Z', re.I)   # http or https, a host, and no space

def is_web(url) -> bool:
    "Whether `url` is an http or https URL with a host, and no space, backslash or control character: a link that `rh:link` can open."
    return isinstance(url, str) and bool(_WEB.match(url)) and not _BAD.search(url)

def pane_url(url, talk:bool=False) -> str|None:
    "`url` with `pane=1` in its query (and `talk=1` with `talk`, for the talk type), when it is a local path; else None."
    if not is_local(url): return None
    p = urlsplit(url)
    drop = ('pane=', 'talk=') if talk else ('pane=',)
    q = [x for x in p.query.split('&') if x and not x.startswith(drop)] + ['pane=1'] + (['talk=1'] if talk else [])
    return urlunsplit(('', '', p.path, '&'.join(q), p.fragment))

def pane_link(label, href:str, title:str='', cls:str='pane-link', **kw):
    "A real link to `href` in a new tab; `pane.js` opens it in the side pane on a wide screen, or in the same tab on a narrow one."
    return A(label, href=href, target='_blank', data_pane=pane_url(href), data_title=title or None, cls=cls, **kw)

YT_EMBED, WATCH = 'https://www.youtube-nocookie.com', '/watch'   # the one host that the pane embeds, and the local page that embeds it
_YT_HOSTS = ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be', 'www.youtube-nocookie.com', 'youtube-nocookie.com')
_YT_ID, _YT_LIST = re.compile(r'[\w-]{11}'), re.compile(r'[\w-]{10,64}')

def _secs(t:str) -> int:
    "The seconds of a YouTube time: `65`, `65s`, `1m5s` or `1h2m3s`; 0 when it is not one."
    if (t := str(t or '').strip()).isdigit(): return int(t)
    m = re.fullmatch(r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?', t)
    return int(m[1] or 0) * 3600 + int(m[2] or 0) * 60 + int(m[3] or 0) if m and t else 0

def yt_embed(url) -> str|None:
    """The embed URL on `YT_EMBED` for the YouTube link `url`: a video (`watch?v=`, `youtu.be/`, `shorts/`, `embed/`) at its start time
    (`t=` or `start=`), or a playlist (`videoseries?list=`). None for any other link, such as a YouTube search, which cannot be embedded.
    kosha shows no helper for this: fossick makes watch links but does not read them."""
    if not is_web(url): return None
    p = urlsplit(url)
    if (p.hostname or '').lower() not in _YT_HOSTS: return None
    q = {k: v[0] for k, v in parse_qs(p.query).items()}
    parts = [x for x in p.path.split('/') if x]
    vid = parts[0] if p.hostname.lower() == 'youtu.be' and parts else q.get('v') if parts == ['watch'] else parts[1] if len(parts) == 2 and parts[0] in ('shorts', 'embed', 'live') else None
    start = _secs(q.get('t') or q.get('start'))
    if vid and _YT_ID.fullmatch(vid) and vid != 'videoseries': return f'{YT_EMBED}/embed/{vid}' + (f'?start={start}' if start else '')
    if (lst := q.get('list')) and _YT_LIST.fullmatch(lst) and parts in (['playlist'], ['watch'], ['embed', 'videoseries']): return f'{YT_EMBED}/embed/videoseries?list={lst}'
    return None

def watch_url(url) -> str|None:
    "The local page that embeds the YouTube link `url` in the pane (`/watch?u=<link>`), or None when `yt_embed` cannot embed it."
    return f"{WATCH}?u={quote(url, safe='')}" if yt_embed(url) else None

def side_link(label, href:str, title:str='', **kw):
    """The one rule for a link on a learning page to a page that supports the exercise: a local page opens in the side pane
    (`pane_link`), so the page keeps its scroll, its draft and its open check. A YouTube video or playlist opens embedded in the pane
    (`watch_url`): the link is the YouTube link, so a narrow screen or a modifier key opens it in a new tab. Any other web page opens in a
    new tab with `noopener`, marked ↗ (`out-link`); it never takes the place of the learning page. Any other link is text."""
    if is_local(href): return pane_link(label, href, title, **{'cls': 'pane-link', **kw})
    if w := watch_url(href):
        return A(label, href=href, target='_blank', rel='noopener noreferrer', data_pane=pane_url(w), data_local=w, data_yt='1', data_title=title or None,
                 **{**kw, 'cls': ' '.join(x for x in ('pane-link yt-link', kw.get('cls')) if x)})
    if is_web(href): return A(label, href=href, target='_blank', rel='noopener noreferrer', **{**kw, 'cls': ' '.join(x for x in ('out-link', kw.get('cls')) if x)})
    return Span(label, **{k: v for k, v in kw.items() if k == 'cls'})

def _trail(trail, title):
    "The trail in the bar: each part a link when it is local, then the page in the pane."
    out = []
    for t, h in trail: out += [A(t, href=h) if is_local(h) else Span(t), Span('›', cls='sep')]
    return Div(*out, B(title), cls='rh-trail')

def PaneHost(url, title:str='', trail=()):
    "The side pane open on `url`: the bar (the trail, New tab, ×), the grip, and the page in a frame. Nothing when `url` is not local."
    if not is_local(url): return ''
    title = title or 'Side pane'
    bar = Header(Div(_trail(trail, title), A('New tab ↗', href=url, target='_blank', cls='rh-own', title='Open this page in a new tab'),
                     Button('×', type='button', cls='rh-x', title='Close (Esc)', aria_label='Close the side pane'), cls='rh-top'), cls='rh-bar')
    grip = Div(cls='grip', role='separator', aria_orientation='vertical', aria_label='Resize the side pane', tabindex='0',
               title='Drag to resize. Double-click to reset.')
    return Aside(grip, bar, Iframe(src=pane_url(url), title=title), id='rh-pane', aria_label='Side pane')
