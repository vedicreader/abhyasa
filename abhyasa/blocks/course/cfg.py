class Routes:
    one = '/course/{cid}'                  # the course page: the goal, you are here, next and why, the stages, what blocks the goal, the sources
    level = '/course/{cid}/level'          # POST: write the questions of "where do you start" on the pool
    answer = '/course/{cid}/answer'        # POST: one answer, by a tap or in words
    stage = '/course/{cid}/stage/{key}'    # build the walk of a stage on the pool, then open it
    job = '/course/{cid}/job'              # the state of a pool job of the course: ?k=level, plan or a stage key
    walk = '/w/{jid}'                      # the walk block: a walk
    step = '/w/{jid}/{i}'                  # the walk block: one step
    start = '/start'                       # the session block: ?focus= starts a session on one idea
    def of_(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', str(v))
        return route
