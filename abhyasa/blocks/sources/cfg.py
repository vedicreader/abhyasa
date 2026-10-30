class Routes:
    base = '/sources'                 # your documents: each source that your walks read, and each folder and repo that you filed
    index = '/sources/index/{what}'
    remove = '/sources/remove'        # forget each document of one folder or repo that you filed
    unfile = '/walk/unfile'           # the walk block's Undo, for one hour after Start filed a folder or a repo
    doc = '/v/{shelf}/{doc_id}'       # the vault viewer
    walk = '/w/{jid}'                 # a walk; a path is at `path`
    path = '/path/{jid}'
    talk = '/t/{tid}'
    def of(route, **kw):
        for k, v in kw.items(): route = route.replace('{' + k + '}', v)
        return route
