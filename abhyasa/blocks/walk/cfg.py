class Routes:
    new = '/walk/new'                 # make a walk from a vault document, a text, a topic or a link
    job = '/walk/job'                 # the state of a walk from a link or a goal while it is made
    unfile = '/walk/unfile'           # Undo: forget what Start filed for a walk
    one = '/w/{jid}'                  # the plan before the start; then the current step
    plan = '/w/{jid}/plan'            # one change to the plan: the check of a step, or drop a step
    start = '/w/{jid}/start'          # start the walk and open a sitting
    step = '/w/{jid}/{i}'             # one idea: the passage, the figure, the note and the check
    note = '/w/{jid}/{i}/note'        # the tutor note, loaded after the page
    check = '/w/{jid}/{i}/check'      # GET: the check card, loaded after the page; POST: write the notebook of the step again
    answer = '/w/{jid}/{i}/answer'
    hint = '/w/{jid}/{i}/hint'
    giveup = '/w/{jid}/{i}/giveup'
    run = '/w/{jid}/{i}/run'          # the code check
    predict = '/w/{jid}/{i}/predict'  # a demo or order prediction
    keep = '/w/{jid}/{i}/keep'        # keep the demo state on the last prediction
    ladder = '/w/{jid}/{i}/ladder'    # the help under a demo check after a wrong prediction: a lesson in another way, or a simpler demo
    next = '/w/{jid}/{i}/next'        # skip or go on
    done = '/w/{jid}/{i}/done'        # the summary at the end of a section
    img = '/w/{jid}/{i}/img'          # the figure of the step, from the vault assets
    result = '/w/{jid}/{i}/result/{n}.png'   # one image of a run that Leela filed, from the vault assets under leela/<walk>/<step>/
    notebook = '/w/{jid}/{i}/notebook'  # download the notebook of a step that runs in Leela, for Jupyter
    data = '/w/{jid}/{i}/data'          # POST: the path of one data entry of the notebook, as the folder of your images
    leela = '/w/{jid}/{i}/leela'        # POST: Open in Leela. Note the time on the step (`leela_at`), then go to the Leela link
    source = '/w/{jid}/{i}/source'    # GET: the passage, or the line while the tutor looks for a source; POST: look for a source on the web
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', str(v))
        return route
