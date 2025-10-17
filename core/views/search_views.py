import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from services import lookup
from core.models.Card import Card, Collection
from core.models.CardSearchResult import CardSearchResult
from services.models import Brand, Subset, KnownName, Team, City, CardAttribute, Condition, Parallel, Settings
from django.db.models import F

# Search-related views

def get_dynamic_options(request):
    # ...existing code for get_dynamic_options...
    pass

@csrf_exempt
def image_search(request, card_id):
    print("image_searchy", request.body)
    if not card_id:
        return JsonResponse({'error': 'Card ID is required'}, status=400)
    card = Card.objects.get(id=card_id)
    if request.body:
        data = json.loads(request.body)
        if data:
            all_fields = data.get('required_words', {})
        
    settings = Settings.get_default()
    search_results = lookup.single_image_lookup(card, all_fields, settings, refine=False, scrape_sold_data=False)
    if search_results:
        return JsonResponse({"success": True, "error": ""})
    return JsonResponse({"error": True, "error": "No results"})

@csrf_exempt
def image_search_collection(request, collection_id):
    print("image_search")
    
    collection = Collection.objects.get(id=collection_id)
    if request.method == "POST":
        try:
            card_ids = json.loads(request.POST.get('card_ids', '[]'))
            card_list = Card.objects.filter(id__in=card_ids).order_by('id')
        except json.JSONDecodeError:
            card_list = list(collection.cards.order_by('id'))
    else:
        card_list = list(collection.cards.order_by('id'))

    if not card_list:
        return JsonResponse({'error': 'Collection ID is required'}, status=400)
    
    for card in card_list:
        lookup.single_image_lookup(card, {}, Settings.get_default(), scrape_sold_data=True)   
    return JsonResponse({"success": True, "error": ""})

@csrf_exempt
def text_search(request, card_id):
    print("text search")
    if not card_id:
        return JsonResponse({'error': 'Card ID is required'}, status=400)
    card = Card.objects.get(id=card_id)
    search_results = lookup.single_text_lookup(card) 
    if search_results:
        return JsonResponse({"success": True, "error": ""})
    return JsonResponse({"error": True, "error": "No results"})

@csrf_exempt
def text_search_collection(request, collection_id):
    print("text search")
    if not collection_id:
        return JsonResponse({'error': 'Collection ID is required'}, status=400)
    collection = Collection.objects.get(id=collection_id)
    for card in collection.cards:
        lookup.single_text_lookup(card)
    return JsonResponse({"success": True, "error": ""})
