class Routes:
    js = '/rupaka/rupaka.js'
    css = '/rupaka/rupaka.css'
    three = '/rupaka/three.js'   # rupaka loads it beside rupaka.js when a scene mounts
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
