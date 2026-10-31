class Routes:
    base = '/you'               # You → Progress: this week, your strengths, what you learned, past sessions
    one = '/you/s/{sid}'        # one past session, read only: the fold of its row loads it
    old = '/learning'           # the old Your learning: it goes to You → Progress (301)
    old_one = '/learning/{sid}' # an old link to one past session: it goes to its row on You → Progress (301)
    page = '/s/{sid}'           # the session block's page: Continue goes there
    start = '/start'            # the session block starts a session: ?journey= or ?focus=
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', v)
        return route
