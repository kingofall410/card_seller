from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Min
from django.utils.timezone import now
from services.models import Brand, Subset, Team, City, KnownName, CardAttribute, Condition, Parallel, Season, CardNumber, SerialNumber
from core.models.CardSearchResult import ListingGroup
from django.db.models import F, When, Value, Case, BooleanField

from core.models.CardSearchResult import CardSearchResult
from core.models.Card import Card, Collection
from services import ebay
# Miscellaneous views

def hello_world(request):
    return render(request, "success.html")

def test_view(request):
    
    lgs = ListingGroup.objects.all()
    for lg in lgs:
        lg.save()

    return JsonResponse({"success":True})

