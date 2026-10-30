class Routes:
    ask = '/guide/ask'             # the question and the page context in; the checked board out, as server-sent events
    figure = '/guide/figure'       # the bytes of a figure image in; the boxes of its labels out, found once and kept
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', v)
        return route
