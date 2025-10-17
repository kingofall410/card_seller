from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Min
from django.utils.timezone import now
from services.models import Brand, Subset, Team, City, KnownName, CardAttribute, Condition, Parallel, Season, CardNumber, SerialNumber
from django.db.models import F, When, Value, Case, BooleanField

from core.models.CardSearchResult import CardSearchResult
from core.models.Card import Card, Collection
from services import ebay
# Miscellaneous views

def hello_world(request):
    return render(request, "success.html")

def test_view(request):
    
    cards = Collection.objects.get(id=86).cards.all()
    #cards = Card.objects.all().order_by('-id')[:200]
    display_fields = CardSearchResult.spreadsheet_fields
    print("done")
    return render(request, "spreadsheet.html", {"cards":cards, "columns":display_fields})

    


    return JsonResponse({"success":True})

