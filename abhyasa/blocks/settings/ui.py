"The Settings page: a side index of the groups, then each group on quiet hairline rows, with the rarely changed values under a closed `More`."
import os
from pathlib import Path
from fasthtml.common import *
from abhyasa.core import n_of, Spin, asset_css, asset_js, THEMES, MODES, look, SettingRow, RangeLine, row_id, say
from abhyasa import voice
from abhyasa.settings import GROUPS, SETTINGS, TASK_HELP, TASK_LABEL, BORROWS, rows, val, raw, clamped
from .cfg import Routes

_P = Path(__file__).parent
def assets(): return (asset_css(_P/'settings.css'), asset_js(_P/'settings.js'))

def size(n:int) -> str:
    "Bytes as MB or GB."
    return '' if not n else f'{n / 2**30:.1f} GB' if n >= 2**30 else f'{n / 2**20:.0f} MB'

def pct(x): return '' if x is None else f'{x:.0%}'

def reset_attrs(name): return dict(hx_post=Routes.default, hx_vals={'name': name}, hx_target=f'#{row_id(SETTINGS[name])}', hx_swap='outerHTML')

def Row(r, v):
    "A setting row on this page: its value posts to `Routes.value`, and `Use the default` to `Routes.default`."
    return SettingRow(r, v, Routes.value, reset_attrs(r.name), file=clamped(r.name) if r.store == 'file' else None)

def More(group, *items, names=()):
    "The closed part of a group: `More in Walks: passage length, note length, depth, and 2 more`."
    if not any(items): return ''
    ns = [n[:1].lower() + n[1:] for n in names]   # only the first letter: "journeys on Today", not "journeys on today"
    say_ = ', '.join(ns[:3]) + (f', and {len(ns) - 3} more' if len(ns) > 3 else '')
    return Details(Summary(f'More in {GROUPS[group][0]}' + (f': {say_}' if ns else '')), *items, cls='more')

def Head(g, n=0):
    "The group label, and `Use the defaults for this group` when the group has changed values."
    return Div(H2(GROUPS[g][0]), GroupReset(g, n), cls='ghead')

def GroupReset(g, n=0, ask=False, oob=False):
    "`Use the defaults for this group`; it asks one time before it changes the values."
    o = dict(hx_swap_oob='true') if oob else {}
    if not n: return Span(id=f'gr-{g}', cls='greset', **o)
    if ask:
        return Span(f"Use the default for {n_of(n, 'value')} in {GROUPS[g][0]}? ",
                    Button('Yes', type='button', cls='quiet small', hx_post=Routes.group_default, hx_vals={'group': g}, hx_target=f'#g-{g}', hx_swap='outerHTML'),
                    Button('No', type='button', cls='quiet small', hx_get=Routes.group_ask, hx_vals={'group': g, 'no': 1}, hx_target=f'#gr-{g}', hx_swap='outerHTML'),
                    id=f'gr-{g}', cls='greset ask', **o)
    return Span(A('Use the defaults for this group', href='#', hx_get=Routes.group_ask, hx_vals={'group': g}, hx_target=f'#gr-{g}', hx_swap='outerHTML'),
                id=f'gr-{g}', cls='greset', **o)

def Group(g, n, *shown, more=(), names=(), extra=()):
    "One group: the head, one lead line, the rows that show, then the closed `More` part."
    return Section(Head(g, n), P(GROUPS[g][1], cls='lead'), *extra, Ul(*shown, cls='plain srows') if shown else '',
                   More(g, *more, names=names), id=f'g-{g}', cls='sgroup')

def RowGroup(g, n, value, extra=(), more_extra=()):
    "A group made only of setting rows: `value(r)` gives the value of row `r`."
    rs = [r for r in rows(g) if r.ui]
    sh, mo = [r for r in rs if not r.more], [r for r in rs if r.more]
    return Group(g, n, *[Row(r, value(r)) for r in sh], extra=extra,
                 more=(Ul(*[Row(r, value(r)) for r in mo], cls='plain srows') if mo else '', *more_extra), names=[r.label for r in mo])

def Index(counts):
    "The side index: a box that finds a setting, then a link to each group, with a dot and the count of changed values."
    return Nav(Input(type='search', placeholder='Find a setting', id='sfind', aria_label='Find a setting', autocomplete='off'),
               Ul(*[IndexItem(g, counts.get(g, 0)) for g in GROUPS], cls='six'), cls='sindex', aria_label='Groups of settings')

def IndexItem(g, n, oob=False):
    return Li(A(GROUPS[g][0], Span(f' · {n}', cls='n') if n else '', Span(cls='dot on') if n else '', href=f'#g-{g}'),
              id=f'ix-{g}', **(dict(hx_swap_oob='true') if oob else {}))

def Look():
    "The theme and the mode. A click changes the page at once (core.js), and the form saves the choice."
    t, m = look()
    def theme(k, note):
        return Label(Input(type='radio', name='theme', value=k, checked=k == t), Span(I(), I(), I(), cls='sw', data_theme=k),
                     Span(Span(k.capitalize(), cls='nm', data_theme=k), Small(note)))
    return Group('look', 0, extra=(
        Form(Div(*[theme(k, n) for k, n in THEMES.items()], cls='themes', role='radiogroup', aria_label='Theme'),
             Div(*[Label(Input(type='radio', name='mode', value=k, checked=k == m), 'Auto, as the Mac' if k == 'auto' else k.capitalize())
                   for k in MODES], cls='modes-pick', role='radiogroup', aria_label='Light or dark'),
             hx_post=Routes.look, hx_trigger='change', hx_swap='none', data_quiet='1', id='look'),))

def Status(sp):
    "The state of the model in use; it asks again each second while the model loads."
    poll = dict(hx_get=Routes.status, hx_trigger='every 1s', hx_swap='outerHTML') if sp.status.startswith('loading') else {}
    return Span(sp.status, id='stt-status', cls='mute', **poll)

def UseBtn(engine, model, get=False):
    "Use a model that is here, or `get` it first: a plain button, since the page has no main action."
    return Button('Download' if get else 'Use', hx_post=Routes.get if get else Routes.use, hx_vals={'engine': engine, 'model': model},
                  title='Download the model, then use it' if get else None, hx_target='#speech', hx_swap='outerHTML', hx_indicator='#use-sp')

def Action(k, cur, s, key):
    "What a row can do: it is in use, or you can use it, get it, or not use it (no key)."
    m, e = k['model'], k['engine']
    if (e, m) == cur: return Span('In use', cls='inuse')
    if e == 'openai': return UseBtn(e, m) if key else Span('Set a key first', cls='mute')
    acts = [UseBtn(e, m) if voice.cached(m) else UseBtn(e, m, get=True)]
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
    "The model in use and the known models, with their numbers."
    s, cur = voice.settings(), voice.current()
    env = os.getenv('ABHYASA_STT')
    known = next((k['label'] for k in voice.KNOWN if (k['engine'], k['model']) == cur), cur[1])
    return Div(
        P(Strong(known), ' ', Span(f'{cur[0]} · {cur[1]}', cls='mute'), ' ', Status(sp), cls='inuse-line'),
        P(f'The speech engine is set to {env} outside this page ($ABHYASA_STT), so a choice here has no effect. '
          'In Abhyasa.app, open Abhyasa, then Settings, and set Speech engine to "From the Settings page".', cls='warn') if env else '',
        P('Clip A is English speech. Clip B has Nyāya terms in IAST and maths words. The model gets these terms as a hint. The numbers are word error rates on this Mac, with the model already loaded. Terms: the number of key terms written correctly. '
                  '"5 s" is the time for one 5-second segment. Only one model is in memory at a time.', cls='mute'),
        Known(cur, s, key),
        Span(Spin('switching…'), id='use-sp'), id='speech', **(dict(hx_swap_oob='true') if oob else {}))

def SpeechGroup(sp, key, jobs, n):
    "Speech to text: the model in use and the model table, cut at pauses, then the pauses, the model search and the OpenAI key under More."
    return RowGroup('stt', n, lambda r: val(r.name), extra=(Speech(sp, key), Jobs(jobs)), more_extra=(Lookup(), Key()))

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
        act = Span('In use', cls='inuse') if cur == ('mlx', m) else UseBtn('mlx', m) if voice.cached(m) else UseBtn('mlx', m, get=True)
        return Tr(Td(A(m, href=f'https://huggingface.co/{m}')), Td(size(r['size']), cls='n'), Td(f"{r['downloads']:,}", cls='n'),
                  Td(Span('on this Mac', cls='ok') if voice.cached(m) else ''), Td(act))
    return Table(Thead(Tr(*map(Th, ('Model', 'Size', 'Downloads', '', '')))), Tbody(*map(row, rows)), cls='models')

def Lookup():
    return Div(H3('Look up models', cls='sub'),
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
    return Div(H3('OpenAI key', cls='sub'),
        P(Strong('The OpenAI engine sends your audio off this machine.'), ' The other engines keep it here.', cls='warn'),
        have, P(err, cls='warn', role='alert') if err else '',
        Form(Input(type='password', name='key', placeholder='sk-…', autocomplete='off'), Button('Save key'),
             Button('Remove key', type='button', hx_post=Routes.key, hx_vals={'key': ''}, hx_target='#key', hx_swap='outerHTML') if own else '',
             hx_post=Routes.key, hx_target='#key', hx_swap='outerHTML', cls='row'),
        P(f'abhyasa keeps the key in {voice.cfg_dir()/"keys.env"}, with mode 0600. It never writes it to the vault.', cls='mute'),
        id='key')

OTHER = '__other__'   # the list item that shows a text box for a model id

def Pick(task, name, dflt_label, rows):
    "The model list for one task: the default, then the models grouped by provider, then 'Type another model id'."
    from abhyasa.llm import model_label, PROVIDERS
    groups, ids = {}, {r['value'] for r in rows}
    for r in rows: groups.setdefault(r.get('provider', ''), []).append(r)
    opt = lambda v, n: Option(n, value=v, selected=v == name, title=v)
    return Select(Option(dflt_label, value='', selected=not name),
                  Optgroup(opt(name, model_label(name)), label='Saved') if name and name not in ids else '',
                  *[Optgroup(*[opt(r['value'], r.get('name') or model_label(r['value'], p)) for r in rs], label=PROVIDERS.get(p, p.capitalize() or 'Other'))
                    for p, rs in groups.items()],
                  Option('Type another model id…', value=OTHER),
                  name='model', id=f'{row_id(SETTINGS["models." + task])}-c', aria_label=f'The model for {TASK_LABEL.get(task, "the default").lower()}',
                  hx_post=Routes.model, hx_vals={'task': task}, hx_trigger='change', hx_target=f'#{row_id(SETTINGS["models." + task])}', hx_swap='outerHTML')

def Typed(task, name):
    "A text box for a model id that the list does not have."
    i = row_id(SETTINGS['models.' + task])
    return Span(Input(type='text', name='model', value=name, placeholder='a model id, such as claude/sonnet', autofocus=True, id=f'{i}-c',
                      hx_post=Routes.model, hx_vals={'task': task}, hx_trigger='change', hx_target=f'#{i}', hx_swap='outerHTML',
                      autocomplete='off', spellcheck='false', aria_label=f'The model id for {task}'),
                Button('Back to the list', type='button', hx_post=Routes.model, hx_vals={'task': task, 'model': name},
                       hx_target=f'#{i}', hx_swap='outerHTML'), cls='acts')

def fallback(task, router) -> str:
    "What an empty model means for `task`: the model it borrows, else the default model."
    from abhyasa.llm import model_label, DFLT_MODEL
    if task == 'default': return f"abhyasa's default: {model_label(DFLT_MODEL)}"
    dm = router.model or DFLT_MODEL
    if task in BORROWS: return f'Same as {TASK_LABEL[BORROWS[task]].lower()}: {model_label(router.name(BORROWS[task]) or dm)}'
    return f'Default: {model_label(dm)}'

def ModelRow(task, router, rows, typing=False, set_by=''):
    "One model row: the list of models and a Test button. `set_by` says what sets the default model outside this page."
    from abhyasa.llm import model_label, DFLT_MODEL
    r = SETTINGS['models.' + task]
    name, i = (val(r.name) or ''), row_id(r)
    test = '' if task == 'default' else Span(Button('Test', type='button', cls='quiet small', hx_post=Routes.test, hx_vals={'task': task},
                                                    hx_include=f'#{i}-c', hx_target=f'#{i}-t', data_wait='Testing…'), Span(id=f'{i}-t', cls='mute'))
    ctl = Div(Typed(task, name) if typing else Pick(task, name, fallback(task, router), rows), test, cls='mrow')
    rng = Div(Span(f'{set_by} sets the model now, so this choice has no effect.', cls='no') if set_by else Span(f"default {model_label(DFLT_MODEL)}" if task == 'default' else
                                                                                                 f'default: the model for {TASK_LABEL[BORROWS[task]].lower()}' if task in BORROWS else 'default: the default model'),
              A('Use the default', href='#', cls='use', hx_post=Routes.model, hx_vals={'task': task, 'model': ''}, hx_target=f'#{i}', hx_swap='outerHTML') if name else '',
              cls='rng', id=f'{i}-m')
    return Li(Div(Span(cls='dot' + (' on' if name else ''), id=f'{i}-dot'), Label(r.label, fr=f'{i}-c'), P(r.help, cls='help'), cls='lft'),
              Div(ctl, rng, cls='rgt'), cls='srow', id=i, data_find=f'{r.label} {r.help}'.lower())

def Models(router, cat, set_by=''):
    "The model rows: the default and the four main tasks, then the other tasks and the reply caps under More."
    main, other = ('default', 'question', 'grade', 'hint', 'lesson'), ('extract', *BORROWS)
    caps = [r for r in rows('models') if r.name.startswith('tokens.')]
    return Div(Ul(*[ModelRow(t, router, cat, set_by=set_by if t == 'default' else '') for t in main], cls='plain srows'),
               More('models', Ul(*[ModelRow(t, router, cat) for t in other], cls='plain srows'), Ul(*[Row(r, val(r.name)) for r in caps], cls='plain srows'),
                    names=[TASK_LABEL[t] for t in other] + ['reply caps']), id='models')

def ModelsGroup(n):
    "The Models group. The model lists load after the page, because the list of models can take a moment."
    return Group('models', n, extra=(Div(Spin('getting the list of models…'), hx_get=Routes.catalog, hx_trigger='load', hx_swap='outerHTML', id='models'),))

def registry() -> dict:
    "The editable prompts. Each engine module adds its own when it loads."
    import abhyasa.tutor, abhyasa.demo, abhyasa.nb, abhyasa.voice, abhyasa.journey, abhyasa.walk, abhyasa.profile, abhyasa.method, abhyasa.sources, abhyasa.talk
    from abhyasa.prompts import PROMPTS
    return PROMPTS

def PromptItem(p, text=None, err='', said=''):
    "One prompt: its label, a note on what it changes, and a raised editor with the text in use. `err` says why a text was refused."
    from abhyasa.prompts import saved, prompt
    mine, pid = p.name in saved(), 'pr-' + p.name.replace('.', '-')
    return Details(Summary(Span(cls='dot' + (' on' if mine else '')), Span(p.label, cls='nm'), Span('Your text' if mine else 'The default', cls='mute state')),
                   P(p.note, cls='mute note'),
                   Form(Textarea(prompt(p.name) if text is None else text, name='text', spellcheck='false', autocomplete='off',
                                 aria_label=f'The text of {p.label}'),
                        P(err, cls='no', role='alert') if err else '',
                        Div(Button('Save'), Button('Use the default', type='button', hx_post=Routes.prompt_default, hx_vals={'name': p.name},
                                                   hx_target=f'#{pid}', hx_swap='outerHTML'),
                            Span(said, cls='ok') if said else '', cls='acts'),
                        hx_post=Routes.prompt, hx_vals={'name': p.name}, hx_target=f'#{pid}', hx_swap='outerHTML', cls='raised'),
                   id=pid, cls='prompt', open=bool(err or said), data_find=f'{p.label} {p.note}'.lower())

def Prompts(n):
    "The instruction text of the tutor: one closed item for each prompt, the ways last."
    ps = sorted(registry().values(), key=lambda p: p.name.startswith('way.'))
    return Group('prompts', 0, extra=(
        P('A change works on the next question. To go back to the text that comes with abhyasa, click "Use the default", or save an empty box. '
          'The concept, the conversation and the reply format stay in code.', cls='mute'),
        Div(*map(PromptItem, ps), cls='prompts')))
