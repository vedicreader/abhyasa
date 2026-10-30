class Routes:
    new = '/talk/new'                  # make a talk from a walk, on the pool
    journey = '/talk/journey'          # make a talk from a path (a walk with no source), on the pool
    job = '/talk/job'                  # the state of the talk while it is made
    one = '/t/{tid}'                   # the editor: the slides of the talk
    slide = '/t/{tid}/slide'           # one change to one slide; it saves at once, with an Undo
    undo = '/t/{tid}/undo'             # take back the newest change
    history = '/t/{tid}/history'       # the earlier versions of the talk
    restore = '/t/{tid}/restore'       # go back to the version before one change
    slot = '/t/{tid}/slot'             # the minutes of the slot, and room phones
    fill = '/t/{tid}/fill'             # write the points and the notes of the slides that have none, on the pool
    start = '/t/{tid}/start'           # start a run (Task 6)
    present = '/t/{tid}/present'       # the presenter window (Task 6)
    audience = '/t/{tid}/audience'     # the audience window (Task 6)
    at = '/t/{tid}/at'                 # the place of the run (Task 6)
    ask = '/t/{tid}/ask'               # a question for the room (Task 6)
    img = '/t/{tid}/img/{h}'           # an image of the public deck (Task 6)
    beside = '/t/{tid}/beside'         # a primer beside a slide (Task 7)
    end = '/t/{tid}/end'               # end the run (Task 7)
    after = '/t/{tid}/after'           # after the talk (Task 7)
    recap = '/t/{tid}/recap.html'      # the recap file for the room (Task 7)
    follow = '/t/{tid}/follow'         # walk the weak ideas after the talk (Task 7)
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', str(v))
        return route
