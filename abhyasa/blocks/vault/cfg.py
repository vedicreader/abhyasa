class Routes:
    doc = '/v/{shelf}/{doc_id}'
    learn = '/v/{shelf}/{doc_id}/learn'
    def of(shelf, doc_id): return f'/v/{shelf}/{doc_id}'
