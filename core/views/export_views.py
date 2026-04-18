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

def perform_list(csr_id, publish, group_key, publish_dt=None, price=None, qty=None):
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
    core_config.queue.schedule_listing_task(name=f"list csr {csr_id}", card=csr.parent_card, csr=csr, when=publish_dt, callback=export_handler.export_to_ebay, params={"csr_id": csr_id, "publish":publish, "group_key":group_key})
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
        
    perform_list(csr_id, publish, group_key, publish_dt, price, qty)
    
    success = True
    #else:
    #    success, _, _ = export_handler.export_to_ebay(csr_id, publish=publish, group_key=group_key)
    if success: 
        return JsonResponse({"success": success}, status=200)
    if not success:
        return JsonResponse({'error': 'Need auth', 'url':settings.ebay_user_auth_consent}, status=404)

@csrf_exempt
def bulk_list(request, group_key):
    print("key", group_key)
    group = ProductGroup.objects.get(group_key=group_key)

    try:
        card_ids = request.POST.getlist('card_ids[]') 
        if len(card_ids):           
            card_list = Card.objects.filter(id__in=card_ids).order_by('id')
        else:
            card_list = []
    except json.JSONDecodeError:
        card_list = []
    
    print(card_list)
    
    start_dt = max(group.next_listing_datetime, timezone.now())
    print("start publish_dt:", start_dt)
    
    core_config = apps.get_app_config("core")
    for card in card_list:
        perform_list(card.active_search_results().id, False, group_key, publish_dt=start_dt)
        start_dt += timedelta(days=1)

    return JsonResponse({"success": True, "error": ""})