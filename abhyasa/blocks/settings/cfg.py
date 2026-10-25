class Routes:
    base = '/settings'
    use = '/settings/use'            # switch the speech engine and model
    segment = '/settings/segment'    # cut at pauses, on or off
    search = '/settings/search'      # look up speech models on Hugging Face
    get = '/settings/get'            # download a model in the background, then use it
    jobs = '/settings/jobs'          # the download progress lines
    status = '/settings/status'      # the state of the model in use
    remove = '/settings/remove'      # delete a model that this page downloaded
    key = '/settings/key'            # set or clear the OpenAI key
    model = '/settings/model'        # the model for one tutor task
    test = '/settings/model/test'    # time one short call to a model
    catalog = '/settings/catalog'    # the models that can run here, for the pickers
