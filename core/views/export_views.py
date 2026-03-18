# Export-related views

from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from services.models.models import Settings
from core.models.CardSearchResult import CardSearchResult
from services import export as export_handler
from django.shortcuts import render, redirect, get_object_or_404
from core.apps import CoreConfig
from services.queue_service import Task
from django.apps import apps
from django.utils import timezone

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
        
    csr = CardSearchResult.objects.get(id=csr_id)
    print("csr", csr, group_key)
    listed_info = csr.parent_card.listed_card_info
    listed_info.list_price = price
    listed_info.list_qty = qty
    listed_info.save()
    #if publish_dt:
    #scheduled for the future
    core_config = apps.get_app_config("core")
    core_config.queue.schedule_listing_task(name=f"list csr {csr_id}", card=csr.parent_card, csr=csr, when=publish_dt, callback=export_handler.export_to_ebay, params={"csr_id": csr_id, "publish":publish, "group_key":group_key})

    success = True
    #else:
    #    success, _, _ = export_handler.export_to_ebay(csr_id, publish=publish, group_key=group_key)
    if success: 
        return JsonResponse({"success": success}, status=200)
    if not success:
        return JsonResponse({'error': 'Need auth', 'url':settings.ebay_user_auth_consent}, status=404)
