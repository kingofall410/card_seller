from django.shortcuts import render
from django.http import JsonResponse
from services.models import Settings

from core.models.Card import Collection, CollectionStatus
# Miscellaneous views


def hello_world(request):
    return render(request, "success.html")

def test_view(request):
    Collection.objects.update(status=CollectionStatus.IMPORTED)

    '''settings = Settings.get_default()
    collection = Collection.objects.get(id=97).cards.all()
    csrs = [card.active_search_results() for card in collection]
    for csr in csrs:
        csr.save()
    pg = ProductGroup.objects.get(id=21)
    newpg = ProductGroup.objects.get(id=18)
    for p in pg.products.all():
        p.ebay_product_group = newpg
        p.save()
    pg.delete()
    ebay.delete_inventory_group("Paul Skenes Dollar Bin", settings)
    
    
    columns = CardSearchResult.listing_spreadsheet_fields

    cards = Card.objects.filter(
        Q(search_results__ebay_listing_id__isnull=False) & ~Q(search_results__ebay_listing_id='') |
        Q(search_results__sku__isnull=False) & ~Q(search_results__sku='') |
        Q(search_results__ebay_offer_id__isnull=False) & ~Q(search_results__ebay_offer_id='') & ~Q(search_results__ebay_offer_id='None' )|
        Q(search_results__ebay_listing_datetime__isnull=False)
    ).distinct()'''





    '''rows = collection_views.spreadsheet_rows_from_search_result(cards, columns)
    
    return render(request, "spreadsheet.html", {"columns":columns, "rows":rows})'''

    '''

    collection = Collection.objects.get(id=91)
    for card in collection.cards.all():
        card.active_search_results().save()'''
    

    return JsonResponse({"success": True, "message": "Completed successfully"})


