import json
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.conf import settings
from services.models import Settings
from services import settings_management as app_settings
from urllib.parse import unquote
from django.views.decorators.csrf import csrf_exempt

# Settings-related views

def view_settings(request):
    settings = Settings.objects.first()
    return render(request, "core_settings.html", {"settings": settings})

def update_settings(request):
    print(request.body)
    if request.method == 'POST':
        nr_returned_listings = request.POST.get('nr_returned_listings')
        nr_collection_page_items = request.POST.get('nr_collection_page_items')
        field_pct_threshold = request.POST.get('field_pct_threshold')
        ebay_user_auth_consent = request.POST.get('ebay_user_auth_consent')
        ebay_auth_code_unescaped = request.POST.get('ebay_auth_code_unescaped')
        nr_std_devs = request.POST.get('nr_std_devs')
        settings = Settings.objects.first()  # or however you fetch it
        settings.nr_returned_listings = nr_returned_listings
        settings.nr_collection_page_items = nr_collection_page_items
        settings.field_pct_threshold = field_pct_threshold
        settings.nr_std_devs = nr_std_devs
        settings.ebay_user_auth_consent = ebay_user_auth_consent
        settings.ebay_auth_code_unescaped = ebay_auth_code_unescaped
        settings.ebay_user_auth_code = unquote(ebay_auth_code_unescaped)
        settings.save()
    return redirect('settings')

@csrf_exempt
def settings_file_upload(request, file_type):
    uploaded_files = request.FILES.getlist("file")
    if not uploaded_files:
        return JsonResponse({"success": False, "error": "No files provided"})
    errors = []
    for uploaded_file in uploaded_files:
        try:
            print(request)
            base_name = uploaded_file.name
            file_type = base_name.split('.')[0]
            print(base_name, file_type)
            app_settings.load_settings_file(uploaded_file, file_type)
        except Exception as e:
            errors.append(f"{uploaded_file.name}: {str(e)}")
    if errors:
        return JsonResponse({"success": False, "error": "; ".join(errors)})
    return JsonResponse({"success": True, "error": ""})
