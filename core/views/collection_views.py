# Collection-related views
from django.views.decorators.csrf import csrf_exempt
import os
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.core.files.storage import default_storage
from django.utils.timezone import now
from services import lookup
from services.models import Settings
from core.models.Card import Card, Collection
from core.models.CardSearchResult import CardSearchResult
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, F

@csrf_exempt
def update_collection(request):
    if request.method != 'POST':
        return JsonResponse({"error": True, "message": "Invalid request method"}, status=405)

    collection_id = request.POST.get("collectionId")
    if not collection_id or not collection_id.isdigit():
        return JsonResponse({"error": True, "message": "Missing or invalid collectionId"}, status=400)

    try:
        collection = Collection.objects.get(id=int(collection_id))
    except Collection.DoesNotExist:
        return JsonResponse({"error": True, "message": f"Collection with id {collection_id} not found"}, status=404)

    new_name = request.POST.get("name", "").strip()
    if not new_name:
        return JsonResponse({"error": True, "message": "Missing collection name"}, status=400)

    collection.name = new_name
    collection.save()
    return JsonResponse({"success": True, "message": "Collection updated successfully"})

@csrf_exempt
def export_collection(request, collection_id):
    print("export collection")
    settings = Settings.objects.first()

    if not collection_id or collection_id == 'undefined':
        return JsonResponse({'error': 'Collection ID is required'}, status=400)
    
    collection = Collection.objects.get(id=collection_id)
    csrs = collection.get_default_exports()

    return export_handler.export_zip(csrs)

def render_collection_list(request, collections, per_page, collection_id=None):
    print("render", per_page, collection_id)
    
    settings = Settings.get_default()       
    paginator = Paginator(collections, per_page)
    
    if collection_id:
        page_number = next((c.id for c in collections if c.id == collection_id), None)
    else:
        page_number = request.GET.get('page')

    page_obj = paginator.get_page(page_number)
    return render(request, "manage_collection.html", {"page_obj": page_obj, "settings": settings})

#view specific manage-collections
def manage_collection(request):
    collections = Collection.objects.filter(
        Q(parent_collection__isnull=True) | Q(id=F('parent_collection_id'))
    ).order_by('-id')
    settings = Settings.get_default()    
    return render_collection_list(request, collections, settings.nr_collection_page_items)

#view single collections
#TODO: should do this based on specific next_collection calls, pagniator is just messy
#TODO: fuck the paginator for now
def view_collection(request, collection_id):
    collections = Collection.objects.all().order_by('id')
    collection = Collection.objects.get(id=collection_id)
    settings = Settings.get_default()    
    return render(request, "collection.html", {"collection":collection, "settings":settings, "collections":collections, "columns":CardSearchResult.spreadsheet_fields})

def set_default_collection(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    Collection.objects.update(is_default=False)

    # Set the one with matching ID to True
    Collection.objects.filter(id=collection_id).update(is_default=True)

@csrf_exempt
def move_card_to_collection(card_or_id, collection_or_id):
    if not isinstance(collection_or_id, Collection):
        collection_or_id = get_object_or_404(Collection, id=collection_or_id)

    if not isinstance(card_or_id, Card):
        card_or_id = get_object_or_404(Card, id=card_or_id)
    
    card_or_id.collection = collection_or_id
    card_or_id.save()

@csrf_exempt
def move_to_collection2(request):
    print("mtc")
    print(request.body)
    if request.method == "POST":
        data = json.loads(request.body)
        print(data)
        collection_to_move_id = data.get('collection_to_move')
        target_collection_id = data.get('target_collection')
        cards_to_move = data.get('cards_to_move')
        
        collection_to_move = get_object_or_404(Collection, id=int(collection_to_move_id))
        target_collection = get_object_or_404(Collection, id=int(target_collection_id))

        #cards passed in: send the cards to the new collection
        if cards_to_move:
            for card in cards_to_move:
                move_card_to_collection(card, target_collection)
        else:
            print("move collection", collection_to_move_id, target_collection_id)
            collection_to_move.parent_collection = target_collection
            
        collection_to_move.save()

    return JsonResponse({"success": True})