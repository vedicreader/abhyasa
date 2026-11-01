class Routes:
    video = '/film/{slug}/video'   # no file suffix: FastHTML serves a path that ends in .mp4 as a static file
    subs = '/film/{slug}/subs'
    card = '/film/{slug}/card'   # GET: the card of the film of a demo, or its wait
    make = '/film/{slug}/make'   # POST: start the job that draws it
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', v)
        return route
