"""Your sources: each document that your walks read, with its kind, the walks and talks that use it, and the date you added it.
A folder or a repo that you filed is one row, and so is a paper with its PDF and its HTML copy. The vedicreader import and the indexers are under More."""
import json, re, time
from datetime import datetime, timezone
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import Page, Part, RouteOverrides, n_of, can_undo
from abhyasa.ground import VedicSource, index_ramabana, index_notebooks, RAMA_CFG
from abhyasa.journey import for_talk
from abhyasa.sources import ARXIV_ID, ARXIV_LINK, WEB, YOURS, source_of, vault_roots, root_docs
import abhyasa.talk   # `Learning.talks`
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning', 'sources')

INDEXERS = dict(
    ramabana=('ramabana sessions', 'One document for each session from ~/.config/ramabana, on the shelf "ramabana".'),
    notebooks=('leela agent sessions', 'Each notebook in a _leela_agent_sessions folder under ~/code, on the shelf "notebooks".'))
TEXT = 'text'

def _refs(j):
    "The `(shelf, doc_id)` of each document that walk `j` reads: its source, the documents of a link or a folder, and the passage of each step."
    src = j.get('source') or {}
    out = [(src.get('shelf'), src.get('doc_id'))] + [(d.get('shelf'), d.get('doc_id')) for d in src.get('docs') or ()]
    for s in j.get('steps') or ():
        if (h := source_of(s.get('read') or {}).href): out.append(tuple(h.split('/')[2:4]))
    return [(sh, d) for sh, d in dict.fromkeys(out) if sh and d]

ARXIV_HTML = re.compile(rf'(?:https?://)?(?:www\.)?arxiv\.org/html/({ARXIV_ID.pattern})/?', re.I)

def _paper(source) -> str:
    """The arXiv id of the paper at `source` (an `arxiv.org/abs`, `pdf` or `html` link, with any query), with no version, so the PDF
    copy and the HTML copy (`abs/<id>`, or `abs/<id>?html=<sha>` for a changed copy) are one row; '' for another document."""
    s = re.split(r'[?#]', str(source or '').strip(), maxsplit=1)[0]
    m = ARXIV_LINK.fullmatch(s) or ARXIV_HTML.fullmatch(s)
    return re.sub(r'v\d+$', '', m[1]) if m else ''

def _added(d) -> float:
    "When the vault filed document `d`: its `added_at` is a UTC time as text, `2026-10-30 01:38:44`, or a number."
    x = d['added_at'] if d else None
    if isinstance(x, (int, float)): return float(x)
    try: return datetime.strptime(str(x)[:19], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp()
    except ValueError: return 0.

def connect(app, ctx):
    lr = ctx.learning

    def shelves():
        "The shelves of the vault by name, so a walk that names a shelf that is not there never makes one."
        names = {s['store'] for s in lr.vault.shelves()}
        return {n: lr.vault if n == 'store' else lr.vault.shelf(n) for n in names}

    def rows():
        "One row for each source, the newest first."
        shs, docs, out = shelves(), {}, {}
        def doc(sh, did):
            if (sh, did) not in docs: docs[sh, did] = first(shs[sh].t.docs(where='id=?', where_args=[did])) if sh in shs else None
            return docs[sh, did]
        js = [j for j in lr.journeys() if not for_talk(j)]
        talks = {}
        for t in lr.talks(): talks.setdefault((t.get('src') or {}).get('walk'), []).append(t)
        roots = {}
        for j in js:   # the newest walk first, so each root keeps its newest filing
            for f in j.get('filed') or ():
                if not f.get('undone'): roots.setdefault(f['root'], (j, f))

        def row(key, **kw): return out.setdefault(key, AttrDict(dict(docs=[], used=[], at=0, root='', shelf='', undo='', copies=False), **kw))
        for j in js:
            used = [(j.title, Routes.of(Routes.walk if j.get('mode') == 'walk' else Routes.path, jid=j.id))] + [(t.title, Routes.of(Routes.talk, tid=t.id)) for t in talks.get(j.id, ())]
            got = False
            for sh, did in _refs(j):
                if not (d := doc(sh, did)): continue
                m, got = json.loads(d['meta'] or '{}'), True
                href = Routes.of(Routes.doc, shelf=sh, doc_id=did)
                if (rt := m.get('root')):
                    r = row(('root', sh, rt), title=rt, href='', kind=YOURS)
                    r.root, r.shelf = rt, sh
                elif (aid := _paper(d['source'])):
                    r = row(('paper', aid), title=d['title'], href=href, kind=YOURS)
                    r.copies = True
                else: r = row(('doc', sh, did), title=d['title'], href=href, kind=WEB if d['kind'] == 'web' else YOURS)
                if (d['title'], href) not in r.docs: r.docs.append((d['title'], href))
                r.at = r.at or _added(d)
                r.used += [u for u in used if u not in r.used]
            if not got and any((s.get('read') or {}).get('doc_id') == j.id for s in j.get('steps') or ()):   # pasted text: it is not in the vault
                r = row(('text', j.id), title=j.title, href='', kind=TEXT, at=j.get('created') or 0)
                r.used += [u for u in used if u not in r.used]
        for rt in vault_roots(lr):   # a folder or a repo that is filed, also when its walk failed
            ds = root_docs(lr, rt)
            r = row(('root', 'notebooks', rt), title=rt, href='', kind=YOURS)
            r.root, r.shelf = rt, 'notebooks'
            r.docs = [(d.title, Routes.of(Routes.doc, shelf=d.shelf, doc_id=d.doc_id)) for d in ds]
            if not r.at: r.at = min((_added(doc(d.shelf, d.doc_id)) for d in ds), default=0)
        for r in out.values():
            if r.root and (jf := roots.get(r.root)):
                j, f = jf
                r.at = f.get('at') or r.at
                if can_undo(f): r.undo = j.id
        return sorted(out.values(), key=lambda r: -(r.at or 0))

    def page():
        vs = VedicSource()
        return Page('Sources', H1('Sources'),
            P('Each document that your walks read. The tutor uses them for its questions and does not change them.', cls='mute'),
            ui.Rows(rows()),
            Part('Add more sources', more_label='More', more=[
                P(f"vedicreader library: {len(vs.dbs())} verse databases in {vs.dir}." if vs.dbs() else 'vedicreader library: not found. Set VEDICREADER_ROOT to the vedicreader repo.', cls='mute'),
                P(B('Ramayana episodes'), ': ', st.status() if (st := first(s for s in ctx.sources if getattr(s, 'name', '') == 'vedicstory')) else
                  'Not found. Set VEDICREADER_ROOT to the vedicreader repo.', cls='mute'),
                P('vedicreader: Sanskrit lessons and terms, and the jyotiṣa grahas, rāśis and nakṣatras, from the repo files.', cls='mute'),
                Button('Import vedicreader', hx_post='/add/vedicreader', hx_target='#vr', data_wait='Importing…', data_skel='#vr'), Div(id='vr'),
                P('Each button below adds a shelf to your vault, so every tool can search it. They change no other shelf. A second run skips what did not change.', cls='mute'),
                *[Div(Button(f'Index {t}', hx_post=Routes.index.format(what=k), hx_target=f'#ix-{k}', data_wait='Indexing…', data_skel=f'#ix-{k}'),
                      Span(d, cls='mute'), Div(id=f'ix-{k}', cls='ix'), cls='row') for k, (t, d) in INDEXERS.items()]], cls='sources-more'),
            on='Library', sub='Sources')

    def index(what:str):
        t = time.time()
        if what == 'ramabana': n = index_ramabana(lr.vault, RAMA_CFG)
        elif what == 'notebooks': n = index_notebooks(lr.vault, [str(Path.home()/'code')], only_agent=True)
        else: return P('Unknown source.', cls='mute')
        return P(', '.join(f'{v} {k}' for k, v in n.items()) + f' in {time.time() - t:.0f} s.', cls='mute')

    def remove(shelf:str='notebooks', root:str=''):
        "Forget each document of the folder or repo `root` on `shelf`. The walks keep their steps and passages."
        if shelf not in shelves() or not (ds := root_docs(lr, root, shelf)): return Li(P('There is nothing to remove.', cls='mute'))
        sh = lr.vault.shelf(shelf)
        for d in ds: sh.forget(d.doc_id)
        return Li(P(f"Removed {root} from your vault: {n_of(len(ds), 'document')}.", cls='mute'))

    RouteOverrides.subtabs.setdefault('Library', []).append(('Sources', Routes.base, 1))
    app.get(Routes.base)(page)
    app.post(Routes.index)(index)
    app.post(Routes.remove)(remove)
