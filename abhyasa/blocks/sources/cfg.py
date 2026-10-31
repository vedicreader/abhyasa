class Routes:
    base = '/library/sources'         # the Library tab Sources: each source that your walks read, and each folder and repo that you filed
    old = '/sources'                  # the old path: it goes to the tab (301)
    remove = '/sources/remove'        # forget each document of one folder or repo that you filed
    unfile = '/walk/unfile'           # the walk block's Undo, for one hour after Start filed a folder or a repo
    doc = '/v/{shelf}/{doc_id}'       # the vault viewer
    walk = '/w/{jid}#sources'         # the sources part of a walk page
    talk = '/t/{tid}'
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', v)
        return route
