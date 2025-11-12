from services import ebay, psa
from services.models import Settings
from core.models.Card import Card
from core.models.CardSearchResult import CardSearchResult
from core.models.Status import StatusBase


def single_image_lookup(card: Card, all_fields = {}, settings=None, sites=["ebay"], refine=False, scrape_sold_data=False, retry_limit=5, result_count_max=50, csr=None):
    print("SIL")
    settings = settings or Settings.get_default()
    listing_matches = {}
    sold_matches = {}
    
    page = 1
    resp_count = 0
    
    while (resp_count < result_count_max) and (page <= retry_limit):
        
        if "psa" in sites:
            #TODO: ultimately this is backwards, my lookup modules need to be unifying to Card, not vice versa
            psa_record = psa.scan_and_lookup(card.get_lookup_image())
            csr = card.parse_psa_record(psa_record)
        elif "ebay" in sites:
            listing_matches = ebay.image_search(card.get_lookup_image(), limit=result_count_max, page=page, settings=settings)
        
        csr = card.parse_and_tokenize_search_results(listing_matches, all_fields=all_fields, csr=csr, id_listings=True)

        csr.id_status = StatusBase.AUTO
        csr.filter_terms = all_fields["filter_terms"] if "filter_terms" in all_fields else ""
        search_string = csr.build_title(shorter=True) + " " + csr.filter_terms
        backup_search_string = csr.build_title(shortest=True) + " " + csr.filter_terms
        csr.set_ovr_attribute("sold_search_string", search_string, False)
        csr.set_ovr_attribute("text_search_string", search_string, False)
        
        csr.save()

        if refine:
            text_refinement(csr, csr.text_search_string, all_fields, settings, site=sites[0], retry_limit=retry_limit)
            csr.refinement_status = StatusBase.AUTO
        else:
            csr.refinement_status = StatusBase.UNEXECUTED

        if scrape_sold_data:
            price_only(csr, settings)
            csr.pricing_status = StatusBase.AUTO
        else:
            csr.pricing_status = StatusBase.UNEXECUTED
            
        page += 1
        resp_count = result_count_max
    
    return csr

def text_refinement(csr, keyword_string = "", all_fields = {}, settings=None, site="ebay", retry_limit=5):
    print("text refine", keyword_string)
    settings = settings or Settings.get_default()
    
    filter_terms = csr.display_value("filter_terms") or ""
    filter_terms = "" if filter_terms == "-" else filter_terms
    id_string = csr.build_title(shorter=True)
    wide_id_string = csr.build_title(shortest=True)
    search_string = id_string + " " + filter_terms
    backup_ss = wide_id_string + " " + filter_terms

    #TODO: Update these to operate on the grouop itself
    text_group = csr.create_listing_group(label="text", filter_terms=filter_terms, id_string=id_string)
    text_wide_group = csr.create_listing_group(label="text wide", is_wide=True, filter_terms=filter_terms, id_string=wide_id_string)
    keyword_strings = [(search_string, text_group), (backup_ss, text_wide_group)]

    if csr.condition and csr.condition != " ":
        condition_id = csr.build_title(shorter=True, condition_sensitive=True)
        backup_condition_id = csr.build_title(shortest=True, condition_sensitive=True)
        condition_ss = condition_id + " " + filter_terms
        backup_condition_ss = backup_condition_id + " " + filter_terms

        condition_group = csr.create_listing_group(label="text refined", is_refined=True, filter_terms=filter_terms, id_string=condition_id)
        condition_wide_group = csr.create_listing_group(label="text wide refined", is_wide=True, is_refined=True, filter_terms=filter_terms, id_string=backup_condition_id)

        keyword_strings.append((condition_ss, condition_group))
        keyword_strings.append((backup_condition_ss, condition_wide_group))
    
    nr_pages = int(settings.price_listings/50)+1

    #matches map is keyword_string --> (listing variable, [listings])
    matches_map = ebay.text_search(keyword_strings, settings, limit=settings.price_listings)
    csr.update_listings(matches_map)
    #csr.set_ovr_attribute("sold_search_string", search_string, False)
    #csr.set_ovr_attribute("text_search_string", search_string, False)
    csr.refinement_status = StatusBase.MANUAL#default to manual status here, it's overridden during initial import
    csr.save()
        

def retokenize(card):
    card.retokenize()

def price_only(csr, settings, ss=None):
    
    filter_terms = csr.display_value("filter_terms") or ""
    filter_terms = "" if filter_terms == "-" else filter_terms
    id_string = csr.build_title(shorter=True)
    wide_id_string = csr.build_title(shortest=True)
    search_string = id_string + " " + filter_terms
    backup_ss = wide_id_string + " " + filter_terms

    #TODO: Update these to operate on the grouop itself
    sold_group = csr.create_listing_group(label="sold", is_sold=True, filter_terms=filter_terms, id_string=id_string)
    sold_wide_group = csr.create_listing_group(label="sold wide", is_sold=True, is_wide=True, filter_terms=filter_terms, id_string=wide_id_string)
    
    keyword_strings = [(search_string, sold_group), (backup_ss, sold_wide_group)]

    if csr.condition and csr.condition != " ":
        condition_id = csr.build_title(shorter=True, condition_sensitive=True)
        backup_condition_id = csr.build_title(shortest=True, condition_sensitive=True)
        condition_ss = condition_id + " " + filter_terms
        backup_condition_ss = backup_condition_id + " " + filter_terms

        condition_group = csr.create_listing_group(label="sold refined", is_sold=True, is_refined=True, filter_terms=filter_terms, id_string=condition_id)
        condition_wide_group = csr.create_listing_group(label="sold wide refined", is_sold=True, is_wide=True, is_refined=True, filter_terms=filter_terms, id_string=backup_condition_id)

        keyword_strings.append((condition_ss, condition_group))
        keyword_strings.append((backup_condition_ss, condition_wide_group))
    
    nr_pages = int(settings.price_listings/50)+1

    #matches map is keyword_string --> (listing variable, [listings])
    matches_map = ebay.scrape_with_profile(keyword_strings, limit=settings.price_listings, max_pages=nr_pages)
    csr.update_listings(matches_map)
    csr.pricing_status = StatusBase.MANUAL#default to manual status here, it's overridden during initial import
    csr.save()
    