class Routes:
    base = '/build'                    # GET: a new conversation
    open = '/build/open'               # GET (talk or walk): the conversation of that talk or walk, or a new one for it
    start = '/build/start'             # POST (q, sources, talk): Start or Make a talk in the Start box opens the builder with the job running
    one = '/build/{bid}'               # GET: with pane=1 the builder; else the page at the left, with the builder open in the side pane
    say = '/build/{bid}/say'           # POST (text): one request to the builder; its turn runs on the pool
    chat = '/build/{bid}/chat'         # GET: the conversation as it is now
    brief = '/build/{bid}/brief'       # POST: a change to the brief by hand
    item = '/build/{bid}/item'         # POST (url, role): Keep or Drop of one item that research found
    undo = '/build/{bid}/undo'         # POST: take back the last change of the walk or the talk
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', str(v))
        return route
