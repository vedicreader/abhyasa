class Routes:
    stt = '/voice/stt'                 # one clip in, its text out
    start = '/voice/start'             # open a dictation; returns its id
    seg = '/voice/seg/{did}'           # one segment of a dictation, with its number
    stop = '/voice/stop/{did}'         # no more segments after `n`
    events = '/voice/events/{did}'     # the text of each segment, in order, as server-sent events
