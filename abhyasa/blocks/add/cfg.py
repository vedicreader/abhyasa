class Routes:
    base = '/add'                  # GET: to the Start box in Learn; POST: Find concepts only
    start = '/learn#start'
    read = '/learn/read'           # what the Start box will do with its text
    file = '/learn/file'           # a dropped PDF, filed in the vault
    pick = '/learn/pick'           # POST: the folder chooser of this Mac; it gives the path that you pick
    vedicreader = '/add/vedicreader'
