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
import django.utils.timezone as timezone

def hello_world(request):
    return render(request, "success.html")

def test_view(request):

    tasks = ListingTask.objects.filter(scheduled_for__gt=timezone.now())
    new_group = ProductGroup.objects.get(id="90")
    #tasks = ListingTask.objects.filter(csr_id=3655)
    for task in tasks:
        if task.params()["group_key"] == "77" or task.params()["group_key"] == "90":
            task.update_params("group_key", "90")
            task.csr.ebay_product_group = new_group
            task.csr.save()
            task.save()
            
    
    return JsonResponse({"success": True, "message": "Completed successfully"})


