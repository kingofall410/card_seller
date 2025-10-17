from services import ebay
from services.models import Settings
from core.models.Card import Card
from core.models.CardSearchResult import CardSearchResult


def single_image_lookup(card: Card, all_fields = {}, settings=None, site="ebay", refine=False, scrape_sold_data=False, retry_limit=5):
    print("SIL")
    settings = settings or Settings.get_default()
    listing_matches = {}
    sold_matches = {}
    
    page = 1
    resp_count = 0
    csr=None
    while (resp_count < settings.nr_returned_listings) and (page <= retry_limit):
            
        if site == "ebay":
            listing_matches = ebay.image_search(card.get_lookup_image(), limit=settings.nr_returned_listings, page=page, settings=settings)
        
        csr = card.parse_and_tokenize_search_results(listing_matches, all_fields=all_fields, csr=csr)
        csr.filter_terms = all_fields["filter_terms"] if "filter_terms" in all_fields else ""
        search_string = csr.build_title(shorter=True) + " " + csr.filter_terms
        backup_search_string = csr.build_title(shortest=True) + " " + csr.filter_terms
        csr.set_ovr_attribute("sold_search_string", search_string, False)
        csr.set_ovr_attribute("text_search_string", search_string, False)
        csr.save()

        if refine:
            text_refinement(csr, csr.text_search_string, all_fields, settings, site, retry_limit)

        if scrape_sold_data:
            price_only(csr, search_string, backup_search_string)
            
        page += 1
        resp_count = csr.response_count

def text_refinement(csr, keyword_string = "", all_fields = {}, settings=None, site="ebay", retry_limit=5):
    print("text refine")
    settings = settings or Settings.get_default()
    listing_matches = {}
    
    page = 1
    resp_count = 0
    while (resp_count < settings.nr_returned_listings) and (page <= retry_limit):
            
        if site == "ebay":
            
            listing_matches = ebay.text_search(keyword_string, settings)
        
        csr.refine_listings(listing_matches)
        csr.save()

        filter_terms = csr.display_value("filter_terms") or ""
        search_string = csr.build_title(shorter=True) + " " + filter_terms
        backup_search_string = csr.build_title(shortest=True) + " " + filter_terms
        
        csr.set_ovr_attribute("sold_search_string", search_string, False)
        csr.set_ovr_attribute("text_search_string", search_string, False)
        csr.save()
            
        page += 1
        resp_count = csr.response_count


def retokenize(card):
    card.retokenize()

def price_only(csr, ss=None):

    filter_terms = csr.display_value("filter_terms") or ""
    search_string = csr.build_title(shorter=True) + " " + filter_terms
    backup_ss = csr.build_title(shortest=True) + " " + filter_terms
    sold_matches = ebay.scrape_with_profile(search_string, backup_ss, 4)
    csr.update_pricing(sold_matches)
    csr.save()

    search_string = csr.build_title(shorter=True, condition_sensitive=True) + " " + filter_terms
    backup_ss = csr.build_title(shortest=True, condition_sensitive=True) + " " + filter_terms
    sold_matches = ebay.scrape_with_profile(search_string, backup_ss, 4)
    csr.update_pricing(sold_matches, is_refined=True)
    csr.save()

'''
def lookup_collection(collection, settings=None, site="ebay"):
    if not settings:
        settings = Settings.get_default()
    for card in collection.cards:
        single_image_lookup(card, settings, site)'''