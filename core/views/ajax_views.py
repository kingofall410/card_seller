import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from services import settings_management as app_settings

# AJAX/utility views

@csrf_exempt
def add_token(request):
    print("body", request.body)
    if request.method == 'POST':
        data = json.loads(request.body)
        field_key = data.get("field_key")
        new_value = data.get("token", "")
        allFields = data.get("fields", {})
        print(f"add_token: {field_key}: {new_value}")
        print(allFields)
        if app_settings.add_token(field_key, new_value, allFields):
            return JsonResponse({"success": True, "error": ""})
    return JsonResponse({"error": True, "error": "Failed to add token"})
