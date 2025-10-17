import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.models.Card import Card, Collection
from core.models.Status import StatusBase
from core.models.CardSearchResult import CardSearchResult
from services.models import Settings
from django.db import models
from django.core.paginator import Paginator
from math import floor
from services import lookup
from django.forms.models import model_to_dict


# Card-related views
@csrf_exempt
def view_card(request, card_id):
    print("view_card", request.body)
    settings = Settings.get_default()
    
    if card_id:
        first_card = Card.objects.get(id=card_id)
    
    card_ids = []
    if request.method == "POST":
        try:
            card_ids = json.loads(request.POST.get('card_ids', '[]'))
        except json.JSONDecodeError:
            pass

    if len(card_ids) <= 0:
        card_list = list(first_card.collection.cards.order_by('id'))
    else:
        card_list = Card.objects.filter(id__in=card_ids).order_by('id')
    
    print(card_list)
    if not first_card:
        first_card = card_list[0] if card_list else None

    print("post2")
    page_number = request.GET.get('page')
        
    #at this point we know the cards in the collection and the current card
    #no page number means just go to card_id
    if not page_number and card_id and card_list:
        try:
            index = next((i for i, c in enumerate(card_list) if c.id == int(card_id)))
            page_number = floor(index) + 1
        except StopIteration:
            page_number = 1
    #print("post3")

    card_tuples = []
    #set up the tuples to exclude detailed data for non-current cards
    for i, collection_card in enumerate(card_list):
        cc_asr = collection_card.active_search_results()
        if i == int(page_number)-1:
            #print("prices", json.dumps(cc_asr.get_prices(sold=True)))
            card_tuple = (collection_card, collection_card.id, cc_asr, json.dumps(cc_asr.get_prices(listed=True)), json.dumps(cc_asr.get_prices(sold_refined=True)), json.dumps(cc_asr.get_prices(sold=True)), json.dumps(cc_asr.get_prices(refined=True)))
        else:
            card_tuple = (collection_card, collection_card.id, cc_asr, [], [])
            
        card_tuples.append(card_tuple)

    #print(card_tuples)
    paginator = Paginator(card_tuples, 1)
    page_obj = paginator.get_page(page_number)


    #print("fin:", page_number, "of", paginator.num_pages, card, card.active_search_results())
    
    return render(request, "card.html", {"page_obj": page_obj, "collection_id": first_card.collection.id, "settings": Settings.get_default(), "filtered":first_card.collection.cards.count()-len(card_list), "card_ids":json.dumps(card_ids)})
        
@csrf_exempt
def crop_review(request, collection_id):

    settings = Settings.get_default()
    cards = []
    if not collection_id or collection_id == 'undefined':
        return JsonResponse({'error': 'Collection ID is required'}, status=400)
    
    collection = Collection.objects.get(id=collection_id)
    if request.method == 'POST' and request.body:
        data = json.loads(request.body)
        if data:
            card_ids = data.get('card_ids', [])
            print("Received card_ids:", card_ids)
            cards = Card.objects.filter(id__in=card_ids).order_by('id')       
        
    if not cards:
        print("no cards", collection_id)
        cards = collection.cards.all().order_by('id')
 
    page_number = request.GET.get('page', 1)
    
    #TODO: in these paginated views we need to encapsulate the non-page data better
    card_tuples = [(card, id_, results) for card in cards for id_ in (card.id, card.reverse_id) for results in [card.active_search_results()]]
    #print(card_tuples)
    paginator = Paginator(card_tuples, len(card_tuples))
    page_obj = paginator.get_page(page_number)
    #print("fin:", page_number, "of", paginator.num_pages)
    return render(request, "crop_review.html", {"page_obj": page_obj, "filtered":(collection.cards.count()-len(card_tuples))})

def save_and_next(request, card_id):
    if request.method == "POST":
        upload_crop(request)
        return next(request, card_id)

def next_card(request, card_id):
    if request.method == "POST":
        # Save logic here
        delta = 1
        if card_id[0] == '-':
            delta = -1
        next_card_id = card_id + delta
        return redirect("crop_review", card_id=next_card_id)

@csrf_exempt
def hold_card(request, csr_id):
    print("hold", csr_id)
    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)
    csr = CardSearchResult.objects.get(id=csr_id)
    settings = Settings.get_default()
    if request.method == 'POST':
        field_data = convert_and_sanitize(request.POST.dict(), csr)
        csr.update_fields(field_data)
    csr.status = StatusBase.LOCKED
    csr.save()
    return JsonResponse({"success": 'true'}, status=200)

@csrf_exempt
def delete(request):
    print("delete", request)
    if request.method == 'POST':
        print("POST")
        card_id = request.POST.get('card_id')
        collection_id = request.POST.get('collection_id')
        try:
            if card_id:
                card = Card.objects.get(id=card_id)
                card.delete()
            if collection_id:
                collection = Collection.objects.get(id=collection_id)
                collection.delete()
        except (Collection.DoesNotExist, Card.DoesNotExist):
            return JsonResponse({'error': 'Card/Collection not found'}, status=404)
    return JsonResponse({"success": True, "error": ""})

def convert_and_sanitize(field_data, csr):
    field_data.pop("csrId", None)  # Remove csrId from field data
    field_data.pop("csrfmiddlewaretoken", None)  # Remove CSRF token
    # Coerce boolean fields
    for key, value in field_data.items():
        field = csr._meta.get_field(key) if key in [f.name for f in csr._meta.fields] else None
        if isinstance(field, models.BooleanField):
            if isinstance(value, bool):
                field_data[key] = value
            else:
                field_data[key] = value.lower() in ["true", "1", "yes"]
    return field_data

@csrf_exempt
def update_csr_fields(request):
    if request.method != 'POST':
        return JsonResponse({"error": True, "message": "Invalid request method"}, status=405)
    
    data = json.loads(request.body)
    csr_id = data["csrId"]
    all_fields = data["allFields"]
    if not csr_id:
        return JsonResponse({"error": True, "message": "Missing or invalid csrId"}, status=400)
    try:
        csr = CardSearchResult.objects.get(id=int(csr_id))
    except CardSearchResult.DoesNotExist:
        return JsonResponse({"error": True, "message": f"CardSearchResult with id {csr_id} not found"}, status=404)
    # Convert POST data to dict and sanitize
    field_data = convert_and_sanitize(all_fields, csr)    
    try:
        csr.update_fields(field_data)
    except Exception as e:
        return JsonResponse({"error": True, "message": f"Update failed: {str(e)}"}, status=500)
    
    return JsonResponse({"success": True, "search_result":model_to_dict(csr, fields=CardSearchResult.calculated_fields) })
    

@csrf_exempt
def retokenize(request, csr_id):
    print("retokenize")

    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)
    csr = CardSearchResult.objects.get(id=csr_id)
    csr.retokenize()

    return JsonResponse({"success": True, "error": ""})

@csrf_exempt
def price_only(request, csr_id):
    print("reprice")

    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)
    csr = CardSearchResult.objects.get(id=csr_id)
    lookup.price_only(csr)

    return JsonResponse({"success": True, "error": ""})

@csrf_exempt
def price_collection(request, collection_id):  

    csr_ids = []
    csrs = []
    cards = None
    if not collection_id or collection_id == 'undefined':
        return JsonResponse({'error': 'Collection ID is required'}, status=400)
    
    if request.method == 'POST':
        print("post", request.POST)
        card_ids = request.POST.getlist('card_ids', '[]')
        print(card_ids)
        cards = Card.objects.filter(id__in=card_ids)
        
    if not cards:
        print("no cards")
        collection = Collection.objects.get(id=collection_id)
        cards = collection.cards.all()
 
    for card in cards:
        cc_asr = card.active_search_results()
        lookup.text_refinement(cc_asr, cc_asr.text_search_string)
        lookup.price_only(card.active_search_results())

    return JsonResponse({"success": True, "error": ""})

@csrf_exempt
def text_filter(request):
    all_fields = {}
    csr_ids = []    

    if request.body:
        data = json.loads(request.body)
        if data:
            all_fields = data.get('required_words', {})
            csr_ids = data.get('csr_ids', [])
            new_search = data.get('new_search', False)
    
    csrs = CardSearchResult.objects.filter(id__in=csr_ids)

    if new_search:
        #TODO: ultimately we'll need to separate this from update_fields to filter by something that's not a current value
        for csr in csrs:
            csr.update_fields(all_fields)
            lookup.text_refinement(csr, csr.text_search_string, all_fields, Settings.get_default())

    

        print("filtered listings:", csr.id, len(csr.filtered_listings.all()))
        csr.save()
    
    return JsonResponse({"success": True, "error": ""})