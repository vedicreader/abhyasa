class Routes:
    ask = '/guide/ask'             # the question and the page context in; the checked board out, as server-sent events
    warm = '/guide/warm'           # Hyper+E went down: start the backend of the guide job, with no model call
    figure = '/guide/figure'       # the bytes of a figure image in; the boxes of its labels out, found once and kept
    undo = '/guide/undo/{key}'     # POST: take away the web page that the guide saved in the vault, and its link to the concept
    voice = '/guide/voice'         # POST on=1|0: the voice of the board on or off (the setting `guide.voice`)
    say = '/guide/say'             # POST {text}: one line in the natural voice of the settings, as JSON {audio: base64 WAV, words: [s]}
    video = '/guide/video/{slug}'  # a pasted YouTube link in; the concept's explainer video out
    find = '/guide/video/{slug}/find'   # the tutor finds a video for the concept with fossick's `search_yt`
    drop = '/guide/video/{slug}/drop'   # take the concept's video away
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', v)
        return route
