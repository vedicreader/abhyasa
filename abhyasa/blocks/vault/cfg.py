from urllib.parse import quote

class Routes:
    doc = '/v/{shelf}/{doc_id}'
    learn = '/v/{shelf}/{doc_id}/learn'
    img = '/v/{shelf}/{doc_id}/img'   # an image of the document, from its assets folder: `?f=<link>` (in the query, as fast_app serves a path that ends in .png)
    def of(shelf, doc_id): return f'/v/{shelf}/{doc_id}'
    def img_of(shelf, doc_id, link): return f'/v/{shelf}/{doc_id}/img?f={quote(link, safe="/")}'
