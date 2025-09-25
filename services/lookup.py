from services import ebay
from services.models import Settings
from core.models.Card import Card


def single_image_lookup(card: Card, all_fields = {}, settings=None, site="ebay", retry_limit=5):
    settings = settings or Settings.get_default()
    matches = {}
    
    page = 1
    resp_count = 0
    csr=None
    while (resp_count < settings.nr_returned_listings) and (page <= retry_limit):
            
        if site == "ebay":
            matches = ebay.image_search(card.get_lookup_image(), limit=settings.nr_returned_listings, page=page, settings=settings)
    
        csr = card.parse_and_tokenize_search_results(matches, all_fields=all_fields, csr=csr)
        page += 1
        resp_count = csr.response_count
        
def retokenize(card):
    card.retokenize()

'''
def lookup_collection(collection, settings=None, site="ebay"):
    if not settings:
        settings = Settings.get_default()
    for card in collection.cards:
        single_image_lookup(card, settings, site)'''