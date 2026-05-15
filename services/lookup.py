from services import ebay, psa
from services.models.models import Settings
from core.models.Card import Card
from core.models.ListingGroup import ListingGroup
from core.models.CardSearchResult import CardSearchResult
from core.models.Status import StatusBase
from core.models.ListedInfo import ListedInfo

def single_image_lookup(card: Card, all_fields = {}, settings=None, sites=["ebay"], refine=False, scrape_sold_data=False, retry_limit=5, result_count_max=5, csr=None):
    print("SIL")
    settings = settings or Settings.get_default()
    listing_matches = {}
    sold_matches = {}
    
    page = 1
    resp_count = 0
    
    while (resp_count < result_count_max) and (page <= retry_limit):
        
        if "psa" in sites:
            #TODO: ultimately this is backwards, my lookup modules need to be unifying to Card, not vice versa
            psa_record = psa.scan_and_lookup(card.get_lookup_image().path)
            print("jim", psa_record)
            csr = card.parse_psa_record(psa_record)
        elif "ebay" in sites:
            listing_matches = ebay.image_search(card.get_lookup_image(), limit=5, page=page, settings=settings)
            csr = card.parse_and_tokenize_search_results(listing_matches, all_fields=all_fields, csr=csr, id_listings=True)

        csr.filter_terms = all_fields["filter_terms"] if "filter_terms" in all_fields else ""
        '''search_string = csr.build_title(shorter=True) + " " + csr.filter_terms
        backup_search_string = csr.build_title(shortest=True) + " " + csr.filter_terms
        csr.set_ovr_attribute("sold_search_string", search_string, False)
        csr.set_ovr_attribute("text_search_string", search_string, False)'''
        
        csr.save()

        if refine:
            text_refinement(csr, csr.text_search_string, all_fields, settings, site=sites[0], retry_limit=retry_limit)

        if scrape_sold_data:
            price_only(csr.id, settings.id)
            
        page += 1
        resp_count = result_count_max
    
    return csr

def text_refinement(csr, keyword_string = "", all_fields = {}, settings=None, site="ebay", retry_limit=5):
    print("text refine", keyword_string)
    '''settings = settings or Settings.get_default()
    
    filter_terms = csr.display_value("filter_terms") or ""
    filter_terms = "" if filter_terms == "-" else filter_terms
    id_string = csr.build_title(shorter=True)
    wide_id_string = csr.build_title(shortest=True)
    search_string = id_string + " " + filter_terms
    backup_ss = wide_id_string + " " + filter_terms

    #TODO: Update these to operate on the grouop itself
    text_group = csr.create_listing_group(label="Active Listings", filter_terms=filter_terms, id_string=id_string)
    text_wide_group = csr.create_listing_group(label="Active Listings (wide)", is_wide=True, filter_terms=filter_terms, id_string=wide_id_string)
    keyword_strings = [(search_string, text_group), (backup_ss, text_wide_group)]

    if csr.condition and csr.condition != " ":
        condition_id = csr.build_title(shorter=True, condition_sensitive=True)
        backup_condition_id = csr.build_title(shortest=True, condition_sensitive=True)
        condition_ss = condition_id + " " + filter_terms
        backup_condition_ss = backup_condition_id + " " + filter_terms

        condition_group = csr.create_listing_group(label="Refined Active Listings", is_refined=True, filter_terms=filter_terms, id_string=condition_id)
        condition_wide_group = csr.create_listing_group(label="Refined Active Listings (wide)", is_wide=True, is_refined=True, filter_terms=filter_terms, id_string=backup_condition_id)

        keyword_strings.append((condition_ss, condition_group))
        keyword_strings.append((backup_condition_ss, condition_wide_group))
    
    nr_pages = int(settings.price_listings/50)+1

    #matches map is keyword_string --> (listing variable, [listings])
    matches_map = ebay.text_search(keyword_strings, settings, limit=settings.price_listings)
    csr.update_listings(matches_map)
    #csr.set_ovr_attribute("sold_search_string", search_string, False)
    #csr.set_ovr_attribute("text_search_string", search_string, False)
    csr.save()'''
        

def retokenize(card):
    card.retokenize()

#helper function for tasks, could be cleaned up better
def price_only_card(card_id, settings_id, ss=None):
    csr_id = Card.objects.get(id=card_id).active_search_results.id
    price_only(csr_id, settings_id, ss)
    return True

def refresh_listing_groups(listing_groups=None, lg_ids=None):
    avail_keyword_strings = []
    sold_keyword_strings = []
    matches_map = {}
    print("refresh", listing_groups, lg_ids)
    #IDs take precedence over objects passed in
    if lg_ids:
        listing_groups = ListingGroup.objects.filter(id__in=lg_ids)
    
    csr = listing_groups[0].search_result
    id_string = csr.build_search_string()

    for listing_group in listing_groups:
        if listing_group.is_img:
            #handle is_img right away just go do it as we only have one
            listing_matches = ebay.image_search(csr.parent_card.get_lookup_image(), limit=50, page=1, settings=Settings.get_default())
            csr.update_listings({"": (listing_group, listing_matches)})
        elif listing_group.is_sold:
            sold_keyword_strings.insert(0, (listing_group.get_search_string(id_string), listing_group))
        else:
            avail_keyword_strings.insert(0, (listing_group.get_search_string(id_string), listing_group))
            
    if sold_keyword_strings:
        #matches map is keyword_string --> (listing variable, [listings])
        matches_map = ebay.scrape_with_profile(sold_keyword_strings, limit=50)
        csr.update_listings(matches_map)

    if avail_keyword_strings:
        matches_map = ebay.text_search(avail_keyword_strings, limit=50, settings=Settings.get_default())
        csr.update_listings(matches_map)
        
    return matches_map


def price_only(csr_id, settings_id, ss=None):
    csr = CardSearchResult.objects.get(id=csr_id)
    settings = Settings.objects.get(id=settings_id)

    
    csr.reset_listing_groups()
    csr.save()

    listing_groups = csr.listing_groups.filter(is_img=False)
    matches_map = refresh_listing_groups(listing_groups=listing_groups)   
    psa_count = sum(group[0].listings.count() for group in matches_map.values() if 'PSA' in group[0].label)
     
    csr.overall_status = StatusBase.PRICED
    csr.save()

def bulk_order_update(card_list, listing_ids, settings=None):
    for card in card_list:
        csr = card.active_search_results
        
        if hasattr(card, "listed_card_info"):
            listing_info = card.listed_card_info
        else:
            listing_info = ListedInfo.create_from_csr(csr)
        
        offer_id = listing_info.offer_id
        token = None
        if offer_id:
            listing_status, token = ebay.get_offer_status(offer_id, settings, listing_info, token)
        
    
    ebay.bulk_order_update(listing_ids, settings or Settings.get_default())

    for card in card_list:
        card.active_search_results.save()

'''def update_from_listing(card_list, settings):
    for card in card_list:
        csr = card.active_search_results
        offer_id = csr.parent_card.listed_card_info.offer_id
        listing_info = card.listed_subcard_info

        listing_status, token = ebay.get_offer_status(offer_id, settings, listing_info)    
    #ebay.get_inventory_item(csr.parent_card.listed_card_info.sku, settings)
    listing_status, token = ebay.get_offer_status(offer_id, settings, listing_info)
    if (listing_status.listing_status == StatusBase.SOLD):
        ebay.get_sale_details(listing_info.listing_id, settings, listing_status, token)
    csr.save()'''

    