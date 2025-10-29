# Export-related views

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from services.models import Settings
from core.models.CardSearchResult import CardSearchResult
from services import export as export_handler

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
    group = request.GET.get('group', False)
    print("pub", publish)
    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)
    csr = CardSearchResult.objects.get(id=csr_id)
    success, _, _ = export_handler.export_to_ebay([csr], publish=publish, group=group)
    if success: 
        return JsonResponse({"success": success}, status=200)
    if not success:
        return JsonResponse({'error': 'Need auth', 'url':settings.ebay_user_auth_consent}, status=404)
