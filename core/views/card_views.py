import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.models.Card import Card, Collection
from core.models.Group import ProductGroup
from core.models.ListingGroup import ListingGroup
from core.models.ListedInfo import ListedInfo
from core.models.Status import StatusBase
from core.models.CardSearchResult import CardSearchResult
from services.models.models import Settings
from django.db import models
from django.core.paginator import Paginator
from math import floor
from services import lookup
from django.forms.models import model_to_dict
from django.apps import apps
from django.db import connection, transaction, IntegrityError
from django.db.models import Q
from django.template.loader import render_to_string
from core.views import collection_views
from django.utils.timezone import now
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db.models import F, Value, CharField
from django.db.models.functions import Concat
from django.conf import settings

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
    
    #print(card_list)
    if not first_card:
        first_card = card_list[0] if card_list else None

    #print("post2")
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

    #above is neutered for now until paging is re-implemented

    cc_asr = first_card.active_search_results()

    #print(cc_asr.id)
    dataset_configs = []
    for group in cc_asr.listing_groups.all():
        dataset_configs.append({
            "key": f"group-{group.id}",
            "label": group.label or "Unnamed Group",
            "color": group.color,
            "borderWidth": group.border_width,
            "lineStyle": group.line_style,
            "data": group.serialize_listings(),
            "min_price": group.min_price,
            "max_price": group.max_price,
            "min_date": group.min_date.isoformat() if group.min_date else None,
            "max_date": group.max_date.isoformat() if group.max_date else None,
            "display_default": group.display,
        })

    card_tuple = (first_card, first_card.id, cc_asr, [], [], [], [], [], [], [], [], json.dumps(dataset_configs))
            
    #print(card_tuples)
    
    return render(request, "card.html", {"card_tuple": card_tuple, "collection_id": first_card.collection.id, "settings": Settings.get_default(), "filtered":first_card.collection.cards.count()-len(card_list), "card_ids":json.dumps(card_ids), "StatusBase":StatusBase})


@csrf_exempt
def crop_review(request, collection_id):  

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
        print("no cards")
        collection = Collection.objects.get(id=collection_id)
        card_list = collection.cards.all()

    page_number = request.GET.get('page', 1)
    
    #TODO: in these paginated views we need to encapsulate the non-page data better
    card_tuples = [(card, id_, results) for card in card_list for id_ in (card.id, card.reverse_id) for results in [card.active_search_results()]]
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

import traceback
@csrf_exempt
def get_spreadsheet_data(request):
    if request.method == 'POST':
        try:
            card_ids = request.POST.getlist('card_ids[]') 
            print(card_ids)
            # Use your MEDIA_URL (usually '/media/') to prefix the file path
            #media_prefix = settings.MEDIA_URL 

            records = CardSearchResult.objects.filter(parent_card_id__in=card_ids).annotate(
                # Path: parent_card -> cropped_image object -> img field
                front_url=F('parent_card__cropped_image__img'),
                reverse_url=F('parent_card__cropped_reverse__img'),
            ).values(*CardSearchResult.listing_fields, 'front_url', 'reverse_url')
            print(records)
            return JsonResponse(list(records), safe=False)
        except Exception as e:
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=400)

def card_search_ajax(request):
    query = request.GET.get('q', '').strip()
    since_date_str = request.GET.get('since')
    is_update = request.GET.get('updates_only') is not None

    # 1. Combined Query: Search Text AND Modification Date >= Since Date
    # We start with the text filters
    filters = Q(
        Q(search_results__full_name__icontains=query) |
        Q(search_results__year__icontains=query) |
        Q(search_results__brand__icontains=query) |
        Q(search_results__team__icontains=query) |
        Q(search_results__city__icontains=query) |
        Q(search_results__subset__icontains=query)
    )

    # 2. Add the hard 'since' constraint if provided
    if since_date_str:
        target_date = parse_datetime(since_date_str)
        if target_date:
            if timezone.is_naive(target_date):
                target_date = timezone.make_aware(target_date)
            
            # Use gte (>=) for both initial search and updates per your requirement
            filters &= Q(modification_date__gte=target_date)

    # Execute the single query
    cards_list = Card.objects.filter(filters).distinct().order_by('-modification_date', '-id')
    total_count = cards_list.count()

    # 3. UI Logic (Pagination vs Patching)
    if is_update:
        # Patching: Send modified cards
        cards_to_render = cards_list
        has_next = False
        next_page = None
    else:
        # Standard Search Pagination
        paginator = Paginator(cards_list, 10)
        page_num = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_num)
        cards_to_render = page_obj
        has_next = page_obj.has_next()
        next_page = page_obj.next_page_number() if has_next else None

    # 4. Generate HTML Partial
    html = render_to_string('components/search_results_partial.html', {
        'cards': cards_to_render,
        'is_refresh': is_update
    }, request=request)

    # 5. Spreadsheet Data
    columns = CardSearchResult.listing_fields  
    table_data = [] 
    #if request.GET.get('page') == '1' or is_update: 
        #table_data = collection_views.spreadsheet_rows_from_search_result(cards_to_render, columns) 

    return JsonResponse({
        'html': html,
        'table_data': table_data,
        'col_headers': columns,
        'has_next': has_next,
        'next_page': next_page,
        'total_count': total_count,
        'server_time': timezone.now().isoformat()
    })
    
def get_card_item(request, card_id):
    card = get_object_or_404(Card, id=card_id)
        
    return render(request, 'components/card_item.html', {'card': card})

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
    print("here", request)
    if request.body and len(request.body) > 0 :
        data = json.loads(request.body)
        csr_id = data["csrId"]
        all_fields = data["allFields"]
        print(csr_id)
        print(all_fields)

    if not csr_id:
        return JsonResponse({"error": True, "message": "Missing or invalid csrId"}, status=400)
    try:
        csr = CardSearchResult.objects.get(id=int(csr_id))
    except CardSearchResult.DoesNotExist:
        return JsonResponse({"error": True, "message": f"CardSearchResult with id {csr_id} not found"}, status=404)
    
    # Convert POST data to dict and sanitize
    field_data = convert_and_sanitize(all_fields, csr)    
    print("sanitized", field_data)
    #overwrite the product group info to clear a broken group
    #right now this is only used by Clear group.  It will have to be improved to handle other use cases
    if "group_key" in field_data:
        csr.ebay_product_group = None
    try:
        csr.update_fields(field_data)
    except Exception as e:
        return JsonResponse({"error": True, "message": f"Update failed: {str(e)}"}, status=500)
    
    return JsonResponse({"success": True, "search_result":model_to_dict(csr, fields=CardSearchResult.calculated_fields) })

@csrf_exempt
def update_li_fields(request):
    if request.method != 'POST':
        return JsonResponse({"error": True, "message": "Invalid request method"}, status=405)

    # Read form-encoded POST data
    li_id = request.POST.get("li_id")
    fieldname = request.POST.get("field")
    fieldvalue = request.POST.get("value")

    if not li_id or not fieldname:
        return JsonResponse({"error": True, "message": "Missing parameters"}, status=400)

    try:
        listed_info = ListedInfo.objects.get(id=int(li_id))
    except ListedInfo.DoesNotExist:
        return JsonResponse({"error": True, "message": f"ListedInfo {li_id} not found"}, status=404)

    # Update the field
    if hasattr(listed_info, fieldname):
        setattr(listed_info, fieldname, fieldvalue)
        listed_info.save()
    else:
        return JsonResponse({"error": True, "message": f"Invalid field '{fieldname}'"}, status=400)

    return JsonResponse({"success": True})

def async_lg_monitor(request):
    since_str = request.GET.get('since')
    group_ids = request.GET.getlist('ids[]')
    
    if not since_str or not group_ids:
        return JsonResponse({'html': '', 'server_time': timezone.now().isoformat()})

    since_date = parse_datetime(since_str)
    
    # We only return groups that were actually modified after the refresh was clicked
    updated_groups = ListingGroup.objects.filter(id__in=group_ids, modification_date__gt=since_date)

    html_output = ""
    for group in updated_groups:
        html_output += render_to_string('product_listings.html', {
            'listing_group': group
        }, request=request)

    return JsonResponse({
        'html': html_output,
        'server_time': timezone.now().isoformat()
    })

#this method is fudged
def render_single_card(request, card_id):
    """
    Returns the HTML partial for a single card to be swapped into the grid.
    """
    card = get_object_or_404(Card, id=card_id)
    
    # Context should match what your main grid loop uses
    context = {
        'card': card,
        # If your status_badge logic requires specific task data:
        'id_task': card.get_latest_id_task(), 
        'pricing_task': card.get_latest_pricing_task(),
        'listing_task': card.get_latest_listing_task(),
    }
    
    return render(request, 'components/card_item_partial.html', context)

@csrf_exempt
def retokenize(request, csr_id):
    print("retokenize")

    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)
    csr = CardSearchResult.objects.get(id=csr_id)
    csr.retokenize()

    return JsonResponse({"success": True, "error": ""})

@csrf_exempt
def async_price_card(request, csr_id):  

    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)
    csr = CardSearchResult.objects.get(id=csr_id)
    card = csr.parent_card

    core_config = apps.get_app_config("core")
    core_config.queue.schedule_pricing_task(name=f"price card {card.id}", csr=csr, card=card, callback=lookup.price_only_card, params={"card_id": card.id, "settings_id":2}, on_success_status=StatusBase.PRICED)

    return JsonResponse({"success": True, "error": ""})


@csrf_exempt
def async_price_search(request, lg_id):  

    if not lg_id or lg_id == 'undefined':
        return JsonResponse({'error': 'LG ID is required'}, status=400)
    listing_group = ListingGroup.objects.get(id=lg_id)
    csr = listing_group.search_result
    card = csr.parent_card
    listing_group.save()
    #core_config = apps.get_app_config("core")
    #core_config.queue.schedule_pricing_task(name=f"price card {card.id}", csr=csr, card=card, callback=lookup.refresh_listing_groups, params={"lg_ids":[lg_id]}, on_success_status=StatusBase.PRICED)

    return JsonResponse({"success": True, "error": ""})


@csrf_exempt
def new_group(request, name):  
    clean_name = name.strip()
    
    if not clean_name:
        return JsonResponse({'success': False, 'error': 'Name is empty'}, status=400)
    
    # Use the classmethod we defined earlier
    # Ensure ProductGroup.create(name) handles the DB save properly
    group = ProductGroup.create(clean_name)

    return JsonResponse({
        'success': True,
        'id': group.id,
        'group_key': group.group_key,
        'title': group.group_title
    })
    


@csrf_exempt
def bulk_hold(request, collection_id):  

    collection = Collection.objects.filter(id=collection_id).first()
    print("cid", collection_id)
    try:
        card_ids = request.POST.getlist('card_ids[]')
        if len(card_ids):
            print("lenny", len(card_ids))
            card_list = Card.objects.filter(id__in=card_ids).order_by('id')
        else:
            print("no cards", len(card_ids))
            card_list = list(collection.cards.order_by('id'))
    except json.JSONDecodeError:
        card_list = list(collection.cards.order_by('id'))
    print(card_list)

    for card in card_list:
        perform_status_update(card.active_search_results().id, StatusBase.HELD)

    return JsonResponse({"success": True, "error": ""})

def perform_status_update(csr_id, new_status):
    # Fetch and update
    obj = CardSearchResult.objects.get(id=csr_id)
    obj.overall_status = new_status
    obj.save(update_fields=['overall_status'])
    obj.parent_card.update_mod_date()

@csrf_exempt
def update_csr_status_only(request, csr_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')
            
            perform_status_update(csr_id, new_status)            
            
            return JsonResponse({
                'success': True, 
                'new_mod_date': ""
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@csrf_exempt
def price_only(request, csr_id):
    print("reprice", csr_id)

    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)

    lookup.price_only(csr_id, 2)

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
            lookup.text_refinement(csr, "", all_fields, Settings.get_default()) 
        csr.save()
    
    return JsonResponse({"success": True, "error": ""})

    
@csrf_exempt
def clear_listed_info(request, card_id):
    
    card = Card.objects.get(id=card_id)
    card.clear_listed_info()
    
    return JsonResponse({"success": True, "error": ""})