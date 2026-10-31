"""The background jobs, in one place: the activity chip in the top bar (`nav_extra`), the event stream that tells a page that a job
changed, and the state of the jobs for the Mac app. The rows are in `abhyasa.jobs`; the blocks that run a job write them."""
import asyncio, json, time
from fasthtml.common import *
from starlette.responses import StreamingResponse
from abhyasa.core import hook, n_of
from abhyasa.jobs import activity, ENDED, FRESH, job_version
from abhyasa.research import research_state
from . import ui
from .cfg import Routes

__all__ = ['CAPS', 'connect']
CAPS = ('learning',)
TICK = 1.0          # seconds between two reads of the rows in the event stream
MOST = 3600         # seconds that one stream stays open at most; the page opens a new one after its next swap

def connect(app, ctx):
    lr = ctx.learning

    def counted(r):
        "A research row that ended says how many ideas of its walk have a source now."
        if r.get('kind') != 'research' or r.state == 'running' or not (j := lr.journey((r.get('obj') or '')[5:])): return r
        ideas = [s for s in j.steps if s.get('status') != 'skip']   # each idea of the walk, as the research line counts them
        have = sum(bool((s.get('read') or {}).get('text')) for s in ideas)
        return AttrDict(r, said=f"{have} of {n_of(len(ideas), 'idea')} {'has' if have == 1 or len(ideas) == 1 else 'have'} a source.")

    def now(): return [counted(r) for r in activity(lr)]

    @hook('nav_extra')
    def chip(): return ui.Chip(now())

    def inside(): return ui.Inside(now())

    def seen():
        "Clear: each ended job in the chip is seen, so the chip goes until a new job runs."
        for r in activity(lr):
            if r.state in ENDED: lr.put_job(r.key, seen=True)
        return inside()

    def row(r):
        "One row for the Mac app. A research row also has the walk id and its count of ideas with a source."
        out = dict(key=r.key, kind=r.get('kind'), state=r.state, title=r.get('title') or '', said=r.get('said') or '', why=r.get('why') or '',
                   start=r.get('start'), end=r.get('end'), url=r.get('url') or '', seen=bool(r.get('seen')))
        if r.get('kind') == 'research' and (j := lr.journey((r.get('obj') or '')[5:])):
            s = research_state(j)
            out.update(id=j.id, have=s.have, total=s.total)
        return out

    def rows():
        "The jobs that run now, and the jobs that ended in the last `FRESH` seconds, newest first, for the Mac app."
        now, rs = time.time(), [r for r in lr.jobs().values() if not r.get('quiet')]
        run = sorted((r for r in rs if r.state == 'running'), key=lambda r: -(r.get('start') or 0))
        end = sorted((r for r in rs if r.state in ENDED and now - (r.get('end') or 0) < FRESH), key=lambda r: -(r.get('end') or 0))
        return [row(r) for r in run], [row(r) for r in end]

    def data():
        run, end = rows()
        return JSONResponse(dict(running=run, ended=end))

    def research():
        "The old shape for a Mac app of 0.0.15 and older: only research, each walk with its id, title, link, end and count."
        keep = lambda xs: [dict(id=x['id'], title=x['title'], url=x['url'], end=x['end'], have=x['have'], total=x['total']) for x in xs if x['kind'] == 'research' and 'id' in x]
        run, end = rows()
        return JSONResponse(dict(running=keep(run), ended=keep(end)))

    def changes(rows, last, ups):
        "The events since the last read: a row that changed, and a walk of a running job that changed (a passage came, a source was filed)."
        out = {}
        for k, r in rows.items():
            if last is not None and last.get(k) != (r.state, r.get('said'), r.get('end')): out[r.get('obj') or k] = dict(key=k, obj=r.get('obj') or k, state=r.state)
        for r in rows.values():
            if r.state != 'running' or not (o := r.get('obj') or '').startswith('walk:'): continue
            u = (lr.journey(o[5:]) or {}).get('updated')
            if o in ups and ups[o] != u: out.setdefault(o, dict(key=r.key, obj=o, state='running'))
            ups[o] = u
        return list(out.values())

    async def events(req, v:int=-1):
        """One event stream while a job runs. Each event is `{key, obj, state}`; the parts of the page that wait for that object load
        again. When no job runs, it sends `end` and closes, so a page with nothing to wait for keeps no connection. `v` is the count of
        changes when the page was drawn: a change after it sends one event for every part."""
        async def stream():
            last, ups, t0 = None, {}, time.monotonic()
            while time.monotonic() - t0 < MOST and not await req.is_disconnected():
                rs = await asyncio.to_thread(lr.jobs)
                out = await asyncio.to_thread(changes, rs, last, ups)
                if last is None and v >= 0 and v != job_version(): out = [dict(key='*', obj='*', state='')]
                for e in out: yield f'data: {json.dumps(e)}\n\n'
                if not any(r.state == 'running' for r in rs.values()): break
                last = {k: (r.state, r.get('said'), r.get('end')) for k, r in rs.items()}
                await asyncio.sleep(TICK)
            yield 'event: end\ndata: {}\n\n'
        return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-store'})

    app.get(Routes.chip)(inside)
    app.post(Routes.seen)(seen)
    app.get(Routes.events)(events)
    app.get(Routes.data)(data); app.router.routes.insert(0, app.router.routes.pop())   # before the static route for `.json`
    app.get(Routes.research)(research); app.router.routes.insert(0, app.router.routes.pop())
