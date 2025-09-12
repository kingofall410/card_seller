from services import ebay
from services.models import Settings


def single_image_lookup(card, settings=None, site="ebay"):
    settings = settings or Settings.get_default()
    matches = {}
    if site == "ebay":
        matches = ebay.image_search(card.get_lookup_image(), limit=settings.nr_returned_listings, settings=settings)
    return card.parse_and_tokenize_search_results(matches)

def single_text_lookup(card, settings=None, site="ebay"):
    settings = settings or Settings.get_default()
    matches = ebay.text_search(card.get_search_strings(), limit=settings.nr_returned_listings)
    return card.parse_and_tokenize_search_results(matches)

def retokenize(card):
    card.retokenize()

'''
def lookup_collection(collection, settings=None, site="ebay"):
    if not settings:
        settings = Settings.get_default()
    for card in collection.cards:
        single_image_lookup(card, settings, site)'''