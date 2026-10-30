class Routes:
    ask = '/guide/ask'             # the question and the page context in; the checked board out, as server-sent events
    figure = '/guide/figure'       # the bytes of a figure image in; the boxes of its labels out, found once and kept
    explainer = '/guide/explainer/{slug}'   # find a YouTube explainer for a concept, and file its transcript
    cues = '/guide/cues/{vid}'     # the timed transcript of a filed explainer
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', v)
        return route
