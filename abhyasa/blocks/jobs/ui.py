"The activity chip in the top bar: what runs now and what ended, each with the link to its page."
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import asset_css, Quiet
from abhyasa.jobs import chip_words, job_version
from .cfg import Routes

_P = Path(__file__).parent
ENDED_WORDS = dict(done='Ready.', closed='It stopped because abhyasa closed.', failed='It did not work.')

def Row(r):
    "One job: its title, a link to its page, and what it does now or how it ended."
    name = A(r.get('title') or 'A job', href=r.url) if r.get('url') else Span(r.get('title') or 'A job')
    line = (r.get('said') if r.state in ('running', 'done') else r.get('why') if r.state == 'failed' else '') or ENDED_WORDS.get(r.state, '')
    return Li(name, Span(line, cls='mute') if line else '', cls=f'job {r.state}')

def Inside(rows):
    "The summary (the chip itself) and the list. Nothing when no job runs and no result is new."
    if not rows: return ()
    run = any(r.state == 'running' for r in rows)
    clear = '' if run else Quiet('Clear', small=True, type='button', hx_post=Routes.seen, hx_target='#activity', hx_swap='innerHTML')
    return (Summary(chip_words(rows), cls='running' if run else rows[0].state, data_part='activity', **({'data_stream': '1'} if run else {})),
            Div(Ul(*map(Row, rows), cls='plain'), clear, cls='activity-list'))

def Chip(rows):
    """The activity chip: a small fold in the top bar while a job runs or a result is new. An event of the stream (`job`) loads its
    inside again, so it opens and changes in place. `data-v` is the count of changes when the page was drawn."""
    return asset_css(_P/'jobs.css'), Details(*Inside(rows), id='activity', cls='activity', data_job='*', data_v=str(job_version()),
                   hx_get=Routes.chip, hx_trigger='job', hx_swap='innerHTML')
