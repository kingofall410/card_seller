# Export-related views

from datetime import datetime, timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from services.models.models import Settings
from core.models.CardSearchResult import CardSearchResult
from core.models.Card import Card
from core.models.Status import StatusBase
from services import export as export_handler
from django.shortcuts import render, redirect, get_object_or_404
from core.apps import CoreConfig
from services.queue_service import Task
from django.apps import apps
from django.utils import timezone
from core.models.Group import ProductGroup
from core.models.ListingSpread import ListingSpread

@csrf_exempt
def export_card(request, csr_id):
    settings = Settings.get_default()
    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)
    csr = CardSearchResult.objects.get(id=csr_id)
    success = export_handler.export_zip([csr])
    if not success:
        return JsonResponse({'error': 'Need auth', 'url':settings.ebay_user_auth_consent}, status=404)
    return success

def perform_list(csr_id, publish, group_key, publish_dt=None, price=None, qty=None, priority=0, predecessor=None):
    csr = CardSearchResult.objects.get(id=csr_id)
    print("csr", csr, group_key)
    group = ProductGroup.objects.filter(group_key=group_key).first()

    listed_info = csr.parent_card.listed_card_info

    print("supplied publish_dt:", publish_dt)
    price = price or listed_info.list_price
    qty = qty or 1
    
    listed_info.list_price = price
    listed_info.list_qty = qty
    listed_info.save()
    
    core_config = apps.get_app_config("core")
    core_config.queue.schedule_listing_task(name=f"list csr {csr_id}", card=csr.parent_card, csr=csr, when=publish_dt, callback=export_handler.export_to_ebay, params={"csr_id": csr_id, "publish":publish, "group_key":group_key}, priority=priority, predecessor=predecessor)
    csr.overall_status = StatusBase.STAGED if csr.overall_status == StatusBase.PENDING else csr.overall_status
    csr.save()
    if group and csr.overall_status == StatusBase.STAGED: 
        group.add_to_product_group_internal(csr)
        group.save()

@csrf_exempt
def list_card(request, csr_id):
    
    settings = Settings.get_default()
    publish = request.GET.get('publish', True)
    group_key = request.GET.get('group_key', None)
    dt_string = request.GET.get('schedule', None)
    publish_dt = timezone.make_aware(datetime.fromisoformat(dt_string))
    price = float(request.GET.get('price', 0))
    qty = int(request.GET.get('qty', 1))
    print("pub, group_key", publish, group_key, publish_dt, price, qty)
    
    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)
        
    perform_list(csr_id, publish, group_key, publish_dt, price, qty, priority=1)
    
    success = True
    #else:
    #    success, _, _ = export_handler.export_to_ebay(csr_id, publish=publish, group_key=group_key)
    if success: 
        return JsonResponse({"success": success}, status=200)
    if not success:
        return JsonResponse({'error': 'Need auth', 'url':settings.ebay_user_auth_consent}, status=404)

@csrf_exempt
def bulk_list(request, group_key=None):
    print("key", group_key)
    group = None
    if group_key != -1 and group_key != '-1':
        group = ProductGroup.objects.filter(group_key=group_key).last()
    else:
        group_key = None

    print("key and peele", group_key, group)
    try:
        card_ids = request.POST.getlist('card_ids[]') 
        if len(card_ids):           
            card_list = Card.objects.filter(id__in=card_ids).order_by('id')
        else:
            card_list = []
    except json.JSONDecodeError:
        card_list = []
    
    print(card_list)
    spread = request.POST.get('spread', 0)
    start_dt_string = request.POST.get('start_dt')
    start_dt = timezone.make_aware(datetime.fromisoformat(start_dt_string)) if start_dt_string else timezone.now()
    if group and not start_dt_string:
        start_dt = max(group.next_listing_datetime, timezone.now())
    print("start publish_dt:", start_dt, " spread:",spread)
    
    core_config = apps.get_app_config("core")
    
    cards_per_day = len(card_list)
    if spread == ListingSpread.DAILY_10X:
        cards_per_day = 10
    elif spread == ListingSpread.DAILY_2X:
        cards_per_day = 2
    elif spread == ListingSpread.DAILY or spread == ListingSpread.WEEKLY:
        cards_per_day = 1

    day_increment = 1
    if spread == ListingSpread.WEEKLY:
        day_increment = 7
    
    card_index = 0
    pub_date = start_dt
    blt,mblt = (None,None)
    while card_index < len(card_list):
        
        print("Process listing batch starting: ", card_index, " CPD: ",cards_per_day) 
        end_index = min(card_index + cards_per_day, len(card_list))

        csrs = [card.active_search_results for card in card_list[card_index:end_index]]
        csr_ids = [csr.id for csr in csrs]

        if cards_per_day > 1:
            #create a bulk listing task as needed
            group_name = csrs[0].ebay_product_group.group_title if hasattr(csrs[0], "ebay_product_group") and csrs[0].ebay_product_group else None
            blt,mblt = core_config.queue.prepare_bulk_listing_task(f"Bulk list {len(csr_ids)} --> {group_key}", when=pub_date, callback=export_handler.export_to_ebay, params={"csr_ids": csr_ids, "publish":True, "group_key":group_key})

        for csr in csrs:
            perform_list(csr.id, True, group_key, publish_dt=pub_date, predecessor=blt)

        #schedule the bulk task so everything can run as required
        if mblt:
            core_config.queue.enqueue_bulk_listing_task(mblt, blt)
        
        card_index += cards_per_day
        pub_date += timedelta(days=1)

    return JsonResponse({"success": True, "error": ""})