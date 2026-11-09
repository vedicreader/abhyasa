class Routes:
    base = '/keys'          # every keyboard shortcut, by where it works
    float = '/keys/float'   # POST on=1|0: the Keys button on each page on or off (the setting `look.keys_float`)
    panel = '/keys/panel'   # GET ?path=: the Keys button and panel of the page at `path`, for a host that keeps only the page body
