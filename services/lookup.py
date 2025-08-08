from services import ebay
from services.models import Settings


def single_image_lookup(card, site="ebay"):
    settings = Settings.objects.get()
    matches = {}
    if site == "ebay":
        matches = ebay.image_search(card.get_lookup_image(), limit=settings.nr_returned_listings)
    return card.parse_and_tokenize_search_results(matches)

def single_text_lookup(card, site="ebay"):
    settings = Settings.objects.get()
    matches = ebay.text_search(card.get_search_strings(), limit=settings.nr_returned_listings)
    return card.parse_and_tokenize_search_results(matches)

def lookup_collection(collection, site="ebay"):
    for card in collection.cards:
        single_image_lookup(card, site)