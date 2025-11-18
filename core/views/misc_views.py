from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Min
from django.utils.timezone import now
from services.models import Brand, Subset, Team, City, KnownName, CardAttribute, Condition, Parallel, Season, CardNumber, SerialNumber, Settings
from core.models.CardSearchResult import ListingGroup
from django.db.models import F, Q, When, Value, Case, BooleanField

from core.models.CardSearchResult import CardSearchResult, ProductGroup
from core.models.Card import Card, Collection
from services import ebay, export
# Miscellaneous views

from core.views import collection_views

def hello_world(request):
    return render(request, "success.html")

def test_view(request):
    settings = Settings.get_default()
    '''pg = ProductGroup.objects.get(id=21)
    newpg = ProductGroup.objects.get(id=18)
    for p in pg.products.all():
        p.ebay_product_group = newpg
        p.save()
    pg.delete()'''
    ebay.delete_inventory_group("Reggie Jackson", settings)
    
    '''
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


