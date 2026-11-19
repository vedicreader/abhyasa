class Routes:
    js = '/rupaka/rupaka.js'
    css = '/rupaka/rupaka.css'
    three = '/rupaka/three.js'   # rupaka loads it beside rupaka.js when a scene mounts
    media = '/rupaka/media/{name}'   # GET: a profile asset of a demo, '<sha256>.<ext>', from the store in the vault
    spec = '/demo/{slug}.json'
    page = '/demo/{slug}'   # GET: 301 to the Show slot of its idea, on the concept page
    ask = '/demo/ask'
    asked = '/demo/asked/{aid}'
    predict = '/demo/{slug}/predict'
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', v)
        return route
