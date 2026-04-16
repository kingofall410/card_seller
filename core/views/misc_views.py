from django.shortcuts import render
from django.http import JsonResponse
from services.models.models import Settings, Brand
from services.models.task import Task, ListingTask
from core.models.Status import StatusBase
from core.models.ListedInfo import ListedInfo
from core.models.Group import ProductGroup
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from core.models.Card import Collection, CollectionStatus
from core.models.Group import ProductGroup
from core.models.CardSearchResult import CardSearchResult, ListingGroup
from core.models.Card import Card
# Miscellaneous views
from django.apps import apps
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
import re, json

def hello_world(request):
    return render(request, "success.html")

def test_view(request):

    # Use prefetch_related to grab all nested data in 2-3 queries instead of hundreds
    results = CardSearchResult.objects.filter(~Q(overall_status='pending'))
    print(results.count())
    '''for card in cards:
        # Assuming active_search_results() returns a queryset or object
        # This loop now uses the data already in memory
        for listing_group in card.active_search_results().listing_groups.all():
            listing_group.save()


            
    collections = Collection.objects.filter(id__in=[155])
    for collection in collections:
        for card in collection.cards.all():
            csr = card.active_search_results()
            if csr:
                lci = ListedInfo.create_from_csr(csr)
            else:
                lci = ListedInfo.create_from_card(card)  
    csr = card.active_search_results()
    for listing_group in csr.listing_groups.all():
        listing_group.save()

    for csr in csrs:
        if not csr.listing_tasks.exists() or not csr.listing_tasks.last()==StatusBase.PENDING:
            csr.overall_status = StatusBase.PRICED
            csr.save()
        

    #core_config.queue.reset()
    li = ListedInfo.objects.get(id=1057)
    csr = li.card.active_search_results()

    li.product_group = csr.ebay_product_group
    li.list_qty = 1
    li.listing_id = csr.ebay_listing_id 
    #self.sku = csr.sku
    li.offer_id = csr.ebay_offer_id
    li.save()
    cards = Card.objects.filter(id__gt=2253).filter(id__lt=2491).delete()
    collections = Collection.objects.filter(id__in=[131])
    for collection in collections:
        for card in collection.cards.all():
            csr = card.active_search_results()
            if csr:
                lci = ListedInfo.create_from_csr(csr)
            else:
                lci = ListedInfo.create_from_card(card)  
    cards = Card.objects.filter(id__gt=2587).filter(id__lt=2605).delete()
    ListedInfo.objects.all().delete()

    collections = Collection.objects.filter(id__in=[132,133])
    for collection in collections:
        for card in collection.cards.all():
            csr = card.active_search_results()
            if csr:
                lci = ListedInfo.create_from_csr(csr)
            else:
                lci = ListedInfo.create_from_card(card)  

    collections = Collection.objects.all() 
    for collection in collections:
        for card in collection.cards.all():
            csr = card.active_search_results()
            if csr and csr.overall_status == StatusBase.LISTED:
                listed_card_info = ListedInfo.create(csr)'''

    #core_config = apps.get_app_config("core")
    #core_config.queue.reset()
    '''lasks = Task.objects.filter(status=StatusBase.PENDING)
    for lt in lasks:
        csr = lt.listingtask.csr
        csr.overall_status = StatusBase.PENDING
        csr.save()'''
    
    
    
    
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


