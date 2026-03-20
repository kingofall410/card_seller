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
from services.models.models import Settings
from core.models.Card import Card, Collection
from services import lookup
from core.models.CardSearchResult import CardSearchResult
from core.views import card_views, image_views
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, F
from django.forms.models import model_to_dict
from django.apps import apps
from django.db.models import Prefetch
@csrf_exempt
def price_collection(request, collection_id):  

    collection = Collection.objects.get(id=collection_id)
    try:
        card_ids = request.GET.getlist('card_ids')
        print(card_ids)
        card_list = Card.objects.filter(id__in=card_ids).order_by('id')
    except json.JSONDecodeError:
        card_list = list(collection.cards.order_by('id'))
    print(card_list)
    for card in card_list:
        cc_asr = card.active_search_results()
        #lookup.text_refinement(cc_asr)
        card_views.price_only(request, cc_asr.id)

    return JsonResponse({"success": True, "error": ""})

def identify_collection(request, collection_id):

    collection = Collection.objects.get(id=collection_id)
    try:
        card_ids = request.GET.getlist('card_ids')
        print(card_ids)
        card_list = Card.objects.filter(id__in=card_ids).order_by('id')
    except json.JSONDecodeError:
        card_list = list(collection.cards.order_by('id'))
    
    
    core_config = apps.get_app_config("core")
    for card in card_list:
        core_config.queue.schedule_id_task(name=f"ID card {card.id}", callback=image_views.perform_id, params={"card_id":card.id})

    return JsonResponse({"success": True, "error": ""})

@csrf_exempt
def update_collection(request):
    collection_id = request.POST.get("collectionId")
    field_name = request.POST.get("field")
    field_value = request.POST.get("value")

    # 1. Fetch collection safely
    try:
        collection = Collection.objects.get(id=collection_id)
    except Collection.DoesNotExist:
        return JsonResponse({"error": True, "message": "Collection not found"}, status=404)

    # 2. Ensure the field exists on the model
    if field_name not in [f.name for f in Collection._meta.get_fields()]:
        return JsonResponse({"error": True, "message": f"Invalid field '{field_name}'"}, status=400)

    # 3. Convert field_value to the correct Python type
    field = Collection._meta.get_field(field_name)
    try:
        python_value = field.to_python(field_value)
    except Exception as e:
        return JsonResponse({"error": True, "message": f"Invalid value: {e}"}, status=400)

    # 4. Assign and save
    setattr(collection, field_name, python_value)
    collection.save(update_fields=[field_name])

    return JsonResponse({
        "success": True,
        "message": "Collection updated successfully",
        "collection": model_to_dict(collection, fields=[field_name])
    })


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
    columns = CardSearchResult.mini_spreadsheet_fields
    #rows = (spreadsheet_rows_from_search_result(collection.cards.all(), columns) for collection in collections)
    return render(request, "manage_collection.html", {"page_obj": page_obj, "settings": settings, "columns":columns, "rows":rows})

#view specific manage-collections
def manage_collection(request):
    collections = Collection.objects.filter(
        Q(parent_collection__isnull=True) | Q(id=F('parent_collection_id'))
    ).order_by('-id')
    settings = Settings.get_default()    
    return render_collection_list(request, collections, settings.nr_collection_page_items)

def spreadsheet_rows_from_search_result(cards, field_names):
    rows = []
    for card in cards:
        asr = card.active_search_results()
        row = {}
        if asr:
            for field in field_names:
                display_attr = f'display_{field}'
                value = getattr(asr, display_attr)
                row[field] = value if value is not None else ''
            row["thumb_url"] = card.cropped_image.url() if card.cropped_image else ""
            row["reverse_thumb_url"] = card.cropped_reverse.url() if card.cropped_reverse else ""
            row["card_id"] = card.id
            rows.append(row)
    return rows

#view single collections
#TODO: should do this based on specific next_collection calls, pagniator is just messy
#TODO: fuck the paginator for now


def new_collection(request):
    collection = Collection.objects.create()
    return redirect('view_collection', collection.id)


def view_collection(request, collection_id):
    
    collection = Collection.objects.prefetch_related(
        'cards__search_results',
        'cards__listed_card_info',
        'cards__listing_tasks'
    ).get(id=collection_id)
    settings = Settings.get_default()
    columns = []
    rows = []
    #columns = CardSearchResult.mini_spreadsheet_fields
    #rows = spreadsheet_rows_from_search_result(collection.cards.all(), columns)
    return render(request, "collection.html", {"collection":collection, "settings":settings, "columns":columns, "rows":rows})

def listing_view(request):
    columns = CardSearchResult.listing_spreadsheet_fields

    cards = Card.objects.filter(
        Q(search_results__ebay_listing_id__isnull=False) & ~Q(search_results__ebay_listing_id='') |
        Q(search_results__sku__isnull=False) & ~Q(search_results__sku='') |
        Q(search_results__ebay_offer_id__isnull=False) & ~Q(search_results__ebay_offer_id='') & ~Q(search_results__ebay_offer_id='None' )|
        Q(search_results__ebay_listing_datetime__isnull=False)
    ).distinct()
    rows = spreadsheet_rows_from_search_result(cards, columns)
        
    return render(request, "spreadsheet_only.html", {"columns":columns, "rows":rows})

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
def move_to_collection3(request, collection_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            card_ids = data.get('card_ids', [])
            target_collection = Collection.objects.get(id=collection_id)

            if not card_ids:
                return JsonResponse({'ok': False, 'message': 'No cards specified'}, status=400)

            # Bulk update the collection_id for all selected cards
            Card.objects.filter(id__in=card_ids).update(collection=target_collection)

            return JsonResponse({
                'ok': True, 
                'message': f'Moved {len(card_ids)} cards successfully.'
            })

        except Exception as e:
            return JsonResponse({'ok': False, 'message': str(e)}, status=500)
            
    return JsonResponse({'ok': False, 'message': 'Invalid method'}, status=405)