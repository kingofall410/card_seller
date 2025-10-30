from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Min
from django.utils.timezone import now
from services.models import Brand, Subset, Team, City, KnownName, CardAttribute, Condition, Parallel, Season, CardNumber, SerialNumber
from core.models.CardSearchResult import ListingGroup
from django.db.models import F, When, Value, Case, BooleanField

from core.models.CardSearchResult import CardSearchResult, ProductGroup
from core.models.Card import Card, Collection
from services import ebay
# Miscellaneous views

def hello_world(request):
    return render(request, "success.html")

def test_view(request):
    
    pgs = ProductGroup.objects.all()
    for pg in pgs:
        for product in pg.products.all():
            product.ebay_product_group = None
            product.save()
    pgs.delete()




    '''collection = Collection.objects.get(id=91)
    for card in collection.cards.all():
        card.active_search_results().save()'''
    

    return JsonResponse({"success": True, "message": "Completed successfully"})


