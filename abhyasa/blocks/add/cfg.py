class Routes:
    base = '/add'                  # GET: to the Start box in Learn; POST: Find concepts only
    start = '/learn#start'
    read = '/learn/read'           # what the Start box will do with its text
    file = '/learn/file'           # a dropped PDF, filed in the vault
    files = '/learn/files'         # POST: several dropped files, each filed in the vault; it gives their ids
    pick = '/learn/pick'           # POST: the folder chooser of this Mac; it gives the path of each folder that you pick
    walk_source = '/learn/walk-source'   # POST: Add a source to a goal walk that exists (`jid`); GET: its filing line
