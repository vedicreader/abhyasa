class Routes:
    js = '/rupaka/rupaka.js'
    css = '/rupaka/rupaka.css'
    spec = '/demo/{slug}.json'
    page = '/demo/{slug}'
    make = '/demo/make'
    ask = '/demo/ask'
    wait = '/demo/wait/{concept}'
    asked = '/demo/asked/{aid}'
    predict = '/demo/{slug}/predict'
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', v)
        return route
