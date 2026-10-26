class Routes:
    base = '/learning'          # your learning: this week, what you learned, past sessions
    one = '/learning/{sid}'     # one past session, read only
    page = '/s/{sid}'           # the session block's page: Continue goes there
    start = '/start'            # the session block starts a session: ?journey= or ?focus=
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', v)
        return route
