class Routes:
    base = '/journeys'              # all walks, and the goal box
    new = '/journeys/new'           # plan a walk from a goal
    attach = '/journeys/attach'     # add a concept to a walk, from its page
    path = '/path/{jid}'            # the path
    path_step = '/path/{jid}/step'  # one change to one step: up, down, skip, known, todo, remove
    path_add = '/path/{jid}/add'    # add a topic by name
    path_split = '/path/{jid}/split'  # split a step into smaller ones
    path_drop = '/path/{jid}/drop'  # remove the walk
    one = '/j/{jid}'                # the old routes: GET redirects to `path`, and the POSTs still work for old pages
    step = '/j/{jid}/step'
    add = '/j/{jid}/add'
    split = '/j/{jid}/split'
    drop = '/j/{jid}/drop'
    walk = '/w/{jid}'               # the walk block: the plan, then the current step
    start = '/start'                # the session block starts a session: ?journey= or ?focus=
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', v)
        return route
