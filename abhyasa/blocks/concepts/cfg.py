class Routes:
    base = '/concepts'
    library = '/library'   # the Library tab: it opens Concepts
    one = '/c/{slug}'
    group = '/c/{slug}/group'
    move = '/c/{slug}/move'   # GET: the "Move to…" form of one row
    rename = '/c/{slug}/rename'
    sort = '/concepts/sort'
    accept = '/concepts/sort/accept'
    cancel = '/concepts/sort/cancel'
    rename_group = '/concepts/group/rename'   # GET: the form; POST: the rename
    new_group = '/concepts/group/new'   # GET: the form; POST: the new group
    back = '/concepts/undo'   # the Undo of the last change by hand
    undo = '/c/{slug}/undo'
    def of(slug): return f'/c/{slug}'
    def group_of(slug): return f'/c/{slug}/group'
    def move_of(slug): return f'/c/{slug}/move'
    def rename_of(slug): return f'/c/{slug}/rename'
    def undo_of(slug): return f'/c/{slug}/undo'
