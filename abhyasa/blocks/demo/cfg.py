class Routes:
    js = '/rupaka/rupaka.js'
    css = '/rupaka/rupaka.css'
    spec = '/demo/{slug}.json'
    page = '/demo/{slug}'
    make = '/demo/make'
    wait = '/demo/wait/{concept}'
    predict = '/demo/{slug}/predict'
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', v)
        return route
