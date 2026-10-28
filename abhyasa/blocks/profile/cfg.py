class Routes:
    base = '/you'               # what abhyasa knows about you; POST saves your edits
    start = '/you/start'        # the first conversation; POST reads the answers
    undo = '/you/undo'          # put back the old value of one change
    setting = '/you/setting'    # save pace, questions in a session or new ways
    setting_default = '/you/setting/default'   # use the default of one of them
    observe = '/you/observe'    # learn from your recent answers now
    clear = '/you/clear'        # remove the profile
