class Routes:
    base = '/journeys'              # all journeys, and the goal box
    new = '/journeys/new'           # plan a journey from a goal
    attach = '/journeys/attach'     # add a concept to a journey, from its page
    one = '/j/{jid}'                # the path
    step = '/j/{jid}/step'          # one change to one step: up, down, skip, known, todo, remove
    add = '/j/{jid}/add'            # add a topic by name
    split = '/j/{jid}/split'        # split a step into smaller ones
    drop = '/j/{jid}/drop'          # remove the journey
    walk = '/w/{jid}'               # the walk block: the plan, then the current step
    start = '/start'                # the session block starts a session: ?journey= or ?focus=
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', v)
        return route
