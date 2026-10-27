import os
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import Spin, asset_css, THEMES, MODES, look
from abhyasa import voice
from .cfg import Routes

_P = Path(__file__).parent
def assets(): return (asset_css(_P/'settings.css'),)

def size(n:int) -> str:
    "Bytes as MB or GB."
    return '' if not n else f'{n / 2**30:.1f} GB' if n >= 2**30 else f'{n / 2**20:.0f} MB'

def pct(x): return '' if x is None else f'{x:.0%}'

def Look():
    "The theme and the mode. A click changes the page at once (core.js), and the form saves the choice."
    t, m = look()
    def theme(k, note):
        return Label(Input(type='radio', name='theme', value=k, checked=k == t), Span(I(), I(), I(), cls='sw', data_theme=k),
                     Span(Span(k.capitalize(), cls='nm', data_theme=k), Small(note)))
    return Section(H2('Theme'),
        Form(Div(*[theme(k, n) for k, n in THEMES.items()], cls='themes', role='radiogroup', aria_label='Theme'),
             Div(*[Label(Input(type='radio', name='mode', value=k, checked=k == m), 'Auto, as the Mac' if k == 'auto' else k.capitalize())
                   for k in MODES], cls='modes-pick', role='radiogroup', aria_label='Light or dark'),
             hx_post=Routes.look, hx_trigger='change', hx_swap='none', data_quiet='1'),
        id='look')

def Status(sp):
    "The state of the model in use; it asks again each second while the model loads."
    poll = dict(hx_get=Routes.status, hx_trigger='every 1s', hx_swap='outerHTML') if sp.status.startswith('loading') else {}
    return Span(sp.status, id='stt-status', cls='mute', **poll)

def UseBtn(engine, model, label='Use', go=False):
    return Button(label, cls='go' if go else '', hx_post=Routes.get if go else Routes.use, hx_vals={'engine': engine, 'model': model},
                  hx_target='#speech', hx_swap='outerHTML', hx_indicator='#use-sp')

def Action(k, cur, s, key):
    "What a row can do: it is in use, or you can use it, get it, or not use it (no key)."
    m, e = k['model'], k['engine']
    if (e, m) == cur: return Span('In use', cls='inuse')
    if e == 'openai': return UseBtn(e, m) if key else Span('Set a key first', cls='mute')
    acts = [UseBtn(e, m) if voice.cached(m) else UseBtn(e, m, 'Get and use', go=True)]
    if m in s['downloaded']: acts.append(Button('Remove', hx_post=Routes.remove, hx_vals={'model': m}, hx_target='#speech', hx_swap='outerHTML',
                                                hx_confirm=f'Delete {m} from the Hugging Face cache?'))
    return Span(*acts, cls='acts')

def Where(k):
    if k['engine'] == 'openai': return Span('cloud', cls='cloud', title='This engine sends audio off this machine.')
    return Span('on this Mac', cls='ok') if voice.cached(k['model']) else Span('not here', cls='mute')

def Known(cur, s, key):
    "The models we measured, with the numbers from the voice notebook; then the models that this page downloaded."
    hd = Tr(*map(Th, ('Model', 'Where', '5 s', 'Clip A', 'Clip B', 'Terms', 'Memory', '')))
    def row(k):
        b = k.get('bench') or {}
        return Tr(Td(Div(k['label']), Div(k['note'], cls='mute')), Td(Where(k), cls='n'),
                  Td(f"{b['seg5']:.2f} s" if 'seg5' in b else '', cls='n'), Td(pct(b.get('wer_a')), cls='n'), Td(pct(b.get('wer_b')), cls='n'),
                  Td(f"{b['terms']}/9" if 'terms' in b else '', cls='n'), Td(f"{b['mem']:.1f} GB" if 'mem' in b else '', cls='n'),
                  Td(Action(k, cur, s, key)), cls='cur' if (k['engine'], k['model']) == cur else '')
    ids = {k['model'] for k in voice.KNOWN}
    more = [dict(engine='mlx', model=m, label=m.split('/')[-1], note='downloaded by this page') for m in s['downloaded'] if m not in ids]
    if cur[1] not in ids | set(s['downloaded']): more.append(dict(engine=cur[0], model=cur[1], label=cur[1].split('/')[-1], note='in use'))
    return Table(Thead(hd), Tbody(*map(row, voice.KNOWN + more)), cls='models')

def Speech(sp, key, oob=False):
    "The speech section: the model in use, cut at pauses, and the known models."
    s, cur = voice.settings(), voice.current()
    env = os.getenv('ABHYASA_STT')
    known = next((k['label'] for k in voice.KNOWN if (k['engine'], k['model']) == cur), cur[1])
    return Section(
        H2('Speech to text'),
        P(Strong(known), ' ', Span(f'{cur[0]} · {cur[1]}', cls='mute'), ' ', Status(sp), cls='inuse-line'),
        P(f'The speech engine is set to {env} outside this page ($ABHYASA_STT), so a choice here has no effect. '
          'In Abhyasa.app, open Abhyasa, then Settings, and set Speech engine to "From the Settings page".', cls='warn') if env else '',
        Label(Input(type='checkbox', name='on', checked=s['stt']['segment'], hx_post=Routes.segment, hx_trigger='change', hx_swap='none',
                    hx_vals='js:{on: event.target.checked ? 1 : 0}'),
              ' Cut at pauses', Span('The text comes after each pause. When this is off, the text comes every 10 seconds.', cls='note'), cls='check'),
        P('Clip A is English speech. Clip B has Nyāya terms in IAST and maths words. The model gets these terms as a hint. The numbers are word error rates on this Mac, with the model already loaded. Terms: the number of key terms written correctly. '
          '"5 s" is the time for one 5-second segment. Only one model is in memory at a time.', cls='mute'),
        Known(cur, s, key), Span(Spin('switching…'), id='use-sp'), id='speech', **(dict(hx_swap_oob='true') if oob else {}))

def Job(j):
    if j.state == 'downloading':
        done, tot = voice.cache_bytes(j.model), j.total
        return Li(f'Downloading {j.model}: {size(done) or "0 MB"}' + (f' of {size(tot)} ({min(done / tot, 1):.0%})' if tot else ''))
    if j.state == 'loading': return Li(f'Loading {j.model} into memory…')
    if j.state == 'failed': return Li(f'{j.model} failed: {j.error}', cls='no')
    return Li(f'{j.model} is ready and in use.', cls='ok')

def Jobs(jobs, oob=False):
    "Progress lines; they ask again each second while a download runs."
    run = any(j.state in ('downloading', 'loading') for j in jobs.values())
    poll = dict(hx_get=Routes.jobs, hx_trigger='every 1s', hx_swap='outerHTML') if run else {}
    return Div(Ul(*[Job(j) for j in jobs.values()], cls='plain jobs') if jobs else '', id='jobs', **poll, **(dict(hx_swap_oob='true') if oob else {}))

def Found(rows, cur):
    "The models that Hugging Face gives for the search."
    if not rows: return P('No speech to text models match. Try "whisper", "asr" or "parakeet".', cls='mute')
    def row(r):
        m = r['model']
        act = Span('In use', cls='inuse') if cur == ('mlx', m) else UseBtn('mlx', m) if voice.cached(m) else UseBtn('mlx', m, 'Get and use', go=True)
        return Tr(Td(A(m, href=f'https://huggingface.co/{m}')), Td(size(r['size']), cls='n'), Td(f"{r['downloads']:,}", cls='n'),
                  Td(Span('on this Mac', cls='ok') if voice.cached(m) else ''), Td(act))
    return Table(Thead(Tr(*map(Th, ('Model', 'Size', 'Downloads', '', '')))), Tbody(*map(row, rows)), cls='models')

def Lookup():
    return Section(H2('Look up models'),
        P('Search the mlx-community models on Hugging Face. The list shows only speech to text models that mlx-audio can load.', cls='mute'),
        Form(Input(type='search', name='q', placeholder='whisper, qwen3-asr, parakeet, voxtral…'), Button('Look up'), Spin('looking…'),
             hx_get=Routes.search, hx_target='#found', cls='row lookup'),
        Div(id='found'))

def Key(err=''):
    "The OpenAI key: where it is from and its last 4 characters. The key itself is never on the page."
    k, src = voice.openai_key()
    own = src == str(voice.cfg_dir()/'keys.env')
    have = (P('In use: ', Code(voice.masked(k)), ' from ', Span('the environment (OPENAI_API_KEY)' if src == 'environment' else src),
              '' if own or src == 'environment' else ' (read only)', '.', cls='mute') if k else P('There is no key. The OpenAI engine is off.', cls='mute'))
    return Section(H2('OpenAI key'),
        P(Strong('The OpenAI engine sends your audio off this machine.'), ' The other engines keep it here.', cls='warn'),
        have, P(err, cls='warn', role='alert') if err else '',
        Form(Input(type='password', name='key', placeholder='sk-…', autocomplete='off'), Button('Save key'),
             Button('Remove key', type='button', hx_post=Routes.key, hx_vals={'key': ''}, hx_target='#key', hx_swap='outerHTML') if own else '',
             hx_post=Routes.key, hx_target='#key', hx_swap='outerHTML', cls='row'),
        P(f'abhyasa keeps the key in {voice.cfg_dir()/"keys.env"}, with mode 0600. It never writes it to the vault.', cls='mute'),
        id='key')

TASK_NOTE = dict(question='writes each question and its hidden answer', grade='reads the conversation and grades it',
                 hint='gives the next hint', lesson='teaches the smallest step after a miss', extract='finds the concepts in a text')

OTHER = '__other__'   # the list item that shows a text box for a model id

def Pick(task, name, dflt, rows):
    "The model list for one task: the default, then the models grouped by provider, then 'Type another model id'."
    from abhyasa.llm import model_label, PROVIDERS, DFLT_MODEL
    groups, ids = {}, {r['value'] for r in rows}
    for r in rows: groups.setdefault(r.get('provider', ''), []).append(r)
    opt = lambda v, n: Option(n, value=v, selected=v == name, title=v)
    return Select(Option(f'Default: {model_label(dflt or DFLT_MODEL)}', value='', selected=not name),
                  Optgroup(opt(name, model_label(name)), label='Saved') if name and name not in ids else '',
                  *[Optgroup(*[opt(r['value'], r.get('name') or model_label(r['value'], p)) for r in rs], label=PROVIDERS.get(p, p.capitalize() or 'Other'))
                    for p, rs in groups.items()],
                  Option('Type another model id…', value=OTHER),
                  name='model', aria_label=f'The model for {task}', hx_post=Routes.model, hx_vals={'task': task}, hx_trigger='change',
                  hx_target=f'#tm-{task}', hx_swap='outerHTML')

def Typed(task, name):
    "A text box for a model id that the list does not have."
    return Span(Input(type='text', name='model', value=name, placeholder='a model id, such as claude/sonnet', autofocus=True,
                      hx_post=Routes.model, hx_vals={'task': task}, hx_trigger='change', hx_target=f'#tm-{task}', hx_swap='outerHTML',
                      autocomplete='off', spellcheck='false', aria_label=f'The model id for {task}'),
                Button('Back to the list', type='button', hx_post=Routes.model, hx_vals={'task': task, 'model': name},
                       hx_target=f'#tm-{task}', hx_swap='outerHTML'), cls='acts')

def TaskRow(task, name, dflt, rows, typing=False):
    "One tutor task: its model (empty means the default), and a test."
    return Tr(Td(Span(task, cls='task'), Br(), Span(TASK_NOTE[task], cls='mute')),
              Td(Typed(task, name) if typing else Pick(task, name, dflt, rows)),
              Td(Button('Test', type='button', hx_post=Routes.test, hx_vals={'task': task}, hx_include='closest tr', hx_target=f'#tt-{task}',
                        data_wait='Testing…'), Span(id=f'tt-{task}', cls='mute')),
              id=f'tm-{task}')

def Tasks(router, rows):
    "The table of tutor tasks, each with its model list."
    from abhyasa.llm import TASKS
    ms = voice.settings()['models']
    return Table(Tbody(*[TaskRow(t, ms.get(t, ''), router.model, rows) for t in TASKS]), cls='models tasks', id='tasks')

def Tutor(router):
    "The model for each tutor task. A quick model can grade and give hints. A strong model can write questions and lessons."
    return Section(H2('Tutor models'),
        P('Choose a model for each task. "Default" uses the model that the app started with. '
          'The list shows the models that can run here. A change works at once. "Test" times one short call.', cls='mute'),
        Div(Spin('getting the list of models…'), hx_get=Routes.catalog, hx_trigger='load', hx_swap='outerHTML', id='tasks'),
        id='tutor-models')
