class Routes:
    one = '/course/{cid}'                  # the course page: the goal, you are here, next and why, the stages, what blocks the goal, the sources
    level = '/course/{cid}/level'          # POST: write the questions of "where do you start" on the pool
    answer = '/course/{cid}/answer'        # POST: one answer, by a tap or in words
    stage = '/course/{cid}/stage/{key}'    # build the walk of a stage on the pool, then open it
    job = '/course/{cid}/job'              # the state of a pool job of the course: ?k=level, plan or a stage key
    data = '/course/{cid}/data'            # POST: keep a folder as your data, which the exercises run on
    data_drop = '/course/{cid}/data/drop'  # POST: remove one data folder
    lock = '/course/{cid}/lock'            # POST: lock a stage that is good, or unlock it (key, on)
    back = '/course/{cid}/back'            # POST: Enough: go back to the place that opened this course as a rabbit hole
    fix = '/course/{cid}/fix'              # POST: Fix the rest: plan again each stage that you did not lock or start, on the pool
    walk = '/w/{jid}'                      # the walk block: a walk
    step = '/w/{jid}/{i}'                  # the walk block: one step
    start = '/start'                       # the session block: ?focus= starts a session on one idea
    def of_(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', str(v))
        return route
