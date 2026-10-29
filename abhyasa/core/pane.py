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
- `rh:open {url}`: open `url` in the same pane (a nested side page).
- `rh:close`: close the pane. `rh:close {level: 1}` goes back one level only: to the last part of the trail, or, when there is
  no part in the pane, the pane closes (⌥Z).
- `rh:done {slug, outcome}`: the side walk ended. The host sends it again as the DOM event `abhyasa:rh-done` on `document`, with
  `detail = {slug, outcome}`. The detail comes from the page in the pane: the host must treat it as input that it cannot trust.
- `rh:link {url}`: open `url` outside the pane, in a new tab with `noopener` (Leela sends it). The URL must pass `is_web`: http
  or https only. The host refuses all other schemes, such as `javascript:`, `data:` and `file:`."""
import re
from urllib.parse import urlsplit, urlunsplit
from fasthtml.common import A, Aside, B, Button, Div, Header, Iframe, Span

__all__ = ['is_local', 'is_web', 'pane_url', 'pane_link', 'PaneHost']

_BAD = re.compile(r'[\x00-\x1f\x7f\\]')   # a control character or a backslash: a browser can make either into a way out of the app

def is_local(url) -> bool:
    "Whether `url` is a path in this app: one `/` at the start, no scheme, no host, no backslash and no control character."
    return isinstance(url, str) and url.startswith('/') and not url.startswith('//') and not _BAD.search(url)

_WEB = re.compile(r'https?://[^\s/?#\\]+[^\s\\]*\Z', re.I)   # http or https, a host, and no space

def is_web(url) -> bool:
    "Whether `url` is an http or https URL with a host, and no space, backslash or control character: a link that `rh:link` can open."
    return isinstance(url, str) and bool(_WEB.match(url)) and not _BAD.search(url)

def pane_url(url) -> str|None:
    "`url` with `pane=1` in its query, when it is a local path; else None."
    if not is_local(url): return None
    p = urlsplit(url)
    q = [x for x in p.query.split('&') if x and not x.startswith('pane=')] + ['pane=1']
    return urlunsplit(('', '', p.path, '&'.join(q), p.fragment))

def pane_link(label, href:str, title:str='', cls:str='pane-link', **kw):
    "A real link to `href` in a new tab; `pane.js` opens it in the side pane on a wide screen, or in the same tab on a narrow one."
    return A(label, href=href, target='_blank', data_pane=pane_url(href), data_title=title or None, cls=cls, **kw)

def _trail(trail, title):
    "The trail in the bar: each part a link when it is local, then the page in the pane."
    out = []
    for t, h in trail: out += [A(t, href=h) if is_local(h) else Span(t), Span('›', cls='sep')]
    return Div(*out, B(title), cls='rh-trail')

def PaneHost(url, title:str='', trail=()):
    "The side pane open on `url`: the bar (the trail, Its own session, ×), the grip, and the page in a frame. Nothing when `url` is not local."
    if not is_local(url): return ''
    title = title or 'Side pane'
    bar = Header(Div(_trail(trail, title), A('Its own session ↗', href=url, target='_blank', cls='rh-own', title='Open this page in a new tab'),
                     Button('×', type='button', cls='rh-x', title='Close (Esc)', aria_label='Close the side pane'), cls='rh-top'), cls='rh-bar')
    grip = Div(cls='grip', role='separator', aria_orientation='vertical', aria_label='Resize the side pane', tabindex='0',
               title='Drag to resize. Double-click to reset.')
    return Aside(grip, bar, Iframe(src=pane_url(url), title=title), id='rh-pane', aria_label='Side pane')
