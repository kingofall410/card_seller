from django.shortcuts import render
from django.http import JsonResponse
from services.models.models import Settings, Brand, Subset
from services.models.task import Task, ListingTask
from core.models.Status import StatusBase
from core.models.ListedInfo import ListedInfo
from core.models.Group import ProductGroup
from django.db.models import Case, When, Value, BooleanField, Q
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
from django.forms.models import model_to_dict

def hello_world(request):
    return render(request, "success.html")

def test_view(request):

    tasks = ListingTask.objects.filter(status=StatusBase.FAILED).filter(csr__full_name__icontains="Griffey").delete()
    tasks = ListingTask.objects.filter(status=StatusBase.PENDING).filter(csr__full_name__icontains="Griffey").delete()
    
    return JsonResponse({"success": True, "message": "Completed successfully"})


