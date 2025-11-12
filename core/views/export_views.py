# Export-related views

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from services.models import Settings
from core.models.CardSearchResult import CardSearchResult, ProductGroup
from services import export as export_handler
from django.shortcuts import render, redirect, get_object_or_404

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
    publish = request.GET.get('publish', False)
    group = request.GET.get('group', None)
    print("pub, group", publish, group)
    
    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)
    csr = CardSearchResult.objects.get(id=csr_id)
    group_name = ""
    if group == "-1":
        group_name = csr.display_full_name + " Bargain Bin 3 (OSBB3)"
    elif group == "-2":
        group_name = csr.full_set + " Commons"
    else:
        group_name = get_object_or_404(ProductGroup, id=group).name
    print(group_name)
    success, _, _ = export_handler.export_to_ebay([csr], publish=publish, group=group_name)
    if success: 
        return JsonResponse({"success": success}, status=200)
    if not success:
        return JsonResponse({'error': 'Need auth', 'url':settings.ebay_user_auth_consent}, status=404)
