import json
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings
from services.models import Settings
from services import settings_management as app_settings
from urllib.parse import unquote
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import unquote
from django.db import models

# Settings-related views

def view_settings(request):
    settings = Settings.objects.first()
    return render(request, "core_settings.html", {"settings": settings})

def update_settings(request):
    if request.method == 'POST':
        settings = Settings.objects.first() or Settings()

        for field in Settings._meta.get_fields():
            if not isinstance(field, models.Field):
                continue

            field_name = field.name
            raw_value = request.POST.get(field_name)

            if raw_value is None or field_name == "ebay_user_auth_code":
                continue

            try:
                if isinstance(field, models.IntegerField):
                    value = int(raw_value)
                elif isinstance(field, models.FloatField):
                    value = float(raw_value)
                elif isinstance(field, models.BooleanField):
                    value = raw_value.lower() in ["true", "1", "yes", "on"]
                else:
                    value = raw_value
                setattr(settings, field_name, value)
            except (ValueError, TypeError):
                pass

        if hasattr(settings, "ebay_auth_code_unescaped") and settings.ebay_auth_code_unescaped:
            settings.ebay_user_auth_code = unquote(settings.ebay_auth_code_unescaped)

        settings.save()

        return JsonResponse({"status": "success"})


    return JsonResponse({"status": "error", "message": "Invalid request method."}, status=400)

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
