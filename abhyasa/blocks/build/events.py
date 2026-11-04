"""The events of a builder conversation, with the names and the fields of AG-UI: `TEXT_MESSAGE_START/CONTENT/END`, `TOOL_CALL_START/ARGS/END/RESULT`,
`RUN_STARTED/FINISHED/ERROR`, `STATE_SNAPSHOT` and `CUSTOM`. The conversation keeps the events, and the pane reads them only through `fold`.
A ramabana that has `Agent.events` gives the events of a turn itself; then `Emit` only sends the stages and the data of a tool through `agent.emit`.
With an older ramabana, `Emit` makes all the events from the tool calls and the reply of a turn."""
import json, time, uuid

__all__ = ['new_id', 'Emit', 'fold']

def new_id() -> str: return uuid.uuid4().hex[:12]

class Emit:
    "Make the events of one turn, and give each to `put(event)`. With `agent` (a ramabana that gives its own events), the tool calls are its own, and a stage or data goes through `agent.emit`."
    def __init__(self, put, agent=None): self.put, self.agent = put, agent
    def ev(self, type, **kw): self.put(dict(type=type, at=time.time(), **kw))
    def text(self, role, text):
        "One whole message of `role` (`user` or `assistant`)."
        m = new_id()
        self.ev('TEXT_MESSAGE_START', messageId=m, role=role); self.ev('TEXT_MESSAGE_CONTENT', messageId=m, delta=text); self.ev('TEXT_MESSAGE_END', messageId=m)
    def tool_start(self, name, args) -> str|None:
        if self.agent is not None: return None
        t = new_id()
        self.ev('TOOL_CALL_START', toolCallId=t, toolCallName=name); self.ev('TOOL_CALL_ARGS', toolCallId=t, delta=json.dumps(args, default=str))
        return t
    def custom(self, name, value):
        if self.agent is not None: self.agent.emit(name, value)
        else: self.ev('CUSTOM', name=name, value=value)
    def stage(self, t, text): self.custom('stage', dict(toolCallId=t, text=text))
    def data(self, t, data): self.custom('data', dict(toolCallId=t, data=data))
    def tool_end(self, t, content):
        if self.agent is not None: return
        self.ev('TOOL_CALL_END', toolCallId=t); self.ev('TOOL_CALL_RESULT', toolCallId=t, content=content)
    def state(self, snapshot): self.ev('STATE_SNAPSHOT', snapshot=snapshot)

def when(e):
    "The time of event `e` in seconds: `at` from `Emit`, or `timestamp` in milliseconds from ramabana."
    return e.get('at') if e.get('at') is not None else (e['timestamp'] / 1000 if e.get('timestamp') is not None else None)

def fold(events) -> list:
    """The items of the pane from `events`, in order: `{kind: 'user'|'assistant', text}`, `{kind: 'tool', id, name, args, result, data, stages, status}`
    (status `running` or `done`), `{kind: 'run', state}` for a turn that ended with an error or a Stop, and `{kind: 'note', text}`."""
    out, msgs, tools, args, last = [], {}, {}, {}, None
    for e in events or ():
        t = e.get('type')
        if t == 'TEXT_MESSAGE_START': msgs[e['messageId']] = m = dict(kind=e.get('role') or 'assistant', text=''); out.append(m)
        elif t == 'TEXT_MESSAGE_CONTENT' and (m := msgs.get(e.get('messageId'))): m['text'] += e.get('delta') or ''
        elif t == 'TOOL_CALL_START' and not e.get('parentMessageId') in tools:   # a call of a sub-agent is not a line of its own
            tools[e['toolCallId']] = last = x = dict(kind='tool', id=e['toolCallId'], name=e.get('toolCallName') or '', args={}, result='', data=None, stages=[], status='running', start=when(e), secs=None); out.append(x)
        elif t == 'TOOL_CALL_ARGS' and (x := tools.get(e.get('toolCallId'))):
            args[x['id']] = args.get(x['id'], '') + (e.get('delta') or '')
            try: x['args'] = json.loads(args[x['id']] or '{}')
            except ValueError: pass
        elif t == 'TOOL_CALL_RESULT' and (x := tools.get(e.get('toolCallId'))):
            x.update(result=e.get('content') or '', status='done', secs=(when(e) - x['start']) if when(e) is not None and x['start'] is not None else None)
        elif t == 'CUSTOM' and e.get('name') in ('stage', 'data') and isinstance(v := e.get('value'), dict) and (x := tools.get(v.get('toolCallId')) or last):   # with no id: the call that runs
            if e.get('name') == 'stage': x['stages'].append(v.get('text') or '')
            elif e.get('name') == 'data': x['data'] = v.get('data')
        elif t == 'CUSTOM' and e.get('name') == 'note': out.append(dict(kind='note', text=str(e.get('value') or '')))
        elif t == 'RUN_ERROR': out.append(dict(kind='run', state=e.get('state') or 'failed', text=e.get('message') or 'The turn did not finish.'))
        elif t == 'RUN_FINISHED' and (st := e.get('state') or (e.get('result') or {}).get('state')) not in (None, 'done', 'complete', 'completed'):
            out.append(dict(kind='run', state=st, text=e.get('message') or f'The turn ended early ({st}).'))
    return out
