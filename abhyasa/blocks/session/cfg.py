class Routes:
    start = '/start'
    page = '/s/{sid}'
    answer = '/s/{sid}/answer'
    giveup = '/s/{sid}/giveup'
    hint = '/s/{sid}/hint'
    teach = '/s/{sid}/teach'
    next = '/s/{sid}/next'
    card = '/s/{sid}/card'
    ready = '/s/{sid}/ready'
    end = '/s/{sid}/end'
    def at(route, sid): return route.replace('{sid}', sid)
