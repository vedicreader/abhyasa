class Routes:
    chip = '/activity'                 # GET: the inside of the activity chip, as it is now
    seen = '/activity/seen'            # POST: Clear: mark each ended job in the chip as seen
    events = '/events'                 # GET: one event stream while a job runs; each event names a job and its object
    data = '/jobs.json'                # GET: each running job and each job that ended in the last hours, for the Mac app
    research = '/walk/research.json'   # GET: the research rows in the old shape, for a Mac app of 0.0.15 and older (one release)
