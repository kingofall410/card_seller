# Export-related views

import time
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from services.models import Settings
from core.models.CardSearchResult import CardSearchResult
from services import export as export_handler
from django.shortcuts import render, redirect, get_object_or_404
from core.apps import CoreConfig
from services.queue import Task
from django.apps import apps

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
    publish_dt = request.GET.get('publish_dt', None)
    print("pub, group_key", publish, group_key, publish_dt)
    
    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)
        
    csr = CardSearchResult.objects.get(id=csr_id)
    print("csr", csr, group_key)

    #if publish_dt:
    #scheduled for the future
    task = Task(name="send_email", time=time.time() + 10, callback=print("hello"), params={})

    core_config = apps.get_app_config("core")
    core_config.queue.add(task)

    success = True
    #else:
    #    success, _, _ = export_handler.export_to_ebay([csr], publish=publish, group_key=group_key)
    if success: 
        return JsonResponse({"success": success}, status=200)
    if not success:
        return JsonResponse({'error': 'Need auth', 'url':settings.ebay_user_auth_consent}, status=404)
