class Routes:
    attach = '/walk/attach'           # POST: add a concept to a walk, from its concept page
    path = '/path/{jid}'              # an old link to a path: the path becomes a walk, and the link goes to the walk page
    old = '/j/{jid}'                  # an older link to a path or a walk: the same
    new = '/walk/new'                 # make a walk from a vault document, a text, a topic or a link
    job = '/walk/job'                 # the state of a walk from a link or a goal while it is made
    unfile = '/walk/unfile'           # Undo: forget what Start filed for a walk
    one = '/w/{jid}'                  # the walk page: its state, its plan, its sources
    gather = '/w/{jid}/gather'        # the line of research: what it reads now, the sources, the time left; it asks again every 3 s while research runs
    gather_log = '/w/{jid}/gather/log'    # the log of the gather agent, newest first, each row with its link; it opens in the side pane
    gather_stop = '/w/{jid}/gather/stop'  # POST: stop the research of the walk: the agent and its sub-agents, or the search of each idea
    gather_again = '/w/{jid}/gather/again'  # POST: Find sources again, for each idea with no source
    status = '/walk/research.json'    # GET: the walks whose research runs now, and the walks whose research ended in the last hours, for the Mac app
    edit = '/w/{jid}/edit'            # POST: one change to the plan, kept with an Undo; GET: the old editor page, which goes to the walk page
    undo = '/w/{jid}/undo'            # POST: take back the newest change of the path
    history = '/w/{jid}/history'      # the earlier versions of the plan, for the fold on the walk page
    restore = '/w/{jid}/restore'      # POST: go back to the version before one change
    improve = '/w/{jid}/improve'      # POST: Improve the walk, from your words: start the job; GET (?key=): the pending line, then the changes to keep or skip
    improve_apply = '/w/{jid}/improve/apply'   # POST: apply the changes that you kept, as one change with an Undo
    passages = '/w/{jid}/passages'    # GET: the real passages that an idea can pick (?i=&q=, or ?name=&q= for a new idea)
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
