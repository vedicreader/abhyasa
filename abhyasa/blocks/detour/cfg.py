class Routes:
    open = '/rh/open'                # make a side walk for one idea and give its first step: POST slug, at, how
    term = '/rh/term'                # the offer for a selected term: GET finds it on the shelf, POST adds it as a gap
    back = '/rh/back/{sid}'          # keep the result of a side walk on the step that opened it, then go to that step
    step = '/w/{jid}/{i}'            # the walk block's step page, by value: this block does not import the walk block
    walk = '/w/{jid}'                # the walk block's plan or current step
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', str(v))
        return route
