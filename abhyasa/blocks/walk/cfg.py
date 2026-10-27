class Routes:
    new = '/walk/new'                 # make a walk from a vault document, a text or a topic
    one = '/w/{jid}'                  # the plan before the start; then the current step
    plan = '/w/{jid}/plan'            # one change to the plan: the check of a step, or drop a step
    start = '/w/{jid}/start'          # start the walk and open a sitting
    step = '/w/{jid}/{i}'             # one idea: the passage, the figure, the note and the check
    check = '/w/{jid}/{i}/check'      # the check card, loaded after the page
    answer = '/w/{jid}/{i}/answer'
    hint = '/w/{jid}/{i}/hint'
    giveup = '/w/{jid}/{i}/giveup'
    run = '/w/{jid}/{i}/run'          # the code check
    predict = '/w/{jid}/{i}/predict'  # a demo or order prediction
    keep = '/w/{jid}/{i}/keep'        # keep the demo state on the last prediction
    next = '/w/{jid}/{i}/next'        # skip or go on
    done = '/w/{jid}/{i}/done'        # the summary at the end of a section
    img = '/w/{jid}/{i}/img'          # the figure of the step, from the vault assets
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', str(v))
        return route
